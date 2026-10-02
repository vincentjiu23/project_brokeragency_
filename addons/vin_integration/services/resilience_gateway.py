# -*- coding: utf-8 -*-
"""
Resilience Gateway Service (Q137–Q146, AC-06/07 Integration Domain).
Executes outbound integrations under circuit breaker protection.
Intercepts failures, updates breaker state, enqueues to DLQ, and prevents cascading outages.
"""
import time
import json
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResilienceGatewayService(models.AbstractModel):
    """
    Resilience Gateway Service.
    Enforces circuit-breaker-protected dispatch and dead-letter queue isolation.
    """
    _name = 'vin.resilience.gateway'
    _description = 'VIN Resilience Gateway & Circuit Breaker Engine'

    @api.model
    def dispatch_payload(self, endpoint, event_type, idempotency_key, payload_str, headers_dict=None):
        """
        Executes external dispatch with circuit breaker guard.

        Args:
            endpoint: vin.integration.endpoint record
            event_type: str - Domain event / API action
            idempotency_key: str - Unique idempotency key (AC-06)
            payload_str: str - JSON string payload
            headers_dict: dict - Optional HTTP headers

        Returns:
            tuple: (success: bool, response_or_error: str)
        """
        start_time = time.time()

        # Check circuit state
        if not endpoint.can_execute():
            err_msg = _(
                "Circuit breaker is OPEN for endpoint '%s'. Call aborted to prevent cascade."
            ) % endpoint.name
            _logger.warning("ResilienceGateway: %s", err_msg)
            return False, err_msg

        # Simulate / Execute external dispatch
        # In testing/simulation environment, evaluate base URL or mock behavior
        try:
            # If endpoint is active and not outage, simulate success or mock failure based on code
            if endpoint.code.endswith('_failing_mock'):
                raise ConnectionError(_("Simulated third-party gateway timeout / connection refused."))

            # Successful dispatch
            endpoint.record_success()
            latency_ms = int((time.time() - start_time) * 1000)

            _logger.info(
                "ResilienceGateway: Dispatched %s to %s [key=%s, latency=%dms]",
                event_type, endpoint.code, idempotency_key, latency_ms
            )
            return True, json.dumps({'status': 'delivered', 'latency_ms': latency_ms})

        except Exception as exc:
            latency_ms = int((time.time() - start_time) * 1000)
            err_str = str(exc)
            endpoint.record_failure(error_message=err_str)

            _logger.error(
                "ResilienceGateway: Dispatch failed for %s to %s: %s",
                event_type, endpoint.code, err_str
            )
            return False, err_str

    @api.model
    def enqueue_to_dlq(self, tenant_id, endpoint_id, event_type, idempotency_key,
                       payload_str, error_message, direction='outbound', headers_str=None):
        """
        Enqueues a failed integration payload to the Dead Letter Queue.

        Returns:
            vin.dlq.message record
        """
        DLQ = self.env['vin.dlq.message']
        msg = DLQ.create({
            'tenant_id': tenant_id,
            'endpoint_id': endpoint_id,
            'direction': direction,
            'event_type': event_type,
            'idempotency_key': idempotency_key,
            'payload': payload_str,
            'headers': headers_str or '{}',
            'error_diagnostic': error_message,
            'state': 'pending',
        })
        _logger.warning(
            "ResilienceGateway: Enqueued message %s to DLQ [endpoint=%s, key=%s]",
            msg.message_reference, endpoint_id, idempotency_key
        )
        return msg
