# -*- coding: utf-8 -*-
"""
Fee Evaluator Service (Q99–Q105, Q180).
Computes dynamic platform take-rate commissions with volume tiers,
subscription plan discounts, and fee boundary limits.
"""
from decimal import Decimal
import logging
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class FeeEvaluatorService:
    """Dynamic fee evaluation engine for transaction commissions and platform take-rates."""

    def __init__(self, env):
        self.env = env

    def evaluate_commission(self, contract_amount, client_org_id=None, partner_profile_id=None, profile_code=None):
        """
        Calculates exact platform take-rate commission for a contract or milestone.

        Args:
            contract_amount (float or Decimal): Gross contract or milestone value.
            client_org_id (int): vin.organization ID.
            partner_profile_id (int): creative.partner.profile ID.
            profile_code (str): Optional specific commission rule profile code.

        Returns:
            dict containing:
                - contract_amount: Decimal
                - base_rate: Decimal (%)
                - effective_take_rate: Decimal (%)
                - platform_fee: Decimal
                - partner_gross_before_tax: Decimal
                - applied_discounts: list of str
                - profile_code: str
        """
        amount_dec = Decimal(str(contract_amount))
        if amount_dec <= Decimal('0.00'):
            raise UserError(_("Contract amount must be greater than zero."))

        # 1. Resolve Commission Profile
        profile_domain = [('code', '=', profile_code)] if profile_code else [('is_default', '=', True)]
        profile = self.env['vin.commission.rule.profile'].search(profile_domain, limit=1)
        if not profile:
            # Fallback to any profile
            profile = self.env['vin.commission.rule.profile'].search([], limit=1)

        base_rate = Decimal(str(profile.base_take_rate if profile else 15.0))
        effective_rate = base_rate
        discounts = []

        # 2. Check Volume Tiers
        if profile and profile.tier_line_ids:
            for tier in profile.tier_line_ids:
                min_v = Decimal(str(tier.min_volume))
                max_v = Decimal(str(tier.max_volume))
                if amount_dec >= min_v and (max_v == Decimal('0.0') or amount_dec <= max_v):
                    effective_rate = Decimal(str(tier.take_rate))
                    discounts.append(f"Volume Tier '{tier.name}': Rate set to {effective_rate}%")
                    break

        # 3. Client Subscription Discount
        if client_org_id:
            client_sub = self.env['vin.subscription'].search([
                ('client_organization_id', '=', client_org_id),
                ('state', '=', 'active')
            ], limit=1)
            if client_sub and client_sub.plan_id.take_rate_commission_discount > 0.0:
                disc = Decimal(str(client_sub.plan_id.take_rate_commission_discount))
                effective_rate -= disc
                discounts.append(f"Client Plan '{client_sub.plan_id.name}': -{disc}% Take-Rate Discount")

        # 4. Partner Subscription Discount
        if partner_profile_id:
            partner_sub = self.env['vin.subscription'].search([
                ('partner_profile_id', '=', partner_profile_id),
                ('state', '=', 'active')
            ], limit=1)
            if partner_sub and partner_sub.plan_id.take_rate_commission_discount > 0.0:
                disc = Decimal(str(partner_sub.plan_id.take_rate_commission_discount))
                effective_rate -= disc
                discounts.append(f"Partner Plan '{partner_sub.plan_id.name}': -{disc}% Take-Rate Discount")

        # Floor commission rate at 3.0%
        if effective_rate < Decimal('3.00'):
            effective_rate = Decimal('3.00')
            discounts.append("Platform Minimum Rate Floor: 3.0% applied")

        # 5. Compute Fee
        raw_fee = (amount_dec * (effective_rate / Decimal('100.0'))).quantize(Decimal('0.01'))

        # 6. Apply Min and Max Boundaries
        min_fee = Decimal(str(profile.min_commission_amount if profile else 25.0))
        max_fee = Decimal(str(profile.max_commission_cap if profile and profile.max_commission_cap > 0 else 0.0))

        if raw_fee < min_fee:
            fee = min_fee
            discounts.append(f"Minimum Fee Floor: Adjusted to {fee}")
        elif max_fee > Decimal('0.0') and raw_fee > max_fee:
            fee = max_fee
            discounts.append(f"Maximum Fee Cap: Capped at {fee}")
        else:
            fee = raw_fee

        partner_gross = amount_dec - fee

        return {
            'contract_amount': amount_dec,
            'base_rate': base_rate,
            'effective_take_rate': effective_rate,
            'platform_fee': fee,
            'partner_gross_before_tax': partner_gross,
            'applied_discounts': discounts,
            'profile_code': profile.code if profile else 'DEFAULT'
        }
