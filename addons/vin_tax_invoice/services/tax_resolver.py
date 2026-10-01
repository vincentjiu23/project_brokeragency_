# -*- coding: utf-8 -*-
"""
Tax Resolver Service (Q129–Q136, Q210).
Determines exact multi-jurisdiction tax obligations (VAT/PPN and WHT/PPh)
based on client/partner tax residency, PKP registration, and international tax treaties.
"""
from decimal import Decimal
import logging
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class TaxResolverService:
    """Dynamic multi-jurisdiction tax calculation engine."""

    def __init__(self, env):
        self.env = env

    def resolve_transaction_taxes(self, amount, client_org_id=None, partner_profile_id=None, currency='USD'):
        """
        Resolves VAT and WHT for a given transaction amount.

        Args:
            amount (float or Decimal): Base contract or milestone amount.
            client_org_id (int): vin.organization ID.
            partner_profile_id (int): creative.partner.profile ID.
            currency (str): Currency code (default 'USD').

        Returns:
            dict containing:
                - base_amount: Decimal
                - vat_rate: Decimal (%)
                - vat_amount: Decimal
                - wht_rate: Decimal (%)
                - wht_amount: Decimal
                - client_payable: Decimal (base + vat)
                - partner_net_payout: Decimal (base - wht)
                - tax_profile_id: int or None
                - applied_rule: str
        """
        base_dec = Decimal(str(amount))
        if base_dec <= Decimal('0.00'):
            raise UserError(_("Tax calculation requires a positive transaction amount."))

        client_org = self.env['vin.organization'].browse(client_org_id) if client_org_id else None
        partner = self.env['creative.partner.profile'].browse(partner_profile_id) if partner_profile_id else None

        # Look up tax profiles
        partner_tax_profile = None
        if partner:
            partner_tax_profile = self.env['vin.tax.profile'].search([
                ('partner_profile_id', '=', partner.id),
                ('status', '=', 'verified')
            ], limit=1)
            if not partner_tax_profile:
                # Fallback to draft/any profile
                partner_tax_profile = self.env['vin.tax.profile'].search([
                    ('partner_profile_id', '=', partner.id)
                ], limit=1)

        client_tax_profile = None
        if client_org:
            client_tax_profile = self.env['vin.tax.profile'].search([
                ('organization_id', '=', client_org.id),
                ('status', '=', 'verified')
            ], limit=1)

        # Default standard rates
        vat_rate = Decimal('11.00')  # Default 11% PPN
        wht_rate = Decimal('2.00')   # Default 2% PPh 23
        applied_rule = "DOMESTIC_B2B_STANDARD"

        # Determine Partner Withholding Tax (WHT)
        if partner_tax_profile:
            jurisdiction = partner_tax_profile.jurisdiction
            entity_type = partner_tax_profile.entity_type
            wht_article = partner_tax_profile.wht_article

            if jurisdiction == 'ID':
                if entity_type == 'corporate':
                    wht_rate = Decimal(str(partner_tax_profile.default_wht_rate or 2.0))
                    applied_rule = "ID_PPH_23_CORPORATE_2PCT"
                elif entity_type == 'individual_freelance':
                    if partner_tax_profile.has_npwp:
                        wht_rate = Decimal('2.50')  # Effective DPP 50% * 5% minimum tier
                        applied_rule = "ID_PPH_21_FREELANCER_WITH_NPWP"
                    else:
                        wht_rate = Decimal('3.00')  # 120% penalty without NPWP
                        applied_rule = "ID_PPH_21_FREELANCER_NO_NPWP_PENALTY"
                elif entity_type == 'individual_business':
                    wht_rate = Decimal('0.50')  # PP 23 UMKM 0.5% final
                    applied_rule = "ID_PP_23_UMKM_FINAL_0_5PCT"
            elif jurisdiction in ['US', 'SG', 'GB', 'EU', 'OTHER']:
                if wht_article == 'pph_26_treaty':
                    wht_rate = Decimal('10.00')  # DGT Form Tax Treaty
                    applied_rule = f"{jurisdiction}_TAX_TREATY_REDUCED_10PCT"
                elif wht_article == 'zero_rated':
                    wht_rate = Decimal('0.00')
                    applied_rule = f"{jurisdiction}_TAX_EXEMPT_ZERO_RATED"
                else:
                    wht_rate = Decimal('20.00')  # PPh 26 Non-resident standard
                    applied_rule = f"{jurisdiction}_NON_RESIDENT_PPH26_20PCT"

        # Determine Client VAT (PPN)
        if client_tax_profile:
            if not client_tax_profile.vat_registered:
                vat_rate = Decimal('0.00')
                applied_rule += "_CLIENT_NON_PKP"
            elif client_tax_profile.jurisdiction != 'ID':
                # Export of services
                vat_rate = Decimal('0.00')
                applied_rule += "_EXPORT_SERVICE_ZERO_VAT"
            else:
                vat_rate = Decimal(str(client_tax_profile.default_vat_rate or 11.0))

        # Compute exact amounts
        vat_amount = (base_dec * (vat_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
        wht_amount = (base_dec * (wht_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
        client_payable = (base_dec + vat_amount).quantize(Decimal('0.01'))
        partner_net_payout = (base_dec - wht_amount).quantize(Decimal('0.01'))

        return {
            'base_amount': base_dec,
            'vat_rate': vat_rate,
            'vat_amount': vat_amount,
            'wht_rate': wht_rate,
            'wht_amount': wht_amount,
            'client_payable': client_payable,
            'partner_net_payout': partner_net_payout,
            'tax_profile_id': partner_tax_profile.id if partner_tax_profile else (client_tax_profile.id if client_tax_profile else None),
            'applied_rule': applied_rule
        }
