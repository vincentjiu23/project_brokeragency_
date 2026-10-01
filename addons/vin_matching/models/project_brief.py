# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinProjectBrief(models.Model):
    _name = 'vin.project.brief'
    _description = 'VIN Project Brief & RFQ'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'version_no desc, create_date desc'

    uuid = fields.Char(
        string='Brief UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    title = fields.Char(
        string='Project Brief Title',
        required=True,
        tracking=True
    )
    version_no = fields.Integer(
        string='Version Number',
        default=1,
        readonly=True,
        index=True
    )
    parent_brief_id = fields.Many2one(
        'vin.project.brief',
        string='Parent Version Lineage',
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
    master_project_id = fields.Many2one(
        'vin.master.project',
        string='Master Project',
        index=True
    )
    target_account_type = fields.Selection(
        [
            ('agency', 'Creative Agency / Studio'),
            ('individual', 'Individual Creative Professional'),
            ('both', 'Any Creative Partner')
        ],
        string='Target Partner Tier',
        required=True,
        default='both',
        index=True
    )
    required_expertise_ids = fields.Many2many(
        'vin.partner.expertise',
        'vin_brief_expertise_rel',
        'brief_id',
        'expertise_id',
        string='Required Creative Skills & Disciplines'
    )
    budget_min = fields.Monetary(
        string='Minimum Budget',
        currency_field='currency_id',
        required=True
    )
    budget_max = fields.Monetary(
        string='Maximum Budget',
        currency_field='currency_id',
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    delivery_deadline = fields.Date(
        string='Target Delivery Deadline',
        required=True
    )
    scope_summary = fields.Text(
        string='Creative Scope & Challenge',
        required=True
    )
    anonymity_mode = fields.Selection(
        [
            ('blind', 'Blind RFQ (Client Identity Hidden Until Bilateral Interest)'),
            ('disclosed', 'Disclosed Client Identity')
        ],
        string='Anonymity Mode',
        required=True,
        default='blind',
        help="Locked Architecture Rule: Blind introduction protects client confidential projects during discovery."
    )
    state = fields.Selection(
        [
            ('draft', 'Draft Brief'),
            ('submitted', 'Submitted & Sealed'),
            ('matched', 'Candidates Screened & Matched'),
            ('shortlisted', 'Shortlist Dispatched'),
            ('contracted', 'Contracted / Assigned'),
            ('cancelled', 'Cancelled')
        ],
        string='Brief Lifecycle State',
        required=True,
        default='draft',
        tracking=True,
        index=True
    )
    immutable_hash = fields.Char(
        string='Brief Canonical SHA-256 Hash',
        size=64,
        readonly=True,
        index=True
    )
    match_snapshot_ids = fields.One2many(
        'vin.match.snapshot',
        'brief_id',
        string='Matching Snapshots',
        readonly=True
    )
    opportunity_ids = fields.One2many(
        'vin.opportunity.record',
        'brief_id',
        string='Dispatched Opportunities',
        readonly=True
    )

    @api.constrains('budget_min', 'budget_max')
    def _check_budget(self):
        for record in self:
            if record.budget_min < 0 or record.budget_max < 0:
                raise ValidationError(_("Budget amounts cannot be negative!"))
            if record.budget_min > record.budget_max:
                raise ValidationError(_("Minimum budget cannot exceed maximum budget!"))

    def _compute_canonical_hash(self):
        """Computes SHA-256 hash sealing the brief contents."""
        self.ensure_one()
        payload = {
            'uuid': self.uuid,
            'title': self.title,
            'version_no': self.version_no,
            'tenant_id': self.tenant_id.uuid if self.tenant_id else None,
            'client_org': self.client_organization_id.uuid if self.client_organization_id else None,
            'target_account_type': self.target_account_type,
            'budget_min': float(self.budget_min),
            'budget_max': float(self.budget_max),
            'currency': self.currency_id.name,
            'scope_summary': self.scope_summary,
            'required_expertise': sorted([exp.code for exp in self.required_expertise_ids])
        }
        encoded = json.dumps(payload, sort_keys=True).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def action_submit_and_match(self):
        """Submits the brief, seals canonical hash, and triggers deterministic matching engine."""
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft briefs can be submitted for matching!"))
            
            canonical_hash = record._compute_canonical_hash()
            record.write({
                'state': 'submitted',
                'immutable_hash': canonical_hash
            })

            # Record immutable audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='BRIEF_CREATED',
                subject_type='vin.project.brief',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'title': record.title,
                    'version_no': record.version_no,
                    'canonical_hash': canonical_hash,
                    'budget_max': float(record.budget_max)
                }
            )

            # Trigger matching engine service
            from ..services.matching_service import MatchingEngineService
            svc = MatchingEngineService(self.env)
            snapshot = svc.execute_matching(record.id)
            record.write({'state': 'matched'})

        return True

    def create_revision(self, delta_values):
        """Creates next immutable version branch (BRIEF_VN lineage)."""
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(_("Cannot create a revision of a draft brief. Edit the draft directly."))

        new_vals = {
            'title': delta_values.get('title', self.title),
            'version_no': self.version_no + 1,
            'parent_brief_id': self.id,
            'tenant_id': self.tenant_id.id,
            'client_organization_id': self.client_organization_id.id,
            'master_project_id': self.master_project_id.id if self.master_project_id else False,
            'target_account_type': delta_values.get('target_account_type', self.target_account_type),
            'budget_min': delta_values.get('budget_min', self.budget_min),
            'budget_max': delta_values.get('budget_max', self.budget_max),
            'currency_id': delta_values.get('currency_id', self.currency_id.id),
            'delivery_deadline': delta_values.get('delivery_deadline', self.delivery_deadline),
            'scope_summary': delta_values.get('scope_summary', self.scope_summary),
            'anonymity_mode': delta_values.get('anonymity_mode', self.anonymity_mode),
            'state': 'draft',
            'required_expertise_ids': [(6, 0, delta_values.get('required_expertise_ids', self.required_expertise_ids.ids))]
        }
        new_brief = self.create(new_vals)
        return new_brief
