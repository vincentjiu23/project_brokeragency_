# -*- coding: utf-8 -*-
"""
Payment Webhook Controller.

Handles incoming webhook callbacks from payment providers (Stripe, Xendit, etc.).
Implements:
  1. Signature verification per provider
  2. Idempotent deduplication via provider event ID
  3. Immutable webhook log recording
  4. Delegation to PaymentOrchestrationService for state transitions

Locked Architecture: All webhooks are logged immutably before processing.
"""
import hashlib
import hmac
import json
import logging

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class PaymentWebhookController(http.Controller):

    @http.route(
        '/api/v1/payment/webhook/<string:provider_code>/<string:provider_uuid>',
        type='json',
        auth='none',
        methods=['POST'],
        csrf=False
    )
    def receive_webhook(self, provider_code, provider_uuid, **kwargs):
        """
        Universal webhook endpoint for all payment providers.
        
        Flow:
          1. Log raw payload immediately (before any processing)
          2. Locate provider configuration
          3. Verify webhook signature
          4. Check idempotent deduplication
          5. Parse provider-specific event
          6. Delegate to PaymentOrchestrationService
          7. Return acknowledgement
        """
        try:
            # Extract raw payload
            raw_body = request.httprequest.get_data(as_text=True)
            payload = json.loads(raw_body) if raw_body else {}

            # Extract headers for signature verification
            signature_header = self._extract_signature_header(provider_code, request.httprequest.headers)
            source_ip = request.httprequest.remote_addr

            # Extract provider event ID for dedup
            provider_event_id = self._extract_event_id(provider_code, payload)
            event_type = self._extract_event_type(provider_code, payload)

            # Step 1: Log webhook immediately (immutable)
            webhook_log = request.env['vin.webhook.log'].sudo().create({
                'provider_code': provider_code,
                'provider_event_id': provider_event_id,
                'event_type': event_type,
                'raw_payload': raw_body,
                'signature_header': signature_header,
                'ip_address': source_ip,
                'processing_state': 'pending',
            })

            # Step 2: Locate provider config
            provider = request.env['vin.payment.provider'].sudo().search([
                ('code', '=', provider_code),
                ('uuid', '=', provider_uuid),
                ('state', 'in', ['live', 'test'])
            ], limit=1)

            if not provider:
                webhook_log.write({
                    'processing_state': 'processing_error',
                    'processing_error': f"Provider not found: {provider_code}/{provider_uuid}",
                    'http_status_code': 404
                })
                return {'status': 'error', 'message': 'Provider not found'}

            webhook_log.write({'tenant_id': provider.tenant_id.id})

            # Step 3: Verify signature
            signature_valid = self._verify_signature(
                provider_code, provider, raw_body, signature_header
            )
            webhook_log.write({'signature_verified': signature_valid})

            if not signature_valid:
                webhook_log.write({
                    'processing_state': 'invalid_signature',
                    'http_status_code': 401
                })
                _logger.warning(
                    "Webhook signature verification failed for %s/%s, event_id=%s",
                    provider_code, provider_uuid, provider_event_id
                )
                return {'status': 'error', 'message': 'Invalid signature'}

            # Step 4: Idempotent deduplication
            if request.env['vin.webhook.log'].sudo().is_duplicate(provider_code, provider_event_id):
                webhook_log.write({
                    'processing_state': 'duplicate',
                    'http_status_code': 200
                })
                _logger.info(
                    "Duplicate webhook skipped: %s/%s event_id=%s",
                    provider_code, provider_uuid, provider_event_id
                )
                return {'status': 'ok', 'message': 'Duplicate event, already processed'}

            # Step 5: Parse and process provider-specific event
            result = self._process_event(provider_code, provider, payload, event_type, webhook_log)

            webhook_log.write({
                'processing_state': 'processed',
                'http_status_code': 200
            })

            return {'status': 'ok', 'result': result}

        except Exception as e:
            _logger.exception(
                "Webhook processing error for %s/%s: %s",
                provider_code, provider_uuid, str(e)
            )
            # Try to update webhook log if it was created
            try:
                if 'webhook_log' in dir() and webhook_log:
                    webhook_log.write({
                        'processing_state': 'processing_error',
                        'processing_error': str(e),
                        'http_status_code': 500
                    })
            except Exception:
                pass

            return {'status': 'error', 'message': 'Internal processing error'}

    def _extract_signature_header(self, provider_code, headers):
        """Extracts the signature header based on provider convention."""
        signature_headers = {
            'stripe': 'Stripe-Signature',
            'xendit': 'X-Xendit-Callback-Token',
            'midtrans': 'X-Midtrans-Signature',
            'wise': 'X-Signature-SHA256',
            'paypal': 'PAYPAL-TRANSMISSION-SIG',
        }
        header_name = signature_headers.get(provider_code, '')
        return headers.get(header_name, '') if header_name else ''

    def _extract_event_id(self, provider_code, payload):
        """Extracts the unique event identifier from provider payload."""
        extractors = {
            'stripe': lambda p: p.get('id', ''),
            'xendit': lambda p: p.get('id', p.get('external_id', '')),
            'midtrans': lambda p: p.get('transaction_id', ''),
            'wise': lambda p: p.get('data', {}).get('resource', {}).get('id', ''),
            'paypal': lambda p: p.get('id', ''),
        }
        extractor = extractors.get(provider_code, lambda p: p.get('id', str(hash(json.dumps(p, sort_keys=True)))))
        return extractor(payload) or str(hash(json.dumps(payload, sort_keys=True)))

    def _extract_event_type(self, provider_code, payload):
        """Extracts the event type string from provider payload."""
        type_paths = {
            'stripe': lambda p: p.get('type', ''),
            'xendit': lambda p: p.get('event', ''),
            'midtrans': lambda p: p.get('transaction_status', ''),
            'wise': lambda p: p.get('event_type', ''),
            'paypal': lambda p: p.get('event_type', ''),
        }
        extractor = type_paths.get(provider_code, lambda p: p.get('type', 'unknown'))
        return extractor(payload)

    def _verify_signature(self, provider_code, provider, raw_body, signature_header):
        """
        Verifies webhook signature using provider-specific algorithm.
        
        In production, each provider has a different signature scheme:
        - Stripe: HMAC-SHA256 with timestamp
        - Xendit: Callback token comparison
        - Midtrans: SHA-512 hash
        
        For now, implements HMAC-SHA256 as the standard verification.
        """
        if not signature_header:
            # If no signature header, allow only in test mode
            return provider.state == 'test'

        secret_ref = provider.webhook_secret_ref
        if not secret_ref:
            _logger.warning("No webhook secret configured for provider %s", provider.name)
            return provider.state == 'test'

        # Standard HMAC-SHA256 verification
        # In production, this would be provider-specific
        try:
            expected = hmac.new(
                secret_ref.encode('utf-8'),
                raw_body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature_header)
        except Exception:
            return False

    def _process_event(self, provider_code, provider, payload, event_type, webhook_log):
        """
        Maps provider-specific events to internal payout state transitions.
        """
        from ..services.payment_orchestration import PaymentOrchestrationService
        orchestrator = PaymentOrchestrationService(request.env.sudo())

        # Map provider event types to internal status
        status_mapping = self._get_status_mapping(provider_code)
        internal_status = status_mapping.get(event_type)

        if not internal_status:
            webhook_log.write({'processing_state': 'ignored'})
            _logger.info(
                "Unhandled event type '%s' for provider %s, ignoring.",
                event_type, provider_code
            )
            return {'action': 'ignored', 'event_type': event_type}

        # Locate the payout by provider transaction reference
        provider_tx_ref = self._extract_transaction_ref(provider_code, payload)
        payout = request.env['vin.payout'].sudo().search([
            ('provider_transaction_id', '=', provider_tx_ref),
            ('tenant_id', '=', provider.tenant_id.id)
        ], limit=1)

        if not payout:
            _logger.warning(
                "No matching payout found for provider ref '%s'",
                provider_tx_ref
            )
            webhook_log.write({
                'processing_state': 'processing_error',
                'processing_error': f"No payout found for provider ref: {provider_tx_ref}"
            })
            return {'action': 'no_match', 'provider_ref': provider_tx_ref}

        webhook_log.write({'payout_id': payout.id})

        # Delegate to orchestrator
        failure_code = self._extract_failure_code(provider_code, payload)
        failure_message = self._extract_failure_message(provider_code, payload)

        orchestrator.process_provider_callback(
            payout_id=payout.id,
            status=internal_status,
            provider_ref=provider_tx_ref,
            raw_response=json.dumps(payload),
            failure_code=failure_code,
            failure_message=failure_message
        )

        return {
            'action': 'processed',
            'payout_ref': payout.reference,
            'new_status': internal_status
        }

    def _get_status_mapping(self, provider_code):
        """Maps provider-specific event types to internal status codes."""
        mappings = {
            'stripe': {
                'payment_intent.processing': 'processing',
                'payment_intent.succeeded': 'succeeded',
                'payment_intent.payment_failed': 'failed',
                'charge.refunded': 'refunded',
                'payout.paid': 'succeeded',
                'payout.failed': 'failed',
            },
            'xendit': {
                'disbursement.completed': 'succeeded',
                'disbursement.failed': 'failed',
            },
            'midtrans': {
                'settlement': 'succeeded',
                'pending': 'processing',
                'deny': 'failed',
                'expire': 'failed',
                'cancel': 'failed',
            },
            'wise': {
                'transfers#state-change': 'processing',
                'transfers#active-cases': 'processing',
                'balances#credit': 'succeeded',
            },
            'paypal': {
                'PAYMENT.PAYOUTS-ITEM.SUCCEEDED': 'succeeded',
                'PAYMENT.PAYOUTS-ITEM.FAILED': 'failed',
                'PAYMENT.PAYOUTS-ITEM.BLOCKED': 'failed',
            },
        }
        return mappings.get(provider_code, {})

    def _extract_transaction_ref(self, provider_code, payload):
        """Extracts the provider transaction reference for payout matching."""
        extractors = {
            'stripe': lambda p: p.get('data', {}).get('object', {}).get('id', ''),
            'xendit': lambda p: p.get('external_id', p.get('id', '')),
            'midtrans': lambda p: p.get('order_id', ''),
            'wise': lambda p: p.get('data', {}).get('resource', {}).get('id', ''),
            'paypal': lambda p: p.get('resource', {}).get('payout_item_id', ''),
        }
        return extractors.get(provider_code, lambda p: '')(payload)

    def _extract_failure_code(self, provider_code, payload):
        """Extracts failure/decline code from provider payload."""
        extractors = {
            'stripe': lambda p: p.get('data', {}).get('object', {}).get('last_payment_error', {}).get('code', ''),
            'xendit': lambda p: p.get('failure_code', ''),
            'midtrans': lambda p: p.get('status_code', ''),
        }
        return extractors.get(provider_code, lambda p: '')(payload)

    def _extract_failure_message(self, provider_code, payload):
        """Extracts human-readable failure message from provider payload."""
        extractors = {
            'stripe': lambda p: p.get('data', {}).get('object', {}).get('last_payment_error', {}).get('message', ''),
            'xendit': lambda p: p.get('failure_reason', ''),
            'midtrans': lambda p: p.get('status_message', ''),
        }
        return extractors.get(provider_code, lambda p: '')(payload)
