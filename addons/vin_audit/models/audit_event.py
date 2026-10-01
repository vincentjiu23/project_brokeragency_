# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinAuditEvent(models.Model):
    _name = 'vin.audit.event'
    _description = 'VIN Immutable Audit Event'
    _order = 'id desc'

    uuid = fields.Char(
        string='Event UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    tenant_id = fields.Char(
        string='Tenant UUID',
        required=True,
        index=True,
        readonly=True
    )
    actor_id = fields.Char(
        string='Actor ID (User / Service Account)',
        required=True,
        index=True,
        readonly=True
    )
    action = fields.Char(
        string='Action Code',
        required=True,
        index=True,
        readonly=True
    )
    subject_type = fields.Char(
        string='Subject Model / Entity Type',
        required=True,
        index=True,
        readonly=True
    )
    subject_id = fields.Char(
        string='Subject UUID',
        required=True,
        index=True,
        readonly=True
    )
    before_hash = fields.Char(
        string='Before State Hash (SHA-256)',
        size=64,
        readonly=True
    )
    after_hash = fields.Char(
        string='After State Hash (SHA-256)',
        size=64,
        readonly=True
    )
    correlation_id = fields.Char(
        string='Correlation / Trace UUID',
        index=True,
        readonly=True,
        default=lambda self: str(uuid.uuid4())
    )
    timestamp_utc = fields.Datetime(
        string='Event Timestamp (UTC)',
        required=True,
        default=fields.Datetime.now,
        readonly=True
    )
    payload = fields.Text(
        string='Event Payload JSON',
        readonly=True
    )
    previous_hash = fields.Char(
        string='Previous Event Hash in Chain',
        size=64,
        readonly=True
    )
    event_hash = fields.Char(
        string='Event SHA-256 Hash',
        size=64,
        readonly=True,
        index=True
    )

    def write(self, vals):
        """Locked Business Invariant: Audit records are strictly immutable."""
        raise UserError(_("Security Violation: Audit events are append-only and cannot be updated!"))

    def unlink(self):
        """Locked Business Invariant: Audit records cannot be deleted."""
        raise UserError(_("Security Violation: Audit events cannot be deleted!"))

    @api.model
    def record_event(self, action, subject_type, subject_id, tenant_id=None, actor_id=None,
                     payload=None, before_hash=None, after_hash=None, correlation_id=None):
        """Creates an immutable audit event linked into the cryptographic hash chain."""
        actor = actor_id or str(self.env.user.id)
        tenant = tenant_id or 'GLOBAL'
        corr = correlation_id or str(uuid.uuid4())
        payload_str = json.dumps(payload or {}, sort_keys=True)

        # Retrieve last hash in tenant chain
        last_event = self.sudo().search([('tenant_id', '=', tenant)], order='id desc', limit=1)
        prev_hash = last_event.event_hash if last_event else '0' * 64

        # Compute SHA-256 hash of this event
        hasher = hashlib.sha256()
        hasher.update(prev_hash.encode('utf-8'))
        hasher.update(tenant.encode('utf-8'))
        hasher.update(actor.encode('utf-8'))
        hasher.update(action.encode('utf-8'))
        hasher.update(subject_type.encode('utf-8'))
        hasher.update(subject_id.encode('utf-8'))
        hasher.update(payload_str.encode('utf-8'))
        cur_hash = hasher.hexdigest()

        return super(VinAuditEvent, self.sudo()).create({
            'tenant_id': tenant,
            'actor_id': actor,
            'action': action,
            'subject_type': subject_type,
            'subject_id': subject_id,
            'before_hash': before_hash,
            'after_hash': after_hash,
            'correlation_id': corr,
            'payload': payload_str,
            'previous_hash': prev_hash,
            'event_hash': cur_hash
        })
