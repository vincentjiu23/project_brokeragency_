# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinPortfolioDisplayGrant(models.Model):
    """
    Portfolio Showcase Display Grant Policy Gate (Q137–Q146).
    Enforces confidentiality, NDA embargo periods, and client authorization
    before creative work can be showcased in partner portfolios.
    """
    _name = 'vin.portfolio.display.grant'
    _description = 'VIN Portfolio Display Grant'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', required=True, index=True, default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False)

    partner_profile_id = fields.Many2one('creative.partner.profile', string='Creative Partner', required=True, index=True)
    contract_id = fields.Many2one('vin.contract', string='Contract Reference', required=True, index=True)
    deliverable_id = fields.Many2one('vin.deliverable', string='Deliverable Asset', index=True)

    client_organization_id = fields.Many2one('vin.organization', string='Client Organization', related='contract_id.client_organization_id', store=True)

    status = fields.Selection([
        ('pending', 'Pending Client Review'),
        ('approved', 'Approved for Public Portfolio'),
        ('embargoed', 'Approved Subject to Launch Embargo'),
        ('rejected_nda', 'Restricted / Strict NDA (Private Only)')
    ], string='Showcase Authorization Status', default='pending', required=True, tracking=True)

    embargo_date = fields.Date(string='Public Release / Embargo Lift Date')
    client_notes = fields.Text(string='Client Guidelines / Restrictions')
    reviewed_at = fields.Datetime(string='Reviewed At', readonly=True)

    def action_approve(self):
        for rec in self:
            rec.write({
                'status': 'approved',
                'reviewed_at': fields.Datetime.now()
            })
            rec.message_post(body=_("Portfolio display approved by client organization."))

    def action_embargo(self, lift_date):
        for rec in self:
            rec.write({
                'status': 'embargoed',
                'embargo_date': lift_date,
                'reviewed_at': fields.Datetime.now()
            })
            rec.message_post(body=_("Portfolio display embargoed until %s.") % lift_date)

    def action_reject_nda(self, reason=None):
        for rec in self:
            rec.write({
                'status': 'rejected_nda',
                'client_notes': reason or _("Strict NDA: Work cannot be displayed publicly."),
                'reviewed_at': fields.Datetime.now()
            })
            rec.message_post(body=_("Portfolio display rejected under NDA restrictions."))
