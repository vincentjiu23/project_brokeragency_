# -*- coding: utf-8 -*-
"""
Legal Hold Lock Model (Q137–Q146, Q250, AC-08/09/10 Compliance Domain).
Enforces mandatory litigation/regulatory hold on records, preventing automated
or manual disposal, cold storage purge, or DSAR erasure during legal proceedings.
"""
import uuid
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class VinLegalHold(models.Model):
    """
    Legal Hold Lock Case.
    When active, blocks all retention disposal, archival purging, and DSAR erasure
    across all scoped entities (contracts, projects, organizations, deliverables).
    """
    _name = 'vin.legal.hold'
    _description = 'VIN Legal Hold Lock Case'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'applied_at desc, id desc'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    hold_reference = fields.Char(
        string='Hold Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )

    title = fields.Char(string='Matter Title', required=True, tracking=True)
    matter_name = fields.Char(string='Matter / Action Name', required=True)
    docket_number = fields.Char(string='Court Docket / Case Ref', tracking=True)
    issuing_authority = fields.Char(
        string='Issuing Court / Regulatory Body',
        help="Court, arbitration body (BANI/SIAC), or government tax/data authority."
    )

    # ── Target Scopes ──
    scope_type = fields.Selection([
        ('contract', 'Specific Contract Lineage'),
        ('project', 'Master Project & All Workstreams'),
        ('organization', 'Client / Agency Organization'),
        ('partner_profile', 'Creative Partner Profile'),
        ('general_inquiry', 'Cross-Entity Regulatory Inquiry'),
    ], string='Hold Scope Type', default='contract', required=True, tracking=True)

    contract_id = fields.Many2one('vin.contract', string='Scoped Contract', index=True)
    project_id = fields.Many2one('vin.master.project', string='Scoped Master Project', index=True)
    organization_id = fields.Many2one('vin.organization', string='Scoped Organization', index=True)
    partner_profile_id = fields.Many2one('creative.partner.profile', string='Scoped Partner', index=True)

    # ── Narrative & Rationale ──
    hold_reason = fields.Text(string='Legal Justification & Notice', required=True)
    preservation_instructions = fields.Text(string='Preservation Instructions for Custodians')

    # ── State & Lifecycle ──
    state = fields.Selection([
        ('draft', 'Draft Case'),
        ('active', 'Active Legal Hold (Records Locked)'),
        ('lifted', 'Lifted / Matter Concluded'),
    ], string='Status', default='draft', required=True, tracking=True)

    applied_by_user_id = fields.Many2one('res.users', string='Applied By Counsel', readonly=True)
    applied_at = fields.Datetime(string='Hold Applied Timestamp', readonly=True)

    lifted_by_user_id = fields.Many2one('res.users', string='Lifted By Counsel', readonly=True)
    lifted_at = fields.Datetime(string='Hold Lifted Timestamp', readonly=True)
    lift_reason = fields.Text(string='Legal Rationale for Lifting Hold')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('hold_reference', _('New')) == _('New'):
                vals['hold_reference'] = f"LH-{fields.Date.today().strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
        return super().create(vals_list)

    def action_apply_hold(self):
        """
        Activates legal hold lock. Scoped records are immediately locked from purge/erasure.
        Emits LEGAL_HOLD_APPLIED audit event.
        """
        for rec in self:
            if rec.state == 'active':
                raise UserError(_("Legal hold is already active."))

            now = fields.Datetime.now()
            rec.write({
                'state': 'active',
                'applied_by_user_id': self.env.user.id,
                'applied_at': now,
            })

            # Emit LEGAL_HOLD_APPLIED audit event
            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'LEGAL_HOLD_APPLIED',
                    'entity_name': 'vin.legal.hold',
                    'entity_id': str(rec.id),
                    'state_after': 'active',
                    'payload': json.dumps({
                        'hold_reference': rec.hold_reference,
                        'scope_type': rec.scope_type,
                        'matter_name': rec.matter_name,
                        'contract_id': rec.contract_id.id if rec.contract_id else None,
                        'project_id': rec.project_id.id if rec.project_id else None,
                        'organization_id': rec.organization_id.id if rec.organization_id else None,
                        'partner_profile_id': rec.partner_profile_id.id if rec.partner_profile_id else None,
                    })
                })

            rec.message_post(body=_(
                "Legal Hold [%s] formally applied by %s. All scoped records locked."
            ) % (rec.hold_reference, self.env.user.name))

    def action_lift_hold(self, reason=None):
        """
        Lifts legal hold lock. Requires formal legal justification.
        Emits LEGAL_HOLD_LIFTED audit event.
        """
        for rec in self:
            if rec.state != 'active':
                raise UserError(_("Only active legal holds can be lifted."))

            rationale = reason or rec.lift_reason
            if not rationale:
                raise UserError(_("A legal justification must be provided to lift a legal hold."))

            now = fields.Datetime.now()
            rec.write({
                'state': 'lifted',
                'lifted_by_user_id': self.env.user.id,
                'lifted_at': now,
                'lift_reason': rationale,
            })

            # Emit LEGAL_HOLD_LIFTED audit event
            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'LEGAL_HOLD_LIFTED',
                    'entity_name': 'vin.legal.hold',
                    'entity_id': str(rec.id),
                    'state_after': 'lifted',
                    'payload': json.dumps({
                        'hold_reference': rec.hold_reference,
                        'lift_reason': rationale,
                    })
                })

            rec.message_post(body=_(
                "Legal Hold [%s] lifted by %s. Reason: %s"
            ) % (rec.hold_reference, self.env.user.name, rationale))

    @api.model
    def check_is_held(self, tenant_id, contract_id=None, project_id=None,
                       organization_id=None, partner_profile_id=None):
        """
        Helper method called by archival and DSAR services to verify if any target record
        is subject to an active legal hold.

        Returns:
            recordset: Active vin.legal.hold records covering the subject, or empty recordset.
        """
        domain = [
            ('tenant_id', '=', tenant_id),
            ('state', '=', 'active'),
        ]
        or_conditions = []
        if contract_id:
            or_conditions.append(('contract_id', '=', contract_id))
        if project_id:
            or_conditions.append(('project_id', '=', project_id))
        if organization_id:
            or_conditions.append(('organization_id', '=', organization_id))
        if partner_profile_id:
            or_conditions.append(('partner_profile_id', '=', partner_profile_id))

        if or_conditions:
            # Build OR clause
            final_domain = domain + ['|'] * (len(or_conditions) - 1) + or_conditions
            return self.search(final_domain)

        return self.env['vin.legal.hold']
