# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class VinSubscriptionPlan(models.Model):
    """
    Subscription Plan (Q99–Q105, Q180).
    Defines tier-based privileges, storage quotas, payout SLA guarantees,
    and platform take-rate discounts for Clients and Creative Partners.
    """
    _name = 'vin.subscription.plan'
    _description = 'VIN Subscription Plan'
    _inherit = ['mail.thread']
    _order = 'price asc, id asc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    name = fields.Char(string='Plan Name', required=True, tracking=True)
    code = fields.Char(string='Plan Code', required=True, index=True, copy=False)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', required=True, index=True, default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False)

    target_type = fields.Selection([
        ('client', 'Client Organization'),
        ('partner', 'Creative Partner Agency/Studio'),
        ('all', 'Universal')
    ], string='Target Audience', default='client', required=True, tracking=True)

    billing_interval = fields.Selection([
        ('monthly', 'Monthly'),
        ('annual', 'Annual (10% Discount)')
    ], string='Billing Cycle', default='monthly', required=True)

    price = fields.Float(string='Subscription Price', default=0.0, required=True, tracking=True)
    currency = fields.Char(string='Currency', default='USD', required=True)

    take_rate_commission_discount = fields.Float(
        string='Take-Rate Discount (%)',
        default=0.0,
        help="Percentage deduction from the standard 15% platform take-rate (e.g. 3.0 gives 12% take-rate)."
    )

    max_active_projects = fields.Integer(string='Max Concurrent Projects', default=10, help='-1 for unlimited')
    vault_storage_gb = fields.Float(string='Asset Vault Storage Quota (GB)', default=100.0)
    payout_sla_hours = fields.Integer(string='Guaranteed Payout SLA (Hours)', default=72)
    dedicated_account_manager = fields.Boolean(string='Dedicated Account Manager', default=False)
    four_eyes_governance_enabled = fields.Boolean(string='Mandatory Four-Eyes Governance', default=True)

    state = fields.Selection([
        ('active', 'Active'),
        ('archived', 'Archived')
    ], string='Status', default='active', required=True, tracking=True)

    description = fields.Text(string='Plan Features & Description')

    @api.constrains('take_rate_commission_discount')
    def _check_discount(self):
        for rec in self:
            if rec.take_rate_commission_discount < 0.0 or rec.take_rate_commission_discount > 15.0:
                raise ValidationError(_("Take-rate discount cannot exceed standard base commission (0% - 15%)."))
