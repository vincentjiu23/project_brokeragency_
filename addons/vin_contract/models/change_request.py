# -*- coding: utf-8 -*-
from datetime import timedelta
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinContractChangeRequest(models.Model):
    _name = 'vin.contract.change.request'
    _description = 'VIN Contract Change Request (CR_VN)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    uuid = fields.Char(
        string='Change Request UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    cr_number = fields.Char(
        string='CR Number',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: f"CR-{uuid.uuid4().hex[:6].upper()}"
    )
    contract_id = fields.Many2one(
        'vin.contract',
        string='Governing Contract',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='contract_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    state = fields.Selection(
        [
            ('draft', 'Draft Change Request'),
            ('review', 'In Bilateral Review'),
            ('approved', 'Approved by Both Parties'),
            ('executed', 'Executed & Contract Version Spawned'),
            ('rejected', 'Rejected')
        ],
        string='CR State',
        required=True,
        default='draft',
        tracking=True,
        index=True
    )
    scope_delta = fields.Text(
        string='Scope Adjustments & Details',
        required=True
    )
    budget_delta = fields.Monetary(
        string='Budget Adjustment (+/-)',
        currency_field='currency_id',
        required=True,
        default=0.0
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='contract_id.currency_id',
        readonly=True
    )
    timeline_delta_days = fields.Integer(
        string='Timeline Adjustment (Days +/-)',
        default=0
    )
    resulting_contract_id = fields.Many2one(
        'vin.contract',
        string='Resulting Contract Version',
        readonly=True
    )

    def action_submit_for_review(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft change requests can be submitted."))
            record.write({'state': 'review'})
        return True

    def action_approve(self):
        for record in self:
            if record.state != 'review':
                raise UserError(_("Only change requests in review can be approved."))
            record.write({'state': 'approved'})
        return True

    def action_execute(self):
        """
        Executes approved change request.
        Spawns next immutable contract version (e.g. v1.0 -> v1.1) and marks prior as amended.
        """
        for record in self:
            if record.state != 'approved':
                raise UserError(_("Only approved change requests can be executed."))

            old_contract = record.contract_id
            new_total = old_contract.total_contract_value + record.budget_delta
            if new_total < 0:
                raise UserError(_("Resulting contract total cannot be negative!"))

            new_deadline = old_contract.completion_deadline + timedelta(days=record.timeline_delta_days)

            # Spawn next contract version
            new_contract = old_contract.create({
                'title': f"{old_contract.title} (Amended v{old_contract.version_no + 1})",
                'version_no': old_contract.version_no + 1,
                'parent_contract_id': old_contract.id,
                'tenant_id': old_contract.tenant_id.id,
                'client_organization_id': old_contract.client_organization_id.id,
                'partner_profile_id': old_contract.partner_profile_id.id,
                'brief_id': old_contract.brief_id.id if old_contract.brief_id else False,
                'master_project_id': old_contract.master_project_id.id if old_contract.master_project_id else False,
                'total_contract_value': new_total,
                'currency_id': old_contract.currency_id.id,
                'completion_deadline': new_deadline,
                'state': 'active',
                'effective_date': fields.Date.today()
            })

            # Mark old contract as amended and CR as executed
            old_contract.write({'state': 'amended'})
            record.write({
                'state': 'executed',
                'resulting_contract_id': new_contract.id
            })

            # Record audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='CONTRACT_AMENDED',
                subject_type='vin.contract',
                subject_id=new_contract.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'cr_number': record.cr_number,
                    'old_contract_uuid': old_contract.uuid,
                    'new_contract_uuid': new_contract.uuid,
                    'new_version_no': new_contract.version_no,
                    'budget_delta': float(record.budget_delta),
                    'timeline_delta_days': record.timeline_delta_days
                }
            )

        return True
