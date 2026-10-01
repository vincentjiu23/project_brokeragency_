# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestIPTransferService(TransactionCase):
    """
    Test suite for IP Transfer Orchestration Service (Q137–Q146, AC-05).
    Validates payment-gated IP transfer, auto portfolio grant creation,
    and chargeback revocation workflows.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Contract = self.env['vin.contract']
        self.IPAssignment = self.env['vin.ip.assignment']
        self.PortfolioGrant = self.env['vin.portfolio.display.grant']
        self.TransferService = self.env['vin.ip.transfer.service']

        self.tenant = self.Tenant.create({'code': 'T_IP_SVC', 'name': 'IP Service Test Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_IP_SVC_CLIENT',
            'name': 'Client Transfer Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_contact = self.Partner.create({'name': 'Design Studio Partner'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })
        self.contract = self.Contract.create({
            'title': 'Brand Identity Design Contract',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'partner_profile_id': self.partner_profile.id,
            'total_contract_value': 25000.0,
            'state': 'active'
        })

    def test_01_execute_transfer_basic(self):
        """Test basic IP transfer execution via service layer."""
        deed = self.IPAssignment.create({
            'contract_id': self.contract.id,
            'tenant_id': self.tenant.id,
            'grant_type': 'exclusive_transfer',
            'territory': 'worldwide',
            'portfolio_display_permitted': True,
        })

        result = self.TransferService.execute_transfer(deed.id)

        self.assertEqual(result['state'], 'assigned')
        self.assertTrue(result['sha256_hash'])
        self.assertEqual(len(result['sha256_hash']), 64)
        self.assertTrue(result['portfolio_grant_id'])

    def test_02_auto_portfolio_grant_with_embargo(self):
        """Test portfolio grant auto-created with embargo date."""
        embargo = fields.Date.today()
        deed = self.IPAssignment.create({
            'contract_id': self.contract.id,
            'tenant_id': self.tenant.id,
            'grant_type': 'perpetual_license',
            'territory': 'worldwide',
            'portfolio_display_permitted': True,
            'portfolio_embargo_date': embargo,
        })

        result = self.TransferService.execute_transfer(deed.id)

        self.assertEqual(result['portfolio_grant_status'], 'embargoed')
        grant = self.PortfolioGrant.browse(result['portfolio_grant_id'])
        self.assertEqual(grant.embargo_date, embargo)

    def test_03_no_portfolio_grant_when_not_permitted(self):
        """Test no portfolio grant created when display is not permitted."""
        deed = self.IPAssignment.create({
            'contract_id': self.contract.id,
            'tenant_id': self.tenant.id,
            'grant_type': 'work_made_for_hire',
            'territory': 'worldwide',
            'portfolio_display_permitted': False,
        })

        result = self.TransferService.execute_transfer(deed.id)

        self.assertIsNone(result['portfolio_grant_id'])
        self.assertIsNone(result['portfolio_grant_status'])

    def test_04_revoke_on_chargeback(self):
        """Test chargeback revocation cascades to portfolio grants."""
        deed = self.IPAssignment.create({
            'contract_id': self.contract.id,
            'tenant_id': self.tenant.id,
            'grant_type': 'exclusive_transfer',
            'territory': 'worldwide',
            'portfolio_display_permitted': True,
        })

        # Execute transfer first
        self.TransferService.execute_transfer(deed.id)
        self.assertEqual(deed.state, 'assigned')

        # Revoke on chargeback
        self.TransferService.revoke_on_chargeback(
            deed.id,
            reason="Fraudulent chargeback detected"
        )
        self.assertEqual(deed.state, 'revoked')

        # Verify portfolio grants are also revoked
        grants = self.PortfolioGrant.search([
            ('contract_id', '=', self.contract.id),
            ('partner_profile_id', '=', self.partner_profile.id),
        ])
        for grant in grants:
            self.assertEqual(grant.status, 'rejected_nda')

    def test_05_cannot_transfer_already_assigned(self):
        """Test cannot execute transfer on already assigned deed."""
        deed = self.IPAssignment.create({
            'contract_id': self.contract.id,
            'tenant_id': self.tenant.id,
            'grant_type': 'exclusive_transfer',
            'territory': 'worldwide',
        })
        self.TransferService.execute_transfer(deed.id)

        with self.assertRaises(UserError):
            self.TransferService.execute_transfer(deed.id)
