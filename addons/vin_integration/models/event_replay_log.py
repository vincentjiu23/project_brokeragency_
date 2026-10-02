# -*- coding: utf-8 -*-
"""
Event Replay Log Model (Q137–Q146, AC-06/07 Integration Domain).
Maintains append-only audit records of all DLQ message replays,
capturing timestamps, operators, idempotency signatures, and responses.
"""
import uuid
from odoo import models, fields, api, _


class VinEventReplayLog(models.Model):
    """
    Event Replay Audit Log.
    Tracks all retry and replay actions executed from the Dead Letter Queue.
    """
    _name = 'vin.event.replay.log'
    _description = 'VIN Event Replay Audit Log'
    _order = 'replayed_at desc, id desc'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )

    dlq_message_id = fields.Many2one('vin.dlq.message', string='DLQ Source Message', required=True, index=True)
    endpoint_id = fields.Many2one('vin.integration.endpoint', string='Target Endpoint', required=True, index=True)
    idempotency_key = fields.Char(string='Idempotency Key', readonly=True, index=True)

    replayed_at = fields.Datetime(string='Replayed At', default=fields.Datetime.now, readonly=True)
    replayed_by_user_id = fields.Many2one('res.users', string='Operator', readonly=True)

    status = fields.Selection([
        ('success', 'Replay Succeeded'),
        ('failure', 'Replay Failed'),
    ], string='Replay Outcome', required=True, readonly=True)

    latency_ms = fields.Integer(string='Roundtrip Latency (ms)', readonly=True)
    response_payload = fields.Text(string='Response Body', readonly=True)
    error_message = fields.Text(string='Error Diagnostics', readonly=True)
