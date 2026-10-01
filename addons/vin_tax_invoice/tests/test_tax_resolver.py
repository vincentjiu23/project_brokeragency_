# -*- coding: utf-8 -*-
from decimal import Decimal
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields

class TestTaxResolver(TransactionCase):
    """
    Test suite for Multi-Jurisdiction Tax & Invoicing (Q129–Q136, Q210).
    Validates VAT/PPN, WHT/PPh calculation accuracy, freelancer NPWP penalty rules,
    digital SHA-256 invoice signatures, and Bukti Potong generation.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.TaxProfile = self.env['vin.tax.profile']
        self.Invoice = self.env['vin.invoice']
        self.InvoiceLine = self.env['vin.invoice.line']
        self.TaxCertificate = self.env['vin.tax.certificate']
        self.TaxService = self.env['vin.tax.invoice.service'] if 'vin.tax.invoice.service' in self.env else None

        self.tenant = self.Tenant.create({'code': 'T_TAX', 'name': 'Tax Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_TAX_CLIENT',
            'name': 'Client Tax Org PT',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_contact = self.Partner.create({'name': 'Creative Agency PT'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })

        # Client Tax Profile (Corporate PKP)
        self.client_tax = self.TaxProfile.create({
            'name': 'Client Corporate Tax Profile',
            'tenant_id': self.tenant.id,
            'organization_id': self.client_org.id,
            'tax_id_number': '01.345.678.9-011.000',
            'jurisdiction': 'ID',
            'entity_type': 'corporate',
            'vat_registered': True,
            'default_vat_rate': 11.0,
            'status': 'verified'
        })

        # Partner Tax Profile (Corporate Domestic PKP)
        self.partner_tax = self.TaxProfile.create({
            'name': 'Partner Corporate Tax Profile',
            'tenant_id': self.tenant.id,
            'partner_profile_id': self.partner_profile.id,
            'tax_id_number': '02.987.654.3-022.000',
            'jurisdiction': 'ID',
            'entity_type': 'corporate',
            'vat_registered': True,
            'default_vat_rate': 11.0,
            'default_wht_rate': 2.0,
            'wht_article': 'pph_23',
            'status': 'verified'
        })

    def test_01_tax_resolver_corporate_b2b(self):
        """Test standard Indonesian domestic B2B: 11% PPN & 2% PPh 23."""
        from ..services.tax_resolver import TaxResolverService
        resolver = TaxResolverService(self.env)
        
        result = resolver.resolve_transaction_taxes(
            amount=10000.0,
            client_org_id=self.client_org.id,
            partner_profile_id=self.partner_profile.id
        )

        self.assertEqual(result['vat_rate'], Decimal('11.00'))
        self.assertEqual(result['vat_amount'], Decimal('1100.00'))
        self.assertEqual(result['wht_rate'], Decimal('2.00'))
        self.assertEqual(result['wht_amount'], Decimal('200.00'))
        self.assertEqual(result['client_payable'], Decimal('11100.00'))
        self.assertEqual(result['partner_net_payout'], Decimal('9800.00'))

    def test_02_individual_freelancer_with_and_without_npwp(self):
        """Test freelancer PPh 21: normal rate vs penalty multiplier."""
        from ..services.tax_resolver import TaxResolverService
        resolver = TaxResolverService(self.env)

        # Freelancer with NPWP
        freelancer_contact = self.Partner.create({'name': 'Freelance Designer'})
        freelancer_profile = self.PartnerProfile.create({
            'partner_id': freelancer_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'individual',
            'verification_status': 'verified'
        })
        self.TaxProfile.create({
            'name': 'Freelancer Tax with NPWP',
            'tenant_id': self.tenant.id,
            'partner_profile_id': freelancer_profile.id,
            'tax_id_number': '09.111.222.3-444.000',
            'jurisdiction': 'ID',
            'entity_type': 'individual_freelance',
            'vat_registered': False,
            'status': 'verified'
        })

        res_npwp = resolver.resolve_transaction_taxes(amount=5000.0, partner_profile_id=freelancer_profile.id)
        self.assertEqual(res_npwp['wht_rate'], Decimal('2.50'))
        self.assertEqual(res_npwp['wht_amount'], Decimal('125.00'))

        # Freelancer WITHOUT NPWP (penalty)
        freelancer_no_npwp_profile = self.PartnerProfile.create({
            'partner_id': self.Partner.create({'name': 'No NPWP Freelancer'}).id,
            'tenant_id': self.tenant.id,
            'account_type': 'individual',
            'verification_status': 'verified'
        })
        self.TaxProfile.create({
            'name': 'Freelancer Tax No NPWP',
            'tenant_id': self.tenant.id,
            'partner_profile_id': freelancer_no_npwp_profile.id,
            'tax_id_number': '',
            'jurisdiction': 'ID',
            'entity_type': 'individual_freelance',
            'vat_registered': False,
            'status': 'verified'
        })
        res_no_npwp = resolver.resolve_transaction_taxes(amount=5000.0, partner_profile_id=freelancer_no_npwp_profile.id)
        self.assertEqual(res_no_npwp['wht_rate'], Decimal('3.00'))
        self.assertEqual(res_no_npwp['wht_amount'], Decimal('150.00'))

    def test_03_invoice_issuance_and_digital_signature(self):
        """Test invoice creation, line items, totals calculation, and SHA-256 digital sealing."""
        invoice = self.Invoice.create({
            'tenant_id': self.tenant.id,
            'invoice_type': 'client_milestone',
            'client_organization_id': self.client_org.id,
            'currency': 'USD',
            'issue_date': fields.Date.today()
        })
        self.InvoiceLine.create({
            'invoice_id': invoice.id,
            'description': 'Brand Identity Phase 1 Deliverables',
            'quantity': 1.0,
            'unit_price': 10000.0,
            'vat_rate': 11.0,
            'wht_rate': 2.0
        })

        self.assertEqual(invoice.subtotal_amount, 10000.0)
        self.assertEqual(invoice.vat_amount, 1100.0)
        self.assertEqual(invoice.gross_total, 11100.0)
        self.assertEqual(invoice.wht_amount, 200.0)
        self.assertEqual(invoice.net_payable, 10900.0)

        # Issue and verify digital seal
        invoice.action_issue()
        self.assertEqual(invoice.state, 'issued')
        self.assertTrue(invoice.digital_signature_hash)
        self.assertEqual(len(invoice.digital_signature_hash), 64)

    def test_04_tax_certificate_bukti_potong_issuance(self):
        """Test Bukti Potong generation and cryptographic signature."""
        cert = self.TaxCertificate.create({
            'tenant_id': self.tenant.id,
            'tax_profile_id': self.partner_tax.id,
            'partner_profile_id': self.partner_profile.id,
            'tax_year': 2026,
            'tax_period': '05',
            'withheld_party_name': 'Creative Agency PT',
            'withheld_party_tax_id': '02.987.654.3-022.000',
            'tax_article': 'PPh Pasal 23 (2%)',
            'gross_amount': 20000.0,
            'tax_rate': 2.0,
            'tax_withheld_amount': 400.0
        })

        self.assertEqual(cert.state, 'draft')
        cert.action_generate_and_sign()
        self.assertEqual(cert.state, 'generated')
        self.assertTrue(cert.sha256_hash)
        self.assertTrue(cert.signature_date)
