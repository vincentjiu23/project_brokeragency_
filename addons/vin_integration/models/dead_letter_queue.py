# -*- coding: utf-8 -*-
"""
Dead Letter Queue (DLQ) Model (Q137–Q146, AC-06/07 Integration Domain).
Isolates and queues poisoned, timed-out, or failed integration payloads
for safe inspection, manual review, or idempotent replay.
"""
import uuid
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class VinDLQMessage(models.Model):
    """
    Dead-Letter Queue (DLQ) Message Record.
    Captures outbound dispatch failures and incoming webhook ingest errors.
    """
    _name = 'vin.dlq.message'
    _description = 'VIN Dead-Letter Queue (DLQ) Message'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    message_reference = fields.Char(
        string='DLQ Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )

    endpoint_id = fields.Many2one(
        'vin.integration.endpoint', string='Target Endpoint',
        index=True, required=True
    )
    direction = fields.Selection([
        ('outbound', 'Outbound Integration Dispatch'),
        ('inbound', 'Inbound Webhook Receipt'),
    ], string='Direction', default='outbound', required=True, index=True)

    event_type = fields.Char(string='Domain Event / Action Type', required=True, index=True)
    idempotency_key = fields.Char(
        string='Idempotency Key', index=True, required=True,
        help="Enforces AC-06 deduplication during re-execution."
    )

    # ── Payload Data ──
    payload = fields.Text(string='Raw JSON Payload', required=True)
    headers = fields.Text(string='HTTP Headers / Metadata')
    error_diagnostic = fields.Text(string='Failure Diagnostic / Stack Trace')

    # ── Retry Execution ──
    retry_count = fields.Integer(string='Retry Count', default=0, readonly=True)
    max_retries = fields.Integer(string='Max Retry Limit', default=3, required=True)
    state = fields.Selection([
        ('pending', 'Pending Review / Retry'),
        ('replaying', 'Currently Replaying'),
        ('resolved', 'Successfully Resolved'),
        ('exhausted', 'Retry Limit Exhausted'),
        ('discarded', 'Discarded by Operator'),
    ], string='DLQ State', default='pending', required=True, tracking=True)

    first_attempt_at = fields.Datetime(string='First Attempt At', default=fields.Datetime.now, readonly=True)
    last_attempt_at = fields.Datetime(string='Last Attempt At', readonly=True)
    resolved_at = fields.Datetime(string='Resolved At', readonly=True)
    resolved_by_user_id = fields.Many2one('res.users', string='Resolved By User', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('message_reference', _('New')) == _('New'):
                vals['message_reference'] = f"DLQ-{uuid.uuid4().hex[:8].upper()}"
        return super().create(vals_list)

    def action_replay(self):
        """
        Triggers safe replay of the message.
        Calls resilience gateway to re-dispatch payload using original idempotency key (AC-06).
        """
        for rec in self:
            if rec.state == 'resolved':
                raise UserError(_("Message has already been successfully resolved."))

            rec.write({'state': 'replaying'})

            # Check if circuit is open
            if not rec.endpoint_id.can_execute():
                rec.write({'state': 'pending'})
                raise UserError(_(
                    "Cannot replay: Target endpoint '%s' circuit breaker is currently OPEN."
                ) % rec.endpoint_id.name)

            # Record replay attempt
            now = fields.Datetime.now()
            new_retries = rec.retry_count + 1

            # Execute replay via service
            Gateway = self.env['vin.resilience.gateway']
            success, error_msg = Gateway.dispatch_payload(
                endpoint=rec.endpoint_id,
                event_type=rec.event_type,
                idempotency_key=rec.idempotency_key,
                payload_str=rec.payload
            )

            if success:
                rec.write({
                    'state': 'resolved',
                    'retry_count': new_retries,
                    'last_attempt_at': now,
                    'resolved_at': now,
                    'resolved_by_user_id': self.env.user.id,
                })
                rec.message_post(body=_("DLQ message successfully replayed and delivered."))
            else:
                new_state = 'exhausted' if new_retries >= rec.max_retries else 'pending'
                rec.write({
                    'state': new_state,
                    'retry_count': new_retries,
                    'last_attempt_at': now,
                    'error_diagnostic': error_msg,
                })
                rec.message_post(body=_(
                    "Replay attempt %d failed. Error: %s"
                ) % (new_retries, error_msg))

    def action_discard(self, reason=None):
        """Discards dead-letter message without replay."""
        for rec in self:
            rec.write({
                'state': 'discarded',
                'resolved_at': fields.Datetime.now(),
                'resolved_by_user_id': self.env.user.id,
            })
            rec.message_post(body=_("DLQ message manually discarded by operator. Reason: %s") % (reason or "Obsolete"))
