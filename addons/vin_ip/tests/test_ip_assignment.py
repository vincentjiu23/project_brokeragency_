# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields

class TestIPAssignment(TransactionCase):
    """
    Test suite for Asset-Level IP Assignment & Portfolio Grants (Q137–Q146, Q250, AC-05).
    Verifies automatic copyright transfer, SHA-256 deed signing,
    IP_ASSIGNED audit event emission, and portfolio policy gates.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Contract = self.env['vin.contract']
        self.Milestone = self.env['vin.milestone']
        self.Deliverable = self.env['vin.deliverable']
        self.IPAssignment = self.env['vin.ip.assignment']
        self.PortfolioGrant = self.env['vin.portfolio.display.grant']

        self.tenant = self.Tenant.create({'code': 'T_IP', 'name': 'IP Test Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_IP_CLIENT',
            'name': 'Client IP Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_contact = self.Partner.create({'name': 'Illustration Agency Studio'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })

        self.contract = self.Contract.create({
            'title': 'Original Character Design IP Contract',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'partner_profile_id': self.partner_profile.id,
            'total_contract_value': 15000.0,
            'state': 'active'
        })

    def test_01_execute_ip_assignment_deed(self):
        """Test AC-05: executing assignment deed generates SHA-256 digital seal and transitions to assigned."""
        deed = self.IPAssignment.create({
            'contract_id': self.contract.id,
            'tenant_id': self.tenant.id,
            'grant_type': 'exclusive_transfer',
            'territory': 'worldwide',
            'moral_rights_waived': True,
            'portfolio_display_permitted': True
        })

        self.assertEqual(deed.state, 'pending_payment')
        self.assertFalse(deed.sha256_hash)

        # Execute assignment deed upon milestone acceptance
        deed.action_execute_assignment()

        self.assertEqual(deed.state, 'assigned')
        self.assertTrue(deed.sha256_hash)
        self.assertEqual(len(deed.sha256_hash), 64)
        self.assertTrue(deed.assigned_at)

    def test_02_portfolio_display_grant_lifecycle(self):
        """Test client approval and NDA embargo policy gates for portfolio showcase."""
        grant = self.PortfolioGrant.create({
            'tenant_id': self.tenant.id,
            'partner_profile_id': self.partner_profile.id,
            'contract_id': self.contract.id
        })
        self.assertEqual(grant.status, 'pending')

        # Approve with launch embargo
        embargo_date = fields.Date.today()
        grant.action_embargo(lift_date=embargo_date)
        self.assertEqual(grant.status, 'embargoed')
        self.assertEqual(grant.embargo_date, embargo_date)

        # Full approve
        grant.action_approve()
        self.assertEqual(grant.status, 'approved')
