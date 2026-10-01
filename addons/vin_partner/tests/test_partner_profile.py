# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessDenied

class TestPartnerProfile(TransactionCase):
    """Test suite for creative partner profile creation and public projection safety."""

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Profile = self.env['creative.partner.profile']
        self.Partner = self.env['res.partner']

        self.tenant = self.Tenant.create({'code': 'T_PARTNER', 'name': 'Partner Tenant'})
        self.partner_contact = self.Partner.create({'name': 'Studio Alpha Creative'})

        self.profile = self.Profile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'pending',
            'internal_trust_score': 92.5,
        })

    def test_public_projection_excludes_internal_trust(self):
        """Public profile projection must never expose internal_trust_score."""
        from ..services.public_profile_projection import PartnerProfileProjectionService
        svc = PartnerProfileProjectionService(self.env)

        # Profile must be verified first
        self.profile.action_verify_partner()
        projection = svc.get_public_projection(self.profile.uuid)

        self.assertIn('public_rating', projection)
        self.assertNotIn('internal_trust_score', projection)
        self.assertNotIn('bank_account', projection)

    def test_unverified_profile_not_projectable(self):
        """Unverified profiles cannot be projected publicly."""
        from ..services.public_profile_projection import PartnerProfileProjectionService
        svc = PartnerProfileProjectionService(self.env)

        with self.assertRaises(AccessDenied):
            svc.get_public_projection(self.profile.uuid)
