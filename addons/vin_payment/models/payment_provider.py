# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VinPaymentProvider(models.Model):
    _name = 'vin.payment.provider'
    _description = 'VIN Payment Provider Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    uuid = fields.Char(
        string='Provider UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    name = fields.Char(
        string='Provider Name',
        required=True,
        tracking=True
    )
    code = fields.Selection(
        [
            ('stripe', 'Stripe'),
            ('xendit', 'Xendit'),
            ('midtrans', 'Midtrans'),
            ('wise', 'Wise (TransferWise)'),
            ('paypal', 'PayPal'),
            ('manual', 'Manual / Bank Transfer'),
        ],
        string='Provider Code',
        required=True,
        tracking=True,
        index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        required=True,
        index=True,
        ondelete='restrict'
    )
    state = fields.Selection(
        [
            ('draft', 'Configuration Draft'),
            ('test', 'Test / Sandbox Mode'),
            ('live', 'Live / Production'),
            ('disabled', 'Disabled')
        ],
        string='Provider State',
        required=True,
        default='draft',
        tracking=True,
        index=True
    )
    sequence = fields.Integer(
        string='Priority Sequence',
        default=10,
        help="Lower = higher priority when multiple providers available."
    )

    # --- Credential Storage (Encrypted at DB / KMS layer) ---
    api_key_ref = fields.Char(
        string='API Key Reference (KMS Vault)',
        help="Reference to KMS-stored API key. NEVER store raw credentials in DB.",
        groups='base.group_system'
    )
    api_secret_ref = fields.Char(
        string='API Secret Reference (KMS Vault)',
        help="Reference to KMS-stored API secret.",
        groups='base.group_system'
    )
    webhook_secret_ref = fields.Char(
        string='Webhook Signing Secret Reference (KMS)',
        help="Reference to KMS-stored webhook signing secret for signature verification.",
        groups='base.group_system'
    )
    sandbox_api_key_ref = fields.Char(
        string='Sandbox API Key Reference (KMS)',
        groups='base.group_system'
    )
    sandbox_api_secret_ref = fields.Char(
        string='Sandbox API Secret Reference (KMS)',
        groups='base.group_system'
    )

    # --- Capabilities ---
    supported_currency_ids = fields.Many2many(
        'res.currency',
        'vin_payment_provider_currency_rel',
        'provider_id',
        'currency_id',
        string='Supported Currencies'
    )
    supports_refund = fields.Boolean(
        string='Supports Programmatic Refund',
        default=True
    )
    supports_partial_refund = fields.Boolean(
        string='Supports Partial Refund',
        default=True
    )
    supports_cross_border = fields.Boolean(
        string='Supports Cross-Border Payout',
        default=False
    )
    max_payout_amount = fields.Float(
        string='Maximum Single Payout Amount (Provider Limit)',
        digits=(16, 2),
        default=0.0,
        help="0 = no limit imposed by provider config."
    )

    # --- Webhook Configuration ---
    webhook_url = fields.Char(
        string='Webhook Callback URL',
        compute='_compute_webhook_url',
        store=False
    )

    def _compute_webhook_url(self):
        """Generates the canonical webhook callback URL for this provider."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for record in self:
            record.webhook_url = f"{base_url}/api/v1/payment/webhook/{record.code}/{record.uuid}"

    def action_activate_live(self):
        """Activates provider for live/production transactions."""
        for record in self:
            if not record.api_key_ref:
                raise UserError(_("Cannot go live without API credentials configured."))
            record.write({'state': 'live'})

    def action_disable(self):
        """Disables provider — no new transactions will use it."""
        self.write({'state': 'disabled'})
