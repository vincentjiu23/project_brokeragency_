# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class VinIPAssignment(models.Model):
    """
    Asset-Level Intellectual Property Assignment Deed (Q137–Q146, Q250, AC-05).
    Enforces automatic copyright transfer, commercial license grants,
    moral rights waivers, and portfolio display policy gates upon milestone acceptance.
    """
    _name = 'vin.ip.assignment'
    _description = 'VIN Intellectual Property Assignment Deed'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'effective_date desc, id desc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    assignment_number = fields.Char(string='Deed Number', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', required=True, index=True, default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False)

    contract_id = fields.Many2one('vin.contract', string='Contract Reference', required=True, index=True, tracking=True)
    milestone_id = fields.Many2one('vin.milestone', string='Milestone Reference', index=True, tracking=True)
    deliverable_id = fields.Many2one('vin.deliverable', string='Deliverable Asset', index=True)

    client_organization_id = fields.Many2one('vin.organization', string='Client Assignee', related='contract_id.client_organization_id', store=True, index=True)
    partner_profile_id = fields.Many2one('creative.partner.profile', string='Partner Assignor', related='contract_id.partner_profile_id', store=True, index=True)

    grant_type = fields.Selection([
        ('exclusive_transfer', 'Full & Exclusive Copyright Assignment (Total Transfer)'),
        ('perpetual_license', 'Perpetual Worldwide Commercial License'),
        ('work_made_for_hire', 'Work Made For Hire (Statutory Assignee)'),
        ('limited_term_license', 'Time / Channel Bound Commercial License')
    ], string='IP Grant Type', default='exclusive_transfer', required=True, tracking=True)

    territory = fields.Selection([
        ('worldwide', 'Worldwide / Global Territory'),
        ('regional', 'Regional / Specific Jurisdictions'),
        ('custom', 'Custom Contractual Boundary')
    ], string='Territory Scope', default='worldwide', required=True)

    moral_rights_waived = fields.Boolean(
        string='Moral Rights Formally Waived',
        default=True,
        help="Assignor waives right of paternity/integrity to the maximum extent permitted by applicable law."
    )

    portfolio_display_permitted = fields.Boolean(
        string='Partner Portfolio Showcase Permitted',
        default=True,
        tracking=True,
        help="Permits partner agency/freelancer to display asset in portfolio, subject to confidentiality embargo."
    )
    portfolio_embargo_date = fields.Date(
        string='Portfolio Embargo Lift Date',
        help="Display blocked until product public release / commercial launch date."
    )

    third_party_materials_disclosed = fields.Boolean(string='Contains Licensed 3rd-Party Materials', default=False)
    third_party_license_details = fields.Text(string='Disclosed 3rd-Party Licenses & Font/Stock Credits')

    effective_date = fields.Date(string='Effective Date', default=fields.Date.context_today, required=True)
    state = fields.Selection([
        ('pending_payment', 'Pending Milestone Acceptance & Escrow Release'),
        ('assigned', 'Legally Assigned & Transferred to Client'),
        ('revoked', 'Revoked / Default on Payment')
    ], string='Assignment Status', default='pending_payment', required=True, tracking=True)

    sha256_hash = fields.Char(string='Deed SHA-256 Digital Seal', readonly=True, copy=False)
    assigned_at = fields.Datetime(string='Executed At', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('assignment_number', _('New')) == _('New'):
                vals['assignment_number'] = f"IP-DEED-{uuid.uuid4().hex[:8].upper()}"
        return super().create(vals_list)

    def action_execute_assignment(self):
        """
        Executes formal assignment transfer (AC-05).
        Generates SHA-256 digital deed hash and logs IP_ASSIGNED audit event.
        """
        for rec in self:
            if rec.state == 'assigned':
                raise UserError(_("IP rights deed has already been executed."))

            # Construct immutable deed payload for hashing
            payload = {
                'uuid': rec.uuid,
                'deed_no': rec.assignment_number,
                'tenant_id': rec.tenant_id.id,
                'contract_id': rec.contract_id.id,
                'milestone_id': rec.milestone_id.id if rec.milestone_id else None,
                'grant_type': rec.grant_type,
                'territory': rec.territory,
                'assignor_partner': rec.partner_profile_id.id,
                'assignee_client': rec.client_organization_id.id,
                'moral_rights_waived': rec.moral_rights_waived,
                'portfolio_display': rec.portfolio_display_permitted,
                'effective_date': str(rec.effective_date)
            }
            raw = json.dumps(payload, sort_keys=True)
            digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()

            rec.write({
                'state': 'assigned',
                'sha256_hash': digest,
                'assigned_at': fields.Datetime.now()
            })

            # Emit IP_ASSIGNED audit event
            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'IP_ASSIGNED',
                    'entity_name': 'vin.ip.assignment',
                    'entity_id': str(rec.id),
                    'state_after': 'assigned',
                    'payload': json.dumps({
                        'assignment_number': rec.assignment_number,
                        'grant_type': rec.grant_type,
                        'sha256_seal': digest
                    })
                })

            rec.message_post(body=_("Intellectual Property rights deed legally executed. SHA-256 Seal: %s") % digest)

    def action_revoke(self, reason=None):
        for rec in self:
            rec.write({'state': 'revoked'})
            rec.message_post(body=_("IP Assignment revoked. Reason: %s") % (reason or "Breach or chargeback"))
