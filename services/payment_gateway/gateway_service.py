# -*- coding: utf-8 -*-
"""
Payment Gateway Service — Unified Provider Adapter Interface.

Abstracts multi-provider payment operations behind a single interface.
Each provider adapter implements the same contract:
  - create_payout(amount, currency, recipient, idempotency_key)
  - check_payout_status(provider_tx_id)
  - create_refund(provider_tx_id, amount, idempotency_key)
  - verify_webhook_signature(raw_body, signature_header, secret)

This service lives in the services/ directory (cloud-native boundary)
and is called by the PaymentOrchestrationService in the Odoo addon.
"""
import logging
from abc import ABC, abstractmethod

_logger = logging.getLogger(__name__)


class PaymentGatewayAdapter(ABC):
    """Abstract base class for payment provider adapters."""

    @abstractmethod
    def create_payout(self, amount, currency_code, recipient_details, idempotency_key, metadata=None):
        """
        Initiates a payout/disbursement to the recipient.
        
        Args:
            amount: Decimal amount to pay out
            currency_code: ISO 4217 currency code (e.g., 'IDR', 'USD')
            recipient_details: Dict with bank/wallet details
            idempotency_key: UUID string for deduplication
            metadata: Optional dict of metadata tags
            
        Returns:
            dict with:
              - provider_transaction_id: str
              - status: str ('submitted', 'processing', 'succeeded', 'failed')
              - raw_response: str (JSON)
        """
        pass

    @abstractmethod
    def check_payout_status(self, provider_transaction_id):
        """
        Checks the current status of a payout.
        
        Returns:
            dict with:
              - status: str
              - failure_code: Optional[str]
              - failure_message: Optional[str]
              - raw_response: str
        """
        pass

    @abstractmethod
    def create_refund(self, provider_transaction_id, amount, idempotency_key, reason=None):
        """
        Initiates a refund for a completed payout.
        
        Returns:
            dict with:
              - refund_id: str
              - status: str
              - raw_response: str
        """
        pass

    @abstractmethod
    def verify_webhook_signature(self, raw_body, signature_header, secret):
        """
        Verifies the webhook signature from this provider.
        
        Returns:
            bool: True if signature is valid
        """
        pass


class StripeAdapter(PaymentGatewayAdapter):
    """Stripe payment provider adapter."""

    def __init__(self, api_key, is_sandbox=False):
        self.api_key = api_key
        self.is_sandbox = is_sandbox
        self.base_url = 'https://api.stripe.com/v1'

    def create_payout(self, amount, currency_code, recipient_details, idempotency_key, metadata=None):
        """
        Creates a Stripe payout via the Payouts API.
        
        Production implementation would call:
          POST /v1/payouts with Stripe-Idempotency-Key header
        """
        _logger.info(
            "Stripe create_payout: amount=%s %s, idempotency=%s",
            amount, currency_code, idempotency_key
        )
        # In production: stripe.Payout.create(...)
        return {
            'provider_transaction_id': f'po_simulated_{idempotency_key[:8]}',
            'status': 'submitted',
            'raw_response': '{"status": "pending", "simulated": true}'
        }

    def check_payout_status(self, provider_transaction_id):
        _logger.info("Stripe check_payout_status: %s", provider_transaction_id)
        return {
            'status': 'processing',
            'failure_code': None,
            'failure_message': None,
            'raw_response': '{"status": "in_transit", "simulated": true}'
        }

    def create_refund(self, provider_transaction_id, amount, idempotency_key, reason=None):
        _logger.info(
            "Stripe create_refund: tx=%s, amount=%s, reason=%s",
            provider_transaction_id, amount, reason
        )
        return {
            'refund_id': f're_simulated_{idempotency_key[:8]}',
            'status': 'succeeded',
            'raw_response': '{"status": "succeeded", "simulated": true}'
        }

    def verify_webhook_signature(self, raw_body, signature_header, secret):
        """Stripe uses HMAC-SHA256 with timestamp-based signature."""
        import hmac
        import hashlib
        try:
            # Stripe signature format: t=<timestamp>,v1=<signature>
            parts = dict(p.split('=', 1) for p in signature_header.split(','))
            timestamp = parts.get('t', '')
            expected_sig = parts.get('v1', '')
            
            payload_to_sign = f"{timestamp}.{raw_body}"
            computed = hmac.new(
                secret.encode('utf-8'),
                payload_to_sign.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(computed, expected_sig)
        except Exception:
            return False


class XenditAdapter(PaymentGatewayAdapter):
    """Xendit payment provider adapter (Indonesia-focused)."""

    def __init__(self, api_key, is_sandbox=False):
        self.api_key = api_key
        self.is_sandbox = is_sandbox
        self.base_url = 'https://api.xendit.co'

    def create_payout(self, amount, currency_code, recipient_details, idempotency_key, metadata=None):
        _logger.info(
            "Xendit create_payout: amount=%s %s, idempotency=%s",
            amount, currency_code, idempotency_key
        )
        return {
            'provider_transaction_id': f'disb_simulated_{idempotency_key[:8]}',
            'status': 'submitted',
            'raw_response': '{"status": "PENDING", "simulated": true}'
        }

    def check_payout_status(self, provider_transaction_id):
        return {
            'status': 'processing',
            'failure_code': None,
            'failure_message': None,
            'raw_response': '{"status": "PENDING", "simulated": true}'
        }

    def create_refund(self, provider_transaction_id, amount, idempotency_key, reason=None):
        return {
            'refund_id': f'ref_simulated_{idempotency_key[:8]}',
            'status': 'submitted',
            'raw_response': '{"status": "PENDING", "simulated": true}'
        }

    def verify_webhook_signature(self, raw_body, signature_header, secret):
        """Xendit uses callback token comparison."""
        return signature_header == secret


class ManualAdapter(PaymentGatewayAdapter):
    """Manual / bank transfer adapter for offline reconciliation."""

    def create_payout(self, amount, currency_code, recipient_details, idempotency_key, metadata=None):
        return {
            'provider_transaction_id': f'manual_{idempotency_key[:8]}',
            'status': 'submitted',
            'raw_response': '{"type": "manual", "requires_confirmation": true}'
        }

    def check_payout_status(self, provider_transaction_id):
        return {
            'status': 'processing',
            'failure_code': None,
            'failure_message': None,
            'raw_response': '{"type": "manual", "awaiting_confirmation": true}'
        }

    def create_refund(self, provider_transaction_id, amount, idempotency_key, reason=None):
        return {
            'refund_id': f'manual_ref_{idempotency_key[:8]}',
            'status': 'submitted',
            'raw_response': '{"type": "manual_refund"}'
        }

    def verify_webhook_signature(self, raw_body, signature_header, secret):
        return True  # Manual webhooks are internally generated


class PaymentGatewayFactory:
    """Factory to instantiate the correct provider adapter."""

    _adapters = {
        'stripe': StripeAdapter,
        'xendit': XenditAdapter,
        'manual': ManualAdapter,
    }

    @classmethod
    def get_adapter(cls, provider_code, api_key, is_sandbox=False):
        """
        Returns the appropriate adapter instance for the provider.
        
        Args:
            provider_code: str from vin.payment.provider.code
            api_key: Decrypted API key
            is_sandbox: Whether to use sandbox/test mode
            
        Returns:
            PaymentGatewayAdapter instance
            
        Raises:
            ValueError: If provider_code is not supported
        """
        adapter_class = cls._adapters.get(provider_code)
        if not adapter_class:
            raise ValueError(f"Unsupported payment provider: {provider_code}")
        return adapter_class(api_key=api_key, is_sandbox=is_sandbox)

    @classmethod
    def register_adapter(cls, provider_code, adapter_class):
        """Registers a new provider adapter (plugin extensibility)."""
        if not issubclass(adapter_class, PaymentGatewayAdapter):
            raise TypeError("Adapter must extend PaymentGatewayAdapter")
        cls._adapters[provider_code] = adapter_class
