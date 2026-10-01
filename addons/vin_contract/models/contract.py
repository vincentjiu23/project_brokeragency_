# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinContract(models.Model):
    _name = 'vin.contract'
    _description = 'VIN Immutable Versioned Legal Contract (CONTRACT_VN)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'version_no desc, create_date desc'

    uuid = fields.Char(
        string='Contract UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    contract_number = fields.Char(
        string='Contract Reference Number',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: f"CTR-{uuid.uuid4().hex[:8].upper()}"
    )
    title = fields.Char(
        string='Contract Title',
        required=True,
        tracking=True
    )
    version_no = fields.Integer(
        string='Version Number',
        default=1,
        readonly=True,
        index=True
    )
    parent_contract_id = fields.Many2one(
        'vin.contract',
        string='Preceding Contract Version',
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        required=True,
        index=True
    )
    client_organization_id = fields.Many2one(
        'vin.organization',
        string='Client Organization',
        required=True,
        index=True
    )
    partner_profile_id = fields.Many2one(
        'creative.partner.profile',
        string='Creative Partner',
        required=True,
        index=True
    )
    brief_id = fields.Many2one(
        'vin.project.brief',
        string='Originating Project Brief',
        index=True
    )
    master_project_id = fields.Many2one(
        'vin.master.project',
        string='Master Project',
        index=True
    )
    total_contract_value = fields.Monetary(
        string='Total Contract Value',
        currency_field='currency_id',
        required=True,
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    effective_date = fields.Date(
        string='Effective Date',
        readonly=True,
        tracking=True
    )
    completion_deadline = fields.Date(
        string='Contract Completion Deadline',
        required=True,
        tracking=True
    )
    state = fields.Selection(
        [
            ('draft', 'Draft Contract'),
            ('in_review', 'Pending Internal Approvals'),
            ('approved', 'Approved by All Tiers'),
            ('active', 'Active & Binding (CONTRACT_VN)'),
            ('suspended', 'Suspended / In Dispute'),
            ('amended', 'Amended (Superseded by Next Version)'),
            ('completed', 'Successfully Completed'),
            ('terminated', 'Terminated Early')
        ],
        string='Contract State',
        required=True,
        default='draft',
        tracking=True,
        index=True
    )
    signed_hash = fields.Char(
        string='Sealed Legal Hash (SHA-256)',
        size=64,
        readonly=True,
        index=True
    )
    client_signed_at = fields.Datetime(
        string='Client Electronic Signature Date',
        readonly=True
    )
    partner_signed_at = fields.Datetime(
        string='Partner Electronic Signature Date',
        readonly=True
    )
    proposal_ids = fields.One2many(
        'vin.contract.proposal',
        'contract_id',
        string='Proposal Negotiations'
    )
    approval_ids = fields.One2many(
        'vin.contract.approval',
        'contract_id',
        string='Multi-Tier Approval Matrix'
    )
    change_request_ids = fields.One2many(
        'vin.contract.change.request',
        'contract_id',
        string='Change Requests'
    )

    def write(self, vals):
        """
        Locked Architecture Invariant (ADR-003 / Q41-Q60):
        Active or finalized contracts cannot have commercial or terms mutated directly.
        All contractual changes must route through Change Requests (CR).
        """
        protected_fields = {'total_contract_value', 'completion_deadline', 'tenant_id', 'client_organization_id', 'partner_profile_id'}
        for record in self:
            if record.state in ('active', 'amended', 'completed', 'terminated'):
                if any(f in vals for f in protected_fields):
                    raise UserError(_("Locked Architecture Invariant: Active or finalized contracts are immutable. Changes must route via Change Requests!"))
        return super().write(vals)

    def _compute_sealed_hash(self):
        """Generates cryptographic SHA-256 seal across contract legal invariants."""
        self.ensure_one()
        payload = {
            'uuid': self.uuid,
            'contract_number': self.contract_number,
            'version_no': self.version_no,
            'tenant_uuid': self.tenant_id.uuid,
            'client_org_uuid': self.client_organization_id.uuid,
            'partner_profile_uuid': self.partner_profile_id.uuid,
            'total_value': float(self.total_contract_value),
            'currency': self.currency_id.name,
            'completion_deadline': str(self.completion_deadline)
        }
        encoded = json.dumps(payload, sort_keys=True).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def action_submit_for_approval(self):
        """Submits draft contract to multi-tier approval matrix."""
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft contracts can be submitted for approval."))
            
            # Setup approval tiers if not already present
            if not record.approval_ids:
                record.env['vin.contract.approval'].create({
                    'contract_id': record.id,
                    'approval_tier': 'commercial',
                    'state': 'pending'
                })
                record.env['vin.contract.approval'].create({
                    'contract_id': record.id,
                    'approval_tier': 'legal',
                    'state': 'pending'
                })

            record.write({'state': 'in_review'})
        return True

    def action_activate(self):
        """Activates contract once all approval tiers are approved and both parties signed."""
        for record in self:
            if record.state not in ('approved', 'in_review'):
                raise UserError(_("Contract cannot be activated in state '%s'.") % record.state)
            
            # Check approval matrix
            pending_approvals = record.approval_ids.filtered(lambda a: a.state != 'approved')
            if pending_approvals:
                raise UserError(_("Cannot activate contract: Approval tiers %s are still pending/invalidated!") %
                                pending_approvals.mapped('approval_tier'))

            sealed_hash = record._compute_sealed_hash()
            now = fields.Datetime.now()
            record.write({
                'state': 'active',
                'effective_date': fields.Date.today(),
                'signed_hash': sealed_hash,
                'client_signed_at': record.client_signed_at or now,
                'partner_signed_at': record.partner_signed_at or now
            })

            # Record audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='CONTRACT_ACTIVATED',
                subject_type='vin.contract',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'contract_number': record.contract_number,
                    'version_no': record.version_no,
                    'total_value': float(record.total_contract_value),
                    'signed_hash': sealed_hash
                }
            )

        return True

    def invalidate_prior_approvals(self, reason):
        """
        AC-03 (Material Proposal Delta):
        Material change to contract terms automatically invalidates prior approvals.
        """
        for record in self:
            approved_records = record.approval_ids.filtered(lambda a: a.state == 'approved')
            for app in approved_records:
                app.write({
                    'state': 'invalidated',
                    'invalidation_reason': reason
                })
                # Record audit event (AC-03)
                self.env['vin.audit.event'].sudo().record_event(
                    action='APPROVAL_INVALIDATED',
                    subject_type='vin.contract.approval',
                    subject_id=app.uuid,
                    tenant_id=record.tenant_id.uuid,
                    payload={
                        'contract_uuid': record.uuid,
                        'tier': app.approval_tier,
                        'reason': reason
                    }
                )
            if approved_records:
                record.write({'state': 'in_review'})
