# -*- coding: utf-8 -*-
import uuid
from decimal import Decimal
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


# Forward-only payout state transitions — terminal states CANNOT regress.
PAYOUT_TRANSITIONS = {
    'draft': ['pending_approval'],
    'pending_approval': ['approved', 'rejected'],
    'approved': ['submitted'],
    'submitted': ['processing'],
    'processing': ['succeeded', 'failed'],
    'failed': ['submitted'],  # Retry is allowed from failed → resubmit
    'succeeded': ['refund_pending'],  # Only refund path from success
    'rejected': [],  # Terminal
    'refund_pending': ['refund_processing'],
    'refund_processing': ['refunded', 'refund_failed'],
    'refunded': [],  # Terminal
    'refund_failed': ['refund_pending'],  # Retry refund
}


class VinPayout(models.Model):
    """
    Payout State Machine.
    
    Manages the lifecycle of a single payout from escrow to creative partner.
    Enforces forward-only state transitions — terminal states (succeeded, rejected, refunded)
    cannot regress per locked architecture rules.
    
    Separation of Duties (SoD / Four-Eyes): The user who initiates a payout
    cannot approve it. Enforced at the approval step.
    """
    _name = 'vin.payout'
    _description = 'VIN Payout State Machine'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    uuid = fields.Char(
        string='Payout UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    reference = fields.Char(
        string='Payout Reference',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: f"PAY-{uuid.uuid4().hex[:8].upper()}"
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    escrow_account_id = fields.Many2one(
        'vin.escrow.account',
        string='Source Escrow Account',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    allocation_id = fields.Many2one(
        'vin.escrow.allocation',
        string='Milestone Allocation',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    contract_id = fields.Many2one(
        'vin.contract',
        string='Governing Contract',
        related='escrow_account_id.contract_id',
        store=True,
        readonly=True
    )
    partner_profile_id = fields.Many2one(
        'creative.partner.profile',
        string='Payee (Creative Partner)',
        related='escrow_account_id.partner_profile_id',
        store=True,
        readonly=True
    )
    provider_id = fields.Many2one(
        'vin.payment.provider',
        string='Payment Provider',
        index=True,
        ondelete='restrict',
        tracking=True
    )

    # --- Amounts (Decimal-safe via Monetary) ---
    gross_amount = fields.Monetary(
        string='Gross Payout Amount',
        currency_field='currency_id',
        required=True,
        readonly=True,
        help="Total amount before any deductions (partner net from escrow release)."
    )
    tax_withholding = fields.Monetary(
        string='Tax Withholding (WHT)',
        currency_field='currency_id',
        default=0.0,
        readonly=True,
        help="Tax withheld at source per jurisdiction rules."
    )
    net_payout_amount = fields.Monetary(
        string='Net Payout to Partner',
        currency_field='currency_id',
        compute='_compute_net_payout',
        store=True,
        help="Gross minus tax withholding. This is the actual disbursed amount."
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        readonly=True
    )
    payout_currency_id = fields.Many2one(
        'res.currency',
        string='Payout Currency (Partner)',
        help="If cross-border, this may differ from escrow currency."
    )
    fx_rate = fields.Float(
        string='Payout FX Rate',
        digits=(12, 6),
        default=1.0,
        readonly=True
    )

    # --- State Machine ---
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('pending_approval', 'Pending Approval (Four-Eyes)'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('submitted', 'Submitted to Provider'),
            ('processing', 'Provider Processing'),
            ('succeeded', 'Payout Succeeded'),
            ('failed', 'Payout Failed'),
            ('refund_pending', 'Refund Pending'),
            ('refund_processing', 'Refund Processing'),
            ('refunded', 'Refunded'),
            ('refund_failed', 'Refund Failed'),
        ],
        string='Payout State',
        required=True,
        default='draft',
        tracking=True,
        index=True
    )

    # --- Provider References ---
    provider_transaction_id = fields.Char(
        string='Provider Transaction ID',
        readonly=True,
        index=True,
        tracking=True
    )
    idempotency_key = fields.Char(
        string='Idempotency Key',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False,
        help="Ensures provider-side deduplication."
    )
    retry_count = fields.Integer(
        string='Retry Attempts',
        default=0,
        readonly=True
    )
    max_retries = fields.Integer(
        string='Maximum Retry Attempts',
        default=3,
        readonly=True
    )

    # --- SoD Tracking ---
    initiated_by_id = fields.Many2one(
        'res.users',
        string='Initiated By',
        readonly=True,
        index=True
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By (Four-Eyes)',
        readonly=True,
        index=True,
        help="Must differ from initiated_by_id per Separation of Duties."
    )

    # --- Event Log ---
    event_ids = fields.One2many(
        'vin.payment.event',
        'payment_id',
        string='Payment Event Log',
        readonly=True
    )

    @api.depends('gross_amount', 'tax_withholding')
    def _compute_net_payout(self):
        for record in self:
            record.net_payout_amount = record.gross_amount - record.tax_withholding

    def _validate_transition(self, target_state):
        """Enforces forward-only state machine transitions."""
        self.ensure_one()
        allowed = PAYOUT_TRANSITIONS.get(self.state, [])
        if target_state not in allowed:
            raise UserError(_(
                "Invalid payout state transition: '%s' → '%s'. "
                "Allowed transitions: %s"
            ) % (self.state, target_state, ', '.join(allowed) or 'NONE (terminal)'))

    def _record_event(self, event_type, provider_ref=None, raw_response=None,
                      failure_code=None, failure_message=None):
        """Appends an immutable payment event to the log."""
        self.ensure_one()
        return self.env['vin.payment.event'].sudo().create({
            'payment_id': self.id,
            'event_type': event_type,
            'provider_reference': provider_ref,
            'provider_raw_response': raw_response,
            'amount': self.gross_amount,
            'currency_id': self.currency_id.id,
            'failure_code': failure_code,
            'failure_message': failure_message,
            'idempotency_key': self.idempotency_key,
        })

    # --- State Machine Actions ---

    def action_submit_for_approval(self):
        """Transitions to pending_approval. Records the initiator for SoD enforcement."""
        for record in self:
            record._validate_transition('pending_approval')
            record.write({
                'state': 'pending_approval',
                'initiated_by_id': self.env.user.id
            })
            record._record_event('initiated')

    def action_approve(self):
        """
        Four-Eyes Approval: The approver MUST differ from the initiator.
        Locked Architecture Decision: Separation of Duties for financial disbursements.
        """
        for record in self:
            record._validate_transition('approved')

            # SoD: Enforce Four-Eyes Principle
            if record.initiated_by_id == self.env.user:
                raise UserError(_(
                    "Separation of Duties Violation: The user who initiated this payout "
                    "cannot also approve it. A different authorized user must approve."
                ))

            record.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id
            })
            record._record_event('submitted')

            # Audit trail
            self.env['vin.audit.event'].sudo().record_event(
                action='PAYOUT_APPROVED',
                subject_type='vin.payout',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'reference': record.reference,
                    'amount': float(record.gross_amount),
                    'initiated_by': record.initiated_by_id.login,
                    'approved_by': self.env.user.login,
                }
            )

    def action_reject(self):
        """Rejects the payout. Terminal state."""
        for record in self:
            record._validate_transition('rejected')
            record.write({'state': 'rejected'})
            record._record_event('cancelled')

    def action_mark_submitted(self, provider_transaction_id):
        """Marks payout as submitted to the external payment provider."""
        for record in self:
            record._validate_transition('submitted')
            record.write({
                'state': 'submitted',
                'provider_transaction_id': provider_transaction_id
            })
            record._record_event('submitted', provider_ref=provider_transaction_id)

    def action_mark_processing(self):
        """Provider confirms processing has begun."""
        for record in self:
            record._validate_transition('processing')
            record.write({'state': 'processing'})
            record._record_event('processing')

    def action_mark_succeeded(self, provider_ref=None, raw_response=None):
        """
        Marks payout as succeeded.
        This is a TERMINAL state for the payment flow.
        Triggers downstream escrow ledger posting (cash disbursement).
        """
        for record in self:
            record._validate_transition('succeeded')
            record.write({'state': 'succeeded'})
            record._record_event(
                'succeeded',
                provider_ref=provider_ref,
                raw_response=raw_response
            )

            # Post escrow disbursement ledger entry
            self._post_disbursement_ledger(record)

            # Audit trail
            self.env['vin.audit.event'].sudo().record_event(
                action='PAYOUT_SUCCEEDED',
                subject_type='vin.payout',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'reference': record.reference,
                    'net_payout': float(record.net_payout_amount),
                    'provider_ref': provider_ref,
                }
            )

    def action_mark_failed(self, failure_code=None, failure_message=None, raw_response=None):
        """Marks payout as failed. Can be retried if under max_retries."""
        for record in self:
            record._validate_transition('failed')
            record.write({
                'state': 'failed',
                'retry_count': record.retry_count + 1
            })
            record._record_event(
                'failed',
                failure_code=failure_code,
                failure_message=failure_message,
                raw_response=raw_response
            )

    def action_retry_submission(self):
        """Re-submits a failed payout if retry count is within limits."""
        for record in self:
            if record.state != 'failed':
                raise UserError(_("Can only retry payouts in 'failed' state."))
            if record.retry_count >= record.max_retries:
                raise UserError(_(
                    "Maximum retry attempts (%s) exhausted for payout %s."
                ) % (record.max_retries, record.reference))

            # Generate new idempotency key for retry
            new_idem_key = str(uuid.uuid4())
            record.write({
                'state': 'submitted',
                'idempotency_key': new_idem_key
            })
            record._record_event('submitted')

    def _post_disbursement_ledger(self, payout):
        """
        Posts the actual cash disbursement to the virtual escrow ledger
        when a payout succeeds. This drains the cash asset account.
        
        Balanced double-entry:
          Dr: liability_partner (clear payable)
          Cr: cash (actual disbursement)
        """
        from decimal import Decimal as D
        net = D(str(payout.net_payout_amount))
        account = payout.escrow_account_id

        entries = [
            {'account_type': 'liability_partner', 'debit': float(net), 'credit': 0.0},
            {'account_type': 'cash', 'debit': 0.0, 'credit': float(net)},
        ]

        self.env['vin.ledger.entry'].post_balanced_transaction(
            escrow_account=account,
            entries=entries,
            reference=f"Payout Disbursement: {payout.reference}",
            transaction_id=str(uuid.uuid4())
        )
