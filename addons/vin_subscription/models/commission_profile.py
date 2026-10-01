# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class VinCommissionRuleProfile(models.Model):
    """
    Commission Rule Profile (Q99–Q105, Q180).
    Configures platform take-rate profiles, volume-tiered commission scales,
    and minimum/maximum commission boundaries.
    """
    _name = 'vin.commission.rule.profile'
    _description = 'VIN Commission Rule Profile'
    _inherit = ['mail.thread']
    _order = 'is_default desc, id desc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    name = fields.Char(string='Profile Name', required=True, tracking=True)
    code = fields.Char(string='Profile Code', required=True, index=True, copy=False)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', required=True, index=True, default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False)

    base_take_rate = fields.Float(string='Base Take-Rate (%)', default=15.0, required=True, tracking=True)
    min_commission_amount = fields.Float(string='Minimum Fee Amount', default=25.0)
    max_commission_cap = fields.Float(string='Maximum Fee Cap', default=10000.0, help='0 for uncapped')

    is_default = fields.Boolean(string='Default Platform Profile', default=False, tracking=True)
    tier_line_ids = fields.One2many('vin.commission.tier.line', 'profile_id', string='Volume Tier Overrides')

    description = fields.Text(string='Description & Business Rationale')

    @api.constrains('base_take_rate')
    def _check_base_take_rate(self):
        for rec in self:
            if rec.base_take_rate < 0.0 or rec.base_take_rate > 50.0:
                raise ValidationError(_("Base take rate must be between 0% and 50%."))


class VinCommissionTierLine(models.Model):
    """Tier Rule within a Commission Profile for Volume-Based Take-Rate Reductions."""
    _name = 'vin.commission.tier.line'
    _description = 'VIN Commission Volume Tier'
    _order = 'min_volume asc, id asc'

    profile_id = fields.Many2one('vin.commission.rule.profile', string='Profile', required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Tier Name', default='Standard Tier')
    min_volume = fields.Float(string='Minimum Contract Volume', default=0.0, required=True)
    max_volume = fields.Float(string='Maximum Contract Volume', default=0.0, help='Set 0 for open-ended top tier.')
    take_rate = fields.Float(string='Tier Take-Rate (%)', required=True, default=15.0)

    @api.constrains('take_rate', 'min_volume', 'max_volume')
    def _check_tier_bounds(self):
        for line in self:
            if line.take_rate < 0.0 or line.take_rate > 50.0:
                raise ValidationError(_("Tier take-rate must be between 0% and 50%."))
            if line.max_volume > 0.0 and line.min_volume >= line.max_volume:
                raise ValidationError(_("Minimum volume must be less than maximum volume."))
