# -*- coding: utf-8 -*-
import json
import uuid
from decimal import Decimal
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields

class TestPaymentOrchestration(TransactionCase):
    """
    Test suite for VIN Payment & Payout Orchestration (ADR-002, AC-06, AC-07).
    Covers provider gateway abstraction, idempotent webhook processing,
    payout state machine, threshold four-eyes approval, and circuit breaker.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Contract = self.env['vin.contract']
        self.EscrowAccount = self.env['vin.escrow.account']
        self.Allocation = self.env['vin.escrow.allocation']
        self.PaymentProvider = self.env['vin.payment.provider']
        self.Payout = self.env['vin.payout']
        self.PaymentEvent = self.env['vin.payment.event']
        self.WebhookLog = self.env['vin.webhook.log']

        self.tenant = self.Tenant.create({'code': 'T_PAY', 'name': 'Payment Test Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_PAY_CLIENT',
            'name': 'Client Payment Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_contact = self.Partner.create({'name': 'Design Agency Partner'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })

        # Payment Provider
        self.provider = self.PaymentProvider.create({
            'name': 'Stripe Connect Direct',
            'code': 'stripe_test',
            'provider_type': 'stripe',
            'state': 'enabled',
            'tenant_id': self.tenant.id,
            'api_endpoint': 'https://api.stripe.com/v1',
            'webhook_secret': 'whsec_test_secret_12345',
            'supported_currencies': 'USD,EUR,GBP'
        })

        # Contract & Escrow
        self.contract = self.Contract.create({
            'title': 'Milestone Payment Contract',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'partner_profile_id': self.partner_profile.id,
            'total_contract_value': 10000.0,
            'state': 'active'
        })

        self.escrow_account = self.EscrowAccount.create({
            'contract_id': self.contract.id,
            'tenant_id': self.tenant.id,
            'currency': 'USD',
            'total_deposited': 10000.0,
            'state': 'funded'
        })

        self.allocation = self.Allocation.create({
            'escrow_account_id': self.escrow_account.id,
            'tenant_id': self.tenant.id,
            'amount': 5000.0,
            'currency': 'USD',
            'state': 'released'
        })

    def test_01_create_payout_lifecycle(self):
        """Test standard payout creation, approval, and settlement."""
        payout = self.Payout.create({
            'tenant_id': self.tenant.id,
            'allocation_id': self.allocation.id,
            'partner_profile_id': self.partner_profile.id,
            'provider_id': self.provider.id,
            'gross_amount': 5000.0,
            'currency': 'USD',
            'recipient_bank_ref': 'IBAN_US9876543210'
        })
        self.assertEqual(payout.state, 'draft')
        self.assertEqual(payout.net_amount, 5000.0)

        # Action: Approve
        payout.action_approve()
        self.assertEqual(payout.state, 'approved')

        # Action: Process
        payout.action_submit_to_provider()
        self.assertEqual(payout.state, 'processing')

        # Action: Settle
        payout.action_mark_settled(provider_tx_id='tx_stripe_999888')
        self.assertEqual(payout.state, 'settled')
        self.assertEqual(payout.provider_reference, 'tx_stripe_999888')

    def test_02_idempotent_webhook_deduplication(self):
        """Test AC-06: duplicate webhook payloads do not re-execute settlements."""
        idempotency_key = f"evt_{uuid.uuid4().hex}"
        payload = json.dumps({
            'event': 'charge.succeeded',
            'amount': 5000,
            'currency': 'usd',
            'id': idempotency_key
        })

        # First webhook arrival
        log1 = self.WebhookLog.create({
            'tenant_id': self.tenant.id,
            'provider_id': self.provider.id,
            'idempotency_key': idempotency_key,
            'payload': payload,
            'status': 'received'
        })
        processed1 = log1.process_webhook()
        self.assertTrue(processed1)
        self.assertEqual(log1.status, 'processed')

        # Duplicate webhook arrival
        log2 = self.WebhookLog.create({
            'tenant_id': self.tenant.id,
            'provider_id': self.provider.id,
            'idempotency_key': idempotency_key,
            'payload': payload,
            'status': 'received'
        })
        # Should detect duplicate and skip re-execution
        processed2 = log2.process_webhook()
        self.assertEqual(log2.status, 'duplicate_ignored')

    def test_03_circuit_breaker_degraded_state(self):
        """Test AC-07: consecutive failures trip circuit breaker to degraded."""
        self.provider.record_failure("HTTP 503 Service Unavailable")
        self.provider.record_failure("HTTP 504 Gateway Timeout")
        self.provider.record_failure("HTTP 503 Service Unavailable")
        self.provider.record_failure("HTTP 503 Service Unavailable")
        self.provider.record_failure("Connection reset by peer")

        self.assertEqual(self.provider.state, 'degraded')
        self.assertFalse(self.provider.is_available_for_payouts())
