# -*- coding: utf-8 -*-
"""
Integration Endpoint & Circuit Breaker Model (Q137–Q146, AC-07 Technical Domain).
Tracks third-party integration health, latency, and circuit breaker states:
  CLOSED (Healthy) → OPEN (Tripped / Outage) → HALF_OPEN (Probing Recovery)
AC-07: Third-party outage triggers INTEGRATION_DEGRADED safely while protecting core Odoo state.
"""
import uuid
import json
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class VinIntegrationEndpoint(models.Model):
    """
    Third-Party Integration Endpoint & Circuit Breaker.
    Manages resilience states for external providers (payment gateways, tax engines, e-signatures).
    """
    _name = 'vin.integration.endpoint'
    _description = 'VIN Integration Endpoint & Circuit Breaker'
    _inherit = ['mail.thread']
    _order = 'name asc, id asc'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )

    name = fields.Char(string='Endpoint Name', required=True)
    code = fields.Char(string='Endpoint Code', required=True, index=True)
    provider_type = fields.Selection([
        ('payment_gateway', 'Payment Gateway (Stripe, Xendit)'),
        ('tax_authority', 'Statutory Tax Authority (DJP, Avalara)'),
        ('esignature', 'e-Signature Provider (PrivyID, DocuSign)'),
        ('storage_vault', 'Encrypted Asset Vault / S3 WORM'),
        ('event_mesh', 'External Event Mesh / Kafka Broker'),
    ], string='Provider Category', required=True, index=True)

    base_url = fields.Char(string='Base URL / Target Host')
    active = fields.Boolean(string='Active', default=True)

    # ── Circuit Breaker Configuration ──
    failure_threshold = fields.Integer(
        string='Consecutive Failure Threshold', default=5, required=True,
        help="Number of consecutive failures required to trip circuit from CLOSED to OPEN."
    )
    recovery_timeout_sec = fields.Integer(
        string='Recovery Timeout (Seconds)', default=60, required=True,
        help="Seconds circuit stays OPEN before entering HALF-OPEN probe state."
    )

    # ── Real-Time Circuit State ──
    circuit_state = fields.Selection([
        ('closed', 'CLOSED (Healthy / Operational)'),
        ('open', 'OPEN (Tripped / Rejecting Calls)'),
        ('half_open', 'HALF-OPEN (Probing Recovery)'),
    ], string='Circuit Breaker State', default='closed', required=True, tracking=True)

    health_status = fields.Selection([
        ('operational', 'Fully Operational (Green)'),
        ('degraded', 'Degraded Performance (Yellow)'),
        ('outage', 'Major Outage / Tripped (Red)'),
    ], string='Health Status', default='operational', required=True, tracking=True)

    # ── Metrics & Telemetry ──
    consecutive_failures = fields.Integer(string='Consecutive Failures', default=0, readonly=True)
    consecutive_successes = fields.Integer(string='Consecutive Successes', default=0, readonly=True)
    total_calls = fields.Integer(string='Total Requests Executed', default=0, readonly=True)
    failed_calls = fields.Integer(string='Total Failed Requests', default=0, readonly=True)

    last_failure_at = fields.Datetime(string='Last Failure At', readonly=True)
    last_success_at = fields.Datetime(string='Last Success At', readonly=True)
    last_trip_at = fields.Datetime(string='Circuit Last Tripped At', readonly=True)
    last_error_message = fields.Text(string='Last Error Diagnostic', readonly=True)

    def record_success(self):
        """Called upon successful response from external provider."""
        for rec in self:
            now = fields.Datetime.now()
            vals = {
                'consecutive_failures': 0,
                'consecutive_successes': rec.consecutive_successes + 1,
                'total_calls': rec.total_calls + 1,
                'last_success_at': now,
            }
            # If in half-open state and succeeded, close the circuit!
            if rec.circuit_state == 'half_open':
                vals['circuit_state'] = 'closed'
                vals['health_status'] = 'operational'
                rec.message_post(body=_("Circuit Breaker reset to CLOSED. External endpoint healthy."))
            elif rec.circuit_state == 'closed' and rec.health_status != 'operational':
                vals['health_status'] = 'operational'

            rec.write(vals)

    def record_failure(self, error_message=None):
        """
        Called upon failed response or timeout from external provider.
        Trips circuit to OPEN if failure_threshold is breached (AC-07).
        """
        for rec in self:
            now = fields.Datetime.now()
            failures = rec.consecutive_failures + 1
            vals = {
                'consecutive_failures': failures,
                'consecutive_successes': 0,
                'total_calls': rec.total_calls + 1,
                'failed_calls': rec.failed_calls + 1,
                'last_failure_at': now,
                'last_error_message': error_message or _("Unspecified integration failure"),
            }

            # Check if threshold reached or already half-open
            if rec.circuit_state == 'half_open' or failures >= rec.failure_threshold:
                vals['circuit_state'] = 'open'
                vals['health_status'] = 'outage'
                vals['last_trip_at'] = now

                # Emit INTEGRATION_DEGRADED audit event (AC-07)
                if 'vin.audit.event' in self.env:
                    self.env['vin.audit.event'].sudo().create({
                        'tenant_id': rec.tenant_id.id,
                        'actor_user_id': self.env.user.id,
                        'event_type': 'INTEGRATION_DEGRADED',
                        'entity_name': 'vin.integration.endpoint',
                        'entity_id': str(rec.id),
                        'state_after': 'open',
                        'payload': json.dumps({
                            'endpoint_code': rec.code,
                            'provider_type': rec.provider_type,
                            'consecutive_failures': failures,
                            'error': error_message or '',
                        })
                    })

                rec.message_post(body=_(
                    "Circuit Breaker TRIPPED to OPEN! Failures: %d >= %d. Error: %s"
                ) % (failures, rec.failure_threshold, error_message or ''))

            elif failures >= 2:
                vals['health_status'] = 'degraded'

            rec.write(vals)

    def can_execute(self):
        """
        Evaluates whether a call should be allowed through or immediately rejected.

        Returns:
            bool: True if allowed, False if rejected by circuit breaker.
        """
        self.ensure_one()
        if self.circuit_state == 'closed':
            return True

        if self.circuit_state == 'open':
            # Check if recovery timeout has elapsed
            if self.last_trip_at:
                now = fields.Datetime.now()
                elapsed = (now - self.last_trip_at).total_seconds()
                if elapsed >= self.recovery_timeout_sec:
                    # Transition to half-open to probe recovery
                    self.write({'circuit_state': 'half_open'})
                    self.message_post(body=_("Recovery timeout elapsed. Circuit transitioning to HALF-OPEN."))
                    return True
            return False

        if self.circuit_state == 'half_open':
            # Allow limited probe calls
            return True

        return True

    def action_manual_reset(self):
        """Allows administrator to manually close circuit breaker after verifying external fix."""
        for rec in self:
            rec.write({
                'circuit_state': 'closed',
                'health_status': 'operational',
                'consecutive_failures': 0,
            })
            rec.message_post(body=_("Circuit breaker manually reset to CLOSED by operator."))
