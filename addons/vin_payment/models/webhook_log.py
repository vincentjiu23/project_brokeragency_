# -*- coding: utf-8 -*-
import hashlib
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VinWebhookLog(models.Model):
    """
    Immutable webhook event log.
    
    Records every incoming webhook payload for idempotent processing,
    replay capability, and forensic audit. Each webhook is deduplicated
    by its provider-assigned event ID.
    
    Locked Architecture Decision (ADR-002): Webhook logs are append-only.
    """
    _name = 'vin.webhook.log'
    _description = 'VIN Immutable Webhook Event Log'
    _order = 'received_at desc, id desc'

    uuid = fields.Char(
        string='Webhook Log UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        readonly=True,
        index=True
    )
    provider_code = fields.Selection(
        [
            ('stripe', 'Stripe'),
            ('xendit', 'Xendit'),
            ('midtrans', 'Midtrans'),
            ('wise', 'Wise'),
            ('paypal', 'PayPal'),
            ('manual', 'Manual'),
        ],
        string='Provider Code',
        required=True,
        readonly=True,
        index=True
    )
    provider_event_id = fields.Char(
        string='Provider Event ID',
        required=True,
        readonly=True,
        index=True,
        help="Provider-assigned unique event ID for idempotent deduplication."
    )
    event_type = fields.Char(
        string='Provider Event Type',
        readonly=True,
        index=True,
        help="e.g., 'payment_intent.succeeded', 'invoice.paid', etc."
    )
    raw_payload = fields.Text(
        string='Raw Webhook Payload (JSON)',
        required=True,
        readonly=True,
        help="Verbatim JSON body received from provider."
    )
    payload_hash = fields.Char(
        string='Payload SHA-256 Hash',
        size=64,
        readonly=True,
        index=True,
        help="Content-addressed hash for integrity verification."
    )
    signature_header = fields.Char(
        string='Signature Header Value',
        readonly=True,
        help="Raw signature header for signature verification audit."
    )
    signature_verified = fields.Boolean(
        string='Signature Verified',
        readonly=True,
        default=False
    )
    received_at = fields.Datetime(
        string='Received Timestamp (UTC)',
        required=True,
        readonly=True,
        default=fields.Datetime.now
    )
    processing_state = fields.Selection(
        [
            ('pending', 'Pending Processing'),
            ('processed', 'Successfully Processed'),
            ('duplicate', 'Duplicate (Idempotent Skip)'),
            ('invalid_signature', 'Invalid Signature — Rejected'),
            ('processing_error', 'Processing Error'),
            ('ignored', 'Ignored (Unhandled Event Type)')
        ],
        string='Processing State',
        required=True,
        default='pending',
        readonly=True,
        index=True
    )
    processing_error = fields.Text(
        string='Processing Error Details',
        readonly=True
    )
    payout_id = fields.Many2one(
        'vin.payout',
        string='Linked Payout Record',
        readonly=True,
        index=True
    )
    http_status_code = fields.Integer(
        string='Response HTTP Status',
        readonly=True
    )
    ip_address = fields.Char(
        string='Source IP Address',
        readonly=True,
        help="IP address of the webhook sender for security audit."
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Computes payload hash on creation."""
        for vals in vals_list:
            if vals.get('raw_payload') and not vals.get('payload_hash'):
                vals['payload_hash'] = hashlib.sha256(
                    vals['raw_payload'].encode('utf-8')
                ).hexdigest()
        return super().create(vals_list)

    def write(self, vals):
        """Locked Architecture: Webhook logs allow only processing_state updates."""
        allowed_fields = {'processing_state', 'processing_error', 'payout_id', 'http_status_code'}
        if not set(vals.keys()).issubset(allowed_fields):
            raise UserError(_(
                "Security Violation: Webhook log records are append-only. "
                "Only processing state updates are permitted."
            ))
        return super().write(vals)

    def unlink(self):
        """Locked Architecture Decision: Webhook logs cannot be deleted."""
        raise UserError(_("Security Violation: Webhook logs cannot be deleted!"))

    @api.model
    def is_duplicate(self, provider_code, provider_event_id):
        """Checks if a webhook with this provider event ID has already been processed."""
        existing = self.search([
            ('provider_code', '=', provider_code),
            ('provider_event_id', '=', provider_event_id),
            ('processing_state', 'in', ['processed', 'duplicate'])
        ], limit=1)
        return bool(existing)
