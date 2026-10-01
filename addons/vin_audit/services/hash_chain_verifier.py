# -*- coding: utf-8 -*-
import hashlib

class HashChainVerifierService:
    """Verifies the mathematical integrity of the append-only audit event hash chain."""

    def __init__(self, env):
        self.env = env

    def verify_tenant_chain(self, tenant_id):
        """Walks the entire audit event chain from root to tip, verifying every SHA-256 link."""
        events = self.env['vin.audit.event'].sudo().search([('tenant_id', '=', tenant_id)], order='id asc')
        expected_prev = '0' * 64

        for ev in events:
            if ev.previous_hash != expected_prev:
                return {
                    'valid': False,
                    'corrupted_event_uuid': ev.uuid,
                    'error': f'Chain broken at event {ev.uuid}: previous_hash mismatch'
                }

            hasher = hashlib.sha256()
            hasher.update(ev.previous_hash.encode('utf-8'))
            hasher.update(ev.tenant_id.encode('utf-8'))
            hasher.update(ev.actor_id.encode('utf-8'))
            hasher.update(ev.action.encode('utf-8'))
            hasher.update(ev.subject_type.encode('utf-8'))
            hasher.update(ev.subject_id.encode('utf-8'))
            hasher.update(ev.payload.encode('utf-8'))
            computed_hash = hasher.hexdigest()

            if computed_hash != ev.event_hash:
                return {
                    'valid': False,
                    'corrupted_event_uuid': ev.uuid,
                    'error': f'Tamper detected at event {ev.uuid}: content hash mismatch'
                }

            expected_prev = ev.event_hash

        return {'valid': True, 'count': len(events)}
