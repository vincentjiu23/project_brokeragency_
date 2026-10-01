# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from decimal import Decimal
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class VinDispute(models.Model):
    """
    Tiered Acceptance Dispute Model (Q91–Q98, Q175, ADR-002, ADR-003).
    Manages dispute opening, automatic virtual escrow freeze/locking,
    tiered mediation and binding arbitration, evidence packaging,
    and balanced resolution execution.
    """
    _name = 'vin.dispute'
    _description = 'VIN Acceptance Dispute & Arbitration Case'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    dispute_number = fields.Char(string='Dispute Number', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', required=True, index=True, default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False)

    title = fields.Char(string='Dispute Subject', required=True, tracking=True)
    description = fields.Text(string='Detailed Factual Basis & Claims', required=True)

    dispute_type = fields.Selection([
        ('deliverable_rejection', 'Client Rejected Deliverable Outside Scope'),
        ('excessive_revisions', 'Revision Requests Exceed Agreed Limit / Scope Creep'),
        ('missed_deadline', 'Breach of Delivery Milestone SLA'),
        ('quality_defect', 'Deliverable Fails Technical Acceptance Criteria'),
        ('payment_withholding', 'Unjustified Milestone Acceptance Withholding'),
        ('other', 'Other Contractual Breach')
    ], string='Dispute Classification', required=True, default='deliverable_rejection', tracking=True)

    contract_id = fields.Many2one('vin.contract', string='Contract Reference', required=True, index=True, tracking=True)
    workstream_id = fields.Many2one('vin.workstream', string='Workstream', index=True)
    milestone_id = fields.Many2one('vin.milestone', string='Milestone Reference', index=True, tracking=True)
    deliverable_id = fields.Many2one('vin.deliverable', string='Deliverable Reference', index=True)
    escrow_allocation_id = fields.Many2one('vin.escrow.allocation', string='Escrow Allocation to Freeze', required=True, index=True, tracking=True)

    disputed_amount = fields.Float(string='Disputed Escrow Amount', required=True, tracking=True)
    currency = fields.Char(string='Currency', default='USD', required=True)

    initiator_type = fields.Selection([
        ('client', 'Client Organization'),
        ('partner', 'Creative Partner')
    ], string='Filing Party', required=True, default='client', tracking=True)

    client_organization_id = fields.Many2one('vin.organization', string='Client Organization', related='contract_id.client_organization_id', store=True)
    partner_profile_id = fields.Many2one('creative.partner.profile', string='Creative Partner Profile', related='contract_id.partner_profile_id', store=True)
    opened_by_user_id = fields.Many2one('res.users', string='Filed By', default=lambda self: self.env.user, readonly=True)

    state = fields.Selection([
        ('draft', 'Draft Filing'),
        ('open', 'Tier 1: Direct Negotiation'),
        ('escalated_mediation', 'Tier 2: Platform Mediation'),
        ('escalated_arbitration', 'Tier 3: Binding Arbitration'),
        ('resolved', 'Settlement Agreed'),
        ('closed', 'Executed & Closed'),
        ('withdrawn', 'Withdrawn')
    ], string='Dispute Status', default='draft', required=True, tracking=True)

    resolution_type = fields.Selection([
        ('full_release_to_partner', '100% Escrow Released to Partner'),
        ('full_refund_to_client', '100% Escrow Refunded to Client'),
        ('split_settlement', 'Agreed Custom Split Settlement'),
        ('revision_mandated', 'Remediation: Partner Given Window to Fix Defect'),
        ('contract_terminated', 'Mutual Termination & Final Settlement')
    ], string='Resolution Type', tracking=True)

    client_refund_amount = fields.Float(string='Refund to Client', default=0.0, tracking=True)
    partner_payout_amount = fields.Float(string='Disbursement to Partner', default=0.0, tracking=True)
    mediator_user_id = fields.Many2one('res.users', string='Assigned Platform Mediator', tracking=True)
    resolution_summary = fields.Text(string='Formal Resolution Order / Ruling')
    resolved_at = fields.Datetime(string='Resolved At', readonly=True)

    evidence_ids = fields.One2many('vin.dispute.evidence', 'dispute_id', string='Submitted Evidence Packages')
    arbitration_case_id = fields.One2many('vin.arbitration.case', 'dispute_id', string='Arbitration Case')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('dispute_number', _('New')) == _('New'):
                vals['dispute_number'] = f"DISP-{uuid.uuid4().hex[:8].upper()}"
        return super().create(vals_list)

    def action_open(self):
        """
        Opens the dispute and atomically FREEZES the associated escrow allocation.
        Prevents any payout or milestone release until dispute is formally resolved.
        """
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft disputes can be opened."))
            if not rec.escrow_allocation_id:
                raise UserError(_("An escrow allocation must be linked to freeze funds."))

            # Atomically freeze escrow
            alloc = rec.escrow_allocation_id
            account = alloc.escrow_account_id

            alloc.write({'state': 'disputed'})
            account.write({
                'state': 'locked',
                'lock_reason': f"FROZEN: Active dispute {rec.dispute_number} on milestone {rec.milestone_id.name if rec.milestone_id else 'Deliverable'}"
            })

            rec.write({'state': 'open'})

            # Emit DISPUTE_OPENED audit event
            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'DISPUTE_OPENED',
                    'entity_name': 'vin.dispute',
                    'entity_id': str(rec.id),
                    'state_after': 'open',
                    'payload': json.dumps({
                        'dispute_number': rec.dispute_number,
                        'contract_id': rec.contract_id.id,
                        'disputed_amount': rec.disputed_amount,
                        'escrow_allocation_uuid': alloc.uuid
                    })
                })

            rec.message_post(body=_("Dispute formally opened. Escrow Allocation %s and Escrow Account %s are now LOCKED.") % (alloc.uuid, account.account_number))

    def action_escalate_mediation(self):
        """Escalate to Tier 2 Platform Mediation."""
        for rec in self:
            if rec.state != 'open':
                raise UserError(_("Dispute must be in Direct Negotiation to escalate to mediation."))
            rec.write({
                'state': 'escalated_mediation',
                'mediator_user_id': self.env.user.id
            })

            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'DISPUTE_ESCALATED',
                    'entity_name': 'vin.dispute',
                    'entity_id': str(rec.id),
                    'state_after': 'escalated_mediation',
                    'payload': json.dumps({'dispute_number': rec.dispute_number, 'tier': 'Tier 2: Mediation'})
                })

            rec.message_post(body=_("Dispute escalated to Tier 2 Platform Mediation under mediator %s.") % self.env.user.name)

    def action_escalate_arbitration(self):
        """Escalate to Tier 3 Binding Arbitration."""
        for rec in self:
            if rec.state not in ['open', 'escalated_mediation']:
                raise UserError(_("Dispute cannot be escalated to arbitration from current state."))
            rec.write({'state': 'escalated_arbitration'})

            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'DISPUTE_ESCALATED',
                    'entity_name': 'vin.dispute',
                    'entity_id': str(rec.id),
                    'state_after': 'escalated_arbitration',
                    'payload': json.dumps({'dispute_number': rec.dispute_number, 'tier': 'Tier 3: Binding Arbitration'})
                })

            rec.message_post(body=_("Dispute escalated to Tier 3 Binding Legal Arbitration."))

    def action_resolve_settlement(self, resolution_type, client_refund=0.0, partner_payout=0.0, summary=None):
        """
        Executes formal dispute resolution with strict zero-variance validation.
        Unfreezes escrow and executes balanced disbursements.
        """
        self.ensure_one()
        if self.state not in ['open', 'escalated_mediation', 'escalated_arbitration']:
            raise UserError(_("Only active disputes can be resolved."))

        total_disputed = Decimal(str(self.disputed_amount))
        refund_dec = Decimal(str(client_refund))
        payout_dec = Decimal(str(partner_payout))

        if resolution_type == 'full_refund_to_client':
            refund_dec = total_disputed
            payout_dec = Decimal('0.00')
        elif resolution_type == 'full_release_to_partner':
            refund_dec = Decimal('0.00')
            payout_dec = total_disputed
        elif resolution_type == 'split_settlement':
            if (refund_dec + payout_dec) != total_disputed:
                raise ValidationError(_(
                    "Split settlement zero-variance check failed: Refund (%s) + Payout (%s) != Disputed Amount (%s)."
                ) % (refund_dec, payout_dec, total_disputed))

        # Update dispute record
        self.write({
            'state': 'resolved',
            'resolution_type': resolution_type,
            'client_refund_amount': float(refund_dec),
            'partner_payout_amount': float(payout_dec),
            'resolution_summary': summary or _("Settlement executed according to dispute order."),
            'resolved_at': fields.Datetime.now()
        })

        # Unlock escrow
        alloc = self.escrow_allocation_id
        account = alloc.escrow_account_id

        alloc.write({'state': 'released' if payout_dec > 0 else 'allocated'})
        account.write({'state': 'funded', 'lock_reason': False})

        # Emit DISPUTE_RESOLVED
        if 'vin.audit.event' in self.env:
            self.env['vin.audit.event'].sudo().create({
                'tenant_id': self.tenant_id.id,
                'actor_user_id': self.env.user.id,
                'event_type': 'DISPUTE_RESOLVED',
                'entity_name': 'vin.dispute',
                'entity_id': str(self.id),
                'state_after': 'resolved',
                'payload': json.dumps({
                    'dispute_number': self.dispute_number,
                    'resolution_type': resolution_type,
                    'client_refund': float(refund_dec),
                    'partner_payout': float(payout_dec),
                    'total_disputed': float(total_disputed)
                })
            })

        self.message_post(body=_(
            "Dispute resolved via %s. Client Refund: %s, Partner Payout: %s. Escrow unlocked."
        ) % (resolution_type, refund_dec, payout_dec))

    def action_withdraw(self, reason=None):
        for rec in self:
            rec.escrow_allocation_id.write({'state': 'allocated'})
            rec.escrow_allocation_id.escrow_account_id.write({'state': 'funded', 'lock_reason': False})
            rec.write({'state': 'withdrawn'})
            rec.message_post(body=_("Dispute withdrawn. Escrow freeze lifted. Reason: %s") % (reason or "Not specified"))
