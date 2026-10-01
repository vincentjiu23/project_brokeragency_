# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VinPaymentEvent(models.Model):
    """
    Immutable payment event log.
    
    Every payment state transition (initiated → processing → succeeded / failed / refunded)
    is recorded as an append-only event. This ensures full payment lineage and auditability.
    
    Locked Architecture Decision (ADR-002): Payment events are strictly immutable.
    """
    _name = 'vin.payment.event'
    _description = 'VIN Immutable Payment Event'
    _order = 'timestamp desc, id desc'

    uuid = fields.Char(
        string='Payment Event UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    payment_id = fields.Many2one(
        'vin.payout',
        string='Parent Payout Record',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='payment_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    event_type = fields.Selection(
        [
            ('initiated', 'Payment Initiated'),
            ('submitted', 'Submitted to Provider'),
            ('processing', 'Provider Processing'),
            ('succeeded', 'Payment Succeeded'),
            ('failed', 'Payment Failed'),
            ('cancelled', 'Payment Cancelled'),
            ('refund_initiated', 'Refund Initiated'),
            ('refund_processing', 'Refund Processing'),
            ('refund_succeeded', 'Refund Completed'),
            ('refund_failed', 'Refund Failed'),
        ],
        string='Event Type',
        required=True,
        readonly=True,
        index=True
    )
    timestamp = fields.Datetime(
        string='Event Timestamp (UTC)',
        required=True,
        readonly=True,
        default=fields.Datetime.now
    )
    provider_reference = fields.Char(
        string='Provider Transaction Reference',
        readonly=True,
        index=True,
        help="External provider transaction/charge ID for reconciliation."
    )
    provider_raw_response = fields.Text(
        string='Provider Raw Response (JSON)',
        readonly=True,
        help="Verbatim JSON response from payment provider for audit/debug."
    )
    amount = fields.Monetary(
        string='Event Amount',
        currency_field='currency_id',
        readonly=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True
    )
    failure_code = fields.Char(
        string='Failure / Decline Code',
        readonly=True
    )
    failure_message = fields.Char(
        string='Failure Message',
        readonly=True
    )
    idempotency_key = fields.Char(
        string='Idempotency Key',
        readonly=True,
        index=True,
        help="Provider-level idempotency key to prevent duplicate charges."
    )
    actor_id = fields.Many2one(
        'res.users',
        string='Actor (User)',
        readonly=True,
        default=lambda self: self.env.user.id
    )

    def write(self, vals):
        """Locked Architecture Decision (ADR-002): Payment events are strictly immutable."""
        raise UserError(_("Security Violation: Payment events are append-only and cannot be modified!"))

    def unlink(self):
        """Locked Architecture Decision (ADR-002): Payment events cannot be deleted."""
        raise UserError(_("Security Violation: Payment events cannot be deleted!"))
