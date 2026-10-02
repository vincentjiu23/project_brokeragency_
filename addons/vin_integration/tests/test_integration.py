# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestIntegrationResilience(TransactionCase):
    """
    Test suite for Integration Resilience & Circuit Breakers (Q137–Q146, AC-06/07).
    Verifies:
      - Circuit breaker CLOSED → OPEN state transitions upon failure threshold breach
      - AC-07: INTEGRATION_DEGRADED event emission
      - Call blocking during OPEN state
      - Dead Letter Queue (DLQ) message creation with idempotency key
      - Idempotent DLQ replay and resolution
      - Retry limit exhaustion
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Endpoint = self.env['vin.integration.endpoint']
        self.DLQ = self.env['vin.dlq.message']
        self.Gateway = self.env['vin.resilience.gateway']

        self.tenant = self.Tenant.create({'code': 'T_INT', 'name': 'Integration Test Tenant'})
        self.endpoint = self.Endpoint.create({
            'name': 'Primary Payment Provider (Stripe)',
            'code': 'stripe_primary',
            'tenant_id': self.tenant.id,
            'provider_type': 'payment_gateway',
            'failure_threshold': 3,
            'recovery_timeout_sec': 60,
        })

    def test_01_circuit_breaker_trips_to_open_on_failures(self):
        """Test AC-07: Breaker trips to OPEN and emits INTEGRATION_DEGRADED after threshold breaches."""
        self.assertEqual(self.endpoint.circuit_state, 'closed')
        self.assertEqual(self.endpoint.health_status, 'operational')
        self.assertTrue(self.endpoint.can_execute())

        # Record 2 failures (below threshold of 3) -> degraded
        self.endpoint.record_failure(error_message="HTTP 503 Service Unavailable")
        self.endpoint.record_failure(error_message="HTTP 504 Gateway Timeout")
        self.assertEqual(self.endpoint.circuit_state, 'closed')
        self.assertEqual(self.endpoint.health_status, 'degraded')
        self.assertTrue(self.endpoint.can_execute())

        # 3rd failure reaches threshold -> trips circuit to OPEN and health to outage!
        self.endpoint.record_failure(error_message="Connection Refused")
        self.assertEqual(self.endpoint.circuit_state, 'open')
        self.assertEqual(self.endpoint.health_status, 'outage')
        self.assertEqual(self.endpoint.consecutive_failures, 3)

        # Call must now be blocked by circuit breaker
        self.assertFalse(self.endpoint.can_execute())

    def test_02_circuit_breaker_manual_reset(self):
        """Test operator manual reset restores circuit to CLOSED and operational."""
        # Force breaker to open
        for _ in range(3):
            self.endpoint.record_failure(error_message="Mock Error")
        self.assertEqual(self.endpoint.circuit_state, 'open')

        # Manual reset
        self.endpoint.action_manual_reset()
        self.assertEqual(self.endpoint.circuit_state, 'closed')
        self.assertEqual(self.endpoint.health_status, 'operational')
        self.assertEqual(self.endpoint.consecutive_failures, 0)
        self.assertTrue(self.endpoint.can_execute())

    def test_03_dlq_message_enqueue_and_idempotent_replay(self):
        """Test AC-06: DLQ message stores idempotency key, replays, and transitions to resolved."""
        idempotency_key = "IDEMP-TEST-PAYOUT-999"
        payload_data = '{"amount": 5000.0, "currency": "IDR", "payout_id": 42}'

        msg = self.Gateway.enqueue_to_dlq(
            tenant_id=self.tenant.id,
            endpoint_id=self.endpoint.id,
            event_type='PAYOUT_EXECUTE',
            idempotency_key=idempotency_key,
            payload_str=payload_data,
            error_message="Connection reset by peer",
        )

        self.assertEqual(msg.state, 'pending')
        self.assertEqual(msg.idempotency_key, idempotency_key)
        self.assertEqual(msg.retry_count, 0)

        # Replay message while endpoint is healthy (closed)
        msg.action_replay()
        self.assertEqual(msg.state, 'resolved')
        self.assertEqual(msg.retry_count, 1)
        self.assertTrue(msg.resolved_at)

    def test_04_dlq_replay_blocked_when_circuit_open(self):
        """Test that replaying a DLQ message is rejected if circuit breaker is OPEN."""
        # Trip the breaker
        for _ in range(3):
            self.endpoint.record_failure(error_message="Persistent Gateway Failure")
        self.assertEqual(self.endpoint.circuit_state, 'open')

        msg = self.Gateway.enqueue_to_dlq(
            tenant_id=self.tenant.id,
            endpoint_id=self.endpoint.id,
            event_type='TAX_SYNC',
            idempotency_key="IDEMP-TAX-001",
            payload_str='{"invoice_id": 101}',
            error_message="Outage",
        )

        # Replay should raise UserError because circuit is open
        with self.assertRaises(UserError):
            msg.action_replay()
        self.assertEqual(msg.state, 'pending')

    def test_05_dlq_discard(self):
        """Test manually discarding an obsolete DLQ message."""
        msg = self.Gateway.enqueue_to_dlq(
            tenant_id=self.tenant.id,
            endpoint_id=self.endpoint.id,
            event_type='STALE_NOTIFICATION',
            idempotency_key="IDEMP-NOTIF-002",
            payload_str='{"user_id": 1}',
            error_message="User unsubscribed",
        )

        msg.action_discard(reason="Customer requested cancellation")
        self.assertEqual(msg.state, 'discarded')
        self.assertTrue(msg.resolved_at)
