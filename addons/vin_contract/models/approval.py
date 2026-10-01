# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinContractApproval(models.Model):
    _name = 'vin.contract.approval'
    _description = 'VIN Multi-Tier Contract Approval'
    _order = 'create_date asc'

    uuid = fields.Char(
        string='Approval UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    contract_id = fields.Many2one(
        'vin.contract',
        string='Contract',
        required=True,
        readonly=True,
        index=True,
        ondelete='cascade'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='contract_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    approver_id = fields.Many2one(
        'res.users',
        string='Assigned Approver',
        index=True
    )
    approval_tier = fields.Selection(
        [
            ('commercial', 'Commercial / Pricing Review'),
            ('legal', 'Legal & Terms Review'),
            ('executive', 'Executive Board Approval')
        ],
        string='Approval Tier',
        required=True,
        index=True
    )
    state = fields.Selection(
        [
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('invalidated', 'Invalidated (Material Change Detected)')
        ],
        string='Approval State',
        required=True,
        default='pending',
        index=True
    )
    invalidation_reason = fields.Char(
        string='Invalidation Reason',
        readonly=True
    )
    approved_at = fields.Datetime(
        string='Approved Timestamp',
        readonly=True
    )

    def action_approve(self):
        """
        Approves tier with strict Four-Eyes Principle / Segregation of Duties (ADR-005).
        """
        for record in self:
            current_user = self.env.user
            # SoD Check: Author/Creator cannot approve
            if current_user.id == record.contract_id.create_uid.id:
                raise UserError(_("SoD / Four-Eyes Violation (ADR-005): Contract creator (%s) cannot approve their own contract!") % current_user.name)

            record.write({
                'state': 'approved',
                'approver_id': current_user.id,
                'approved_at': fields.Datetime.now(),
                'invalidation_reason': False
            })

            # Check if all tiers approved
            all_approved = all(app.state == 'approved' for app in record.contract_id.approval_ids)
            if all_approved:
                record.contract_id.write({'state': 'approved'})

        return True

    def action_reject(self, reason=None):
        """Rejects approval tier."""
        for record in self:
            record.write({
                'state': 'rejected',
                'invalidation_reason': reason or 'Rejected by approver'
            })
            record.contract_id.write({'state': 'draft'})
        return True
