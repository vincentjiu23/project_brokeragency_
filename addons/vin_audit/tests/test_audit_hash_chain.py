# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from ..services.hash_chain_verifier import HashChainVerifierService

class TestAuditHashChain(TransactionCase):
    """Test suite for append-only audit events and cryptographic hash chain verification."""

    def setUp(self):
        super().setUp()
        self.AuditEvent = self.env['vin.audit.event']
        self.verifier = HashChainVerifierService(self.env)
        self.tenant_uuid = "TENANT-AUDIT-TEST-001"

    def test_hash_chain_creation_and_verification(self):
        """Records multiple events and verifies that the SHA-256 chain is mathematically valid."""
        # Event 1
        ev1 = self.AuditEvent.record_event(
            action='PROPOSAL_SUBMITTED',
            subject_type='vin.proposal',
            subject_id='PROP-001',
            tenant_id=self.tenant_uuid,
            payload={'amount': 15000}
        )
        self.assertEqual(ev1.previous_hash, '0' * 64)

        # Event 2
        ev2 = self.AuditEvent.record_event(
            action='PROPOSAL_APPROVED',
            subject_type='vin.proposal',
            subject_id='PROP-001',
            tenant_id=self.tenant_uuid,
            payload={'approver': 'director'}
        )
        self.assertEqual(ev2.previous_hash, ev1.event_hash)

        # Verify integrity of chain
        verification = self.verifier.verify_tenant_chain(self.tenant_uuid)
        self.assertTrue(verification['valid'])
        self.assertGreaterEqual(verification['count'], 2)

    def test_immutability_enforcement(self):
        """Audit events cannot be modified or deleted."""
        ev = self.AuditEvent.record_event(
            action='SECURITY_ALERT',
            subject_type='system',
            subject_id='SYS-001',
            tenant_id=self.tenant_uuid,
            payload={'alert': 'break_glass'}
        )

        with self.assertRaises(UserError):
            ev.write({'action': 'TAMPERED_ACTION'})

        with self.assertRaises(UserError):
            ev.unlink()
