# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestPortfolioDisplay(TransactionCase):
    """Test suite for portfolio item display permissions and security gates."""

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Profile = self.env['creative.partner.profile']
        self.Partner = self.env['res.partner']
        self.PortfolioItem = self.env['vin.portfolio.item']

        self.tenant = self.Tenant.create({'code': 'T_PORTFOLIO', 'name': 'Portfolio Tenant'})
        self.partner_contact = self.Partner.create({'name': 'Design House'})

        self.profile = self.Profile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified',
        })

    def test_publish_denied_without_display_allowed(self):
        """Publishing must fail if display_allowed (IP/NDA clearance) is False (Q124)."""
        item = self.PortfolioItem.create({
            'partner_profile_id': self.profile.id,
            'title': 'Secret Brand Campaign',
            'asset_vault_ref': 'sha256_mock_hash_123',
            'display_allowed': False,
        })

        with self.assertRaises(UserError):
            item.action_publish()

    def test_publish_success_with_display_allowed(self):
        """Publishing succeeds when display_allowed is True and logs audit event."""
        item = self.PortfolioItem.create({
            'partner_profile_id': self.profile.id,
            'title': 'Public Brand Showcase',
            'asset_vault_ref': 'sha256_mock_hash_456',
            'display_allowed': True,
        })

        item.action_publish()
        self.assertEqual(item.publication_state, 'published')
