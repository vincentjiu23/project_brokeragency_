# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinGovernanceOverride(models.Model):
    _name = 'vin.governance.override'
    _description = 'VIN Controlled Human Override & Four-Eyes Governance Protocol'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    uuid = fields.Char(
        string='Override UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    override_domain = fields.Selection(
        [
            ('financial', 'Financial Ledger / Escrow Adjustment'),
            ('legal', 'Contractual Term / Approval Invalidation Override'),
            ('security', 'Emergency Access / Break-Glass'),
            ('dispute', 'Dispute Resolution Overrule')
        ],
        string='Governance Domain',
        required=True,
        index=True
    )
    requested_by_id = fields.Many2one(
        'res.users',
        string='Requester',
        required=True,
        default=lambda self: self.env.user,
        readonly=True
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approver (Four-Eyes Gate)',
        readonly=True,
        tracking=True
    )
    state = fields.Selection(
        [
            ('draft', 'Requested'),
            ('approved', 'Approved & Active'),
            ('rejected', 'Rejected'),
            ('expired', 'Expired'),
            ('rolled_back', 'Rolled Back')
        ],
        string='Override Status',
        required=True,
        default='draft',
        tracking=True,
        index=True
    )
    legal_evidence_ref = fields.Char(
        string='Legal / Evidence Payload Reference',
        required=True,
        help="Asset Vault SHA-256 reference or official signed documentation."
    )
    justification = fields.Text(
        string='Detailed Justification',
        required=True
    )
    expiry_timestamp = fields.Datetime(
        string='Override Expiry (UTC)',
        required=True
    )
    rollback_instructions = fields.Text(
        string='Deterministic Rollback Instructions',
        required=True
    )

    def action_approve_override(self):
        """Four-Eyes Enforcement: Requester can never approve their own override."""
        for record in self:
            current_user = self.env.user
            if record.requested_by_id.id == current_user.id:
                raise UserError(_(
                    "Segregation of Duties (SoD) Violation: "
                    "The requester of an override is strictly forbidden from approving it (Four-Eyes Principle)!"
                ))

            record.write({
                'approved_by_id': current_user.id,
                'state': 'approved'
            })

            # Append immutable audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='GOVERNANCE_OVERRIDE_APPROVED',
                subject_type='vin.governance.override',
                subject_id=record.uuid,
                payload={
                    'domain': record.override_domain,
                    'requester_id': str(record.requested_by_id.id),
                    'approver_id': str(current_user.id),
                    'expiry': str(record.expiry_timestamp)
                }
            )

    def action_rollback(self):
        """Executes rollback of the human override."""
        for record in self:
            if record.state != 'approved':
                raise UserError(_("Only active approved overrides can be rolled back."))

            record.write({'state': 'rolled_back'})
            self.env['vin.audit.event'].sudo().record_event(
                action='GOVERNANCE_OVERRIDE_ROLLED_BACK',
                subject_type='vin.governance.override',
                subject_id=record.uuid,
                payload={'rolled_back_by': str(self.env.user.id)}
            )
