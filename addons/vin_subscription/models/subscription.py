# -*- coding: utf-8 -*-
import json
import uuid
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class VinSubscription(models.Model):
    """
    Active Organization & Partner Subscription Model (Q99–Q105, Q180).
    Manages subscription lifecycle, plan upgrades, auto-renewal schedules,
    and event emissions for tier updates.
    """
    _name = 'vin.subscription'
    _description = 'VIN Organization Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'current_period_end desc, id desc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    subscription_number = fields.Char(string='Subscription Number', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', required=True, index=True, default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False)

    client_organization_id = fields.Many2one('vin.organization', string='Client Organization', index=True, tracking=True)
    partner_profile_id = fields.Many2one('creative.partner.profile', string='Creative Partner Profile', index=True, tracking=True)

    plan_id = fields.Many2one('vin.subscription.plan', string='Subscription Plan', required=True, tracking=True)
    currency = fields.Char(string='Currency', related='plan_id.currency', store=True)
    price = fields.Float(string='Price', related='plan_id.price', store=True)

    start_date = fields.Date(string='Initial Start Date', default=fields.Date.context_today, required=True)
    current_period_start = fields.Date(string='Current Period Start', default=fields.Date.context_today, required=True)
    current_period_end = fields.Date(string='Current Period End', compute='_compute_period_end', store=True, readonly=False)

    state = fields.Selection([
        ('trial', 'Trial Period'),
        ('active', 'Active'),
        ('past_due', 'Past Due / Grace Period'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired')
    ], string='Status', default='active', required=True, tracking=True)

    auto_renew = fields.Boolean(string='Auto Renew', default=True, tracking=True)
    cancellation_reason = fields.Text(string='Cancellation Reason')
    cancelled_at = fields.Datetime(string='Cancelled At', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('subscription_number', _('New')) == _('New'):
                vals['subscription_number'] = f"SUB-{uuid.uuid4().hex[:8].upper()}"
        return super().create(vals_list)

    @api.depends('current_period_start', 'plan_id.billing_interval')
    def _compute_period_end(self):
        for rec in self:
            if rec.current_period_start and rec.plan_id:
                days = 365 if rec.plan_id.billing_interval == 'annual' else 30
                rec.current_period_end = rec.current_period_start + timedelta(days=days)
            elif not rec.current_period_end:
                rec.current_period_end = fields.Date.today() + timedelta(days=30)

    def action_activate(self):
        for rec in self:
            rec.write({'state': 'active'})
            rec.message_post(body=_("Subscription activated under plan %s.") % rec.plan_id.name)

    def action_renew(self):
        for rec in self:
            days = 365 if rec.plan_id.billing_interval == 'annual' else 30
            new_start = rec.current_period_end or fields.Date.today()
            new_end = new_start + timedelta(days=days)
            rec.write({
                'current_period_start': new_start,
                'current_period_end': new_end,
                'state': 'active'
            })
            rec.message_post(body=_("Subscription successfully renewed through %s.") % new_end)

    def action_upgrade_plan(self, new_plan_id):
        self.ensure_one()
        new_plan = self.env['vin.subscription.plan'].browse(new_plan_id)
        if not new_plan.exists():
            raise UserError(_("Selected subscription plan does not exist."))
        old_plan_name = self.plan_id.name
        self.write({
            'plan_id': new_plan.id,
            'state': 'active'
        })

        # Emit audit event for plan upgrade
        if 'vin.audit.event' in self.env:
            self.env['vin.audit.event'].sudo().create({
                'tenant_id': self.tenant_id.id,
                'actor_user_id': self.env.user.id,
                'event_type': 'SUBSCRIPTION_UPGRADED',
                'entity_name': 'vin.subscription',
                'entity_id': str(self.id),
                'state_before': old_plan_name,
                'state_after': new_plan.name,
                'payload': json.dumps({
                    'subscription_number': self.subscription_number,
                    'old_plan': old_plan_name,
                    'new_plan': new_plan.name,
                    'take_rate_discount': new_plan.take_rate_commission_discount
                })
            })
        self.message_post(body=_("Plan upgraded from %s to %s.") % (old_plan_name, new_plan.name))

    def action_cancel(self, reason=None):
        for rec in self:
            rec.write({
                'state': 'cancelled',
                'auto_renew': False,
                'cancellation_reason': reason or _("Cancelled by subscriber"),
                'cancelled_at': fields.Datetime.now()
            })
            rec.message_post(body=_("Subscription cancelled. Reason: %s") % (reason or "Not specified"))
