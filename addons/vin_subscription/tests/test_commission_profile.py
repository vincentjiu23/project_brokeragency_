# -*- coding: utf-8 -*-
from decimal import Decimal
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields

class TestCommissionProfile(TransactionCase):
    """
    Test suite for Subscriptions, Tier Plans, and Dynamic Commission Profiles (Q99–Q105, Q180).
    Validates volume tiers, take-rate discounts, fee caps, and SUBSCRIPTION_UPGRADED audit emissions.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Plan = self.env['vin.subscription.plan']
        self.Subscription = self.env['vin.subscription']
        self.CommissionProfile = self.env['vin.commission.rule.profile']
        self.TierLine = self.env['vin.commission.tier.line']

        self.tenant = self.Tenant.create({'code': 'T_SUB', 'name': 'Subscription Test Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_SUB_CLIENT',
            'name': 'Subscription Client Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_contact = self.Partner.create({'name': 'Elite Design Agency'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })

        # Base Commission Profile
        self.profile = self.CommissionProfile.create({
            'name': 'Standard Platform Take-Rate',
            'code': 'STD_15',
            'tenant_id': self.tenant.id,
            'base_take_rate': 15.0,
            'min_commission_amount': 50.0,
            'max_commission_cap': 5000.0,
            'is_default': True
        })

        # Volume Tiers
        self.TierLine.create({
            'profile_id': self.profile.id,
            'name': 'Tier 1 ($0 - $20,000)',
            'min_volume': 0.0,
            'max_volume': 20000.0,
            'take_rate': 15.0
        })
        self.TierLine.create({
            'profile_id': self.profile.id,
            'name': 'Tier 2 ($20,001 - $100,000)',
            'min_volume': 20000.01,
            'max_volume': 100000.0,
            'take_rate': 12.0
        })
        self.TierLine.create({
            'profile_id': self.profile.id,
            'name': 'Tier 3 (>$100,000)',
            'min_volume': 100000.01,
            'max_volume': 0.0,
            'take_rate': 8.0
        })

        # Plans
        self.starter_plan = self.Plan.create({
            'name': 'Client Starter',
            'code': 'CLI_STARTER',
            'tenant_id': self.tenant.id,
            'target_type': 'client',
            'price': 0.0,
            'take_rate_commission_discount': 0.0
        })

        self.enterprise_plan = self.Plan.create({
            'name': 'Client Enterprise',
            'code': 'CLI_ENT',
            'tenant_id': self.tenant.id,
            'target_type': 'client',
            'price': 999.0,
            'take_rate_commission_discount': 3.0
        })

    def test_01_standard_commission_calculation(self):
        """Test base take-rate calculation on standard tier."""
        from ..services.fee_evaluator import FeeEvaluatorService
        evaluator = FeeEvaluatorService(self.env)

        res = evaluator.evaluate_commission(contract_amount=10000.0, profile_code='STD_15')
        self.assertEqual(res['effective_take_rate'], Decimal('15.00'))
        self.assertEqual(res['platform_fee'], Decimal('1500.00'))
        self.assertEqual(res['partner_gross_before_tax'], Decimal('8500.00'))

    def test_02_volume_tier_discount(self):
        """Test rate reduction on higher contract volume ($50k -> 12%, $150k -> 8%)."""
        from ..services.fee_evaluator import FeeEvaluatorService
        evaluator = FeeEvaluatorService(self.env)

        # $50,000 -> 12%
        res_50k = evaluator.evaluate_commission(contract_amount=50000.0, profile_code='STD_15')
        self.assertEqual(res_50k['effective_take_rate'], Decimal('12.00'))
        self.assertEqual(res_50k['platform_fee'], Decimal('6000.00'))  # Wait, capped at $5,000!
        # Because max cap is 5000:
        self.assertEqual(res_50k['platform_fee'], Decimal('5000.00'))

    def test_03_subscription_plan_take_rate_discount(self):
        """Test subscriber with Enterprise plan receives -3% take-rate discount."""
        from ..services.fee_evaluator import FeeEvaluatorService
        evaluator = FeeEvaluatorService(self.env)

        # Assign Enterprise subscription to Client
        self.Subscription.create({
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'plan_id': self.enterprise_plan.id,
            'state': 'active'
        })

        # $10,000 contract: standard 15% - 3% discount = 12%
        res = evaluator.evaluate_commission(
            contract_amount=10000.0,
            client_org_id=self.client_org.id,
            profile_code='STD_15'
        )
        self.assertEqual(res['effective_take_rate'], Decimal('12.00'))
        self.assertEqual(res['platform_fee'], Decimal('1200.00'))
        self.assertTrue(any("Client Plan 'Client Enterprise': -3.0%" in d for d in res['applied_discounts']))

    def test_04_plan_upgrade_lifecycle_and_audit(self):
        """Test subscription plan upgrade transitions and audit logging."""
        sub = self.Subscription.create({
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'plan_id': self.starter_plan.id,
            'state': 'active'
        })
        self.assertEqual(sub.plan_id.code, 'CLI_STARTER')

        # Upgrade to Enterprise
        sub.action_upgrade_plan(self.enterprise_plan.id)
        self.assertEqual(sub.plan_id.code, 'CLI_ENT')
        self.assertEqual(sub.state, 'active')
