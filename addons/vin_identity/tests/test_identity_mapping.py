# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestIdentityMapping(TransactionCase):
    """Test suite for external identity federation and KYC/KYB approval segregation."""

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.User = self.env['res.users']
        self.IdLink = self.env['vin.identity.link']
        self.Verification = self.env['vin.identity.verification']

        self.tenant = self.Tenant.create({
            'code': 'TENANT_IDP',
            'name': 'Identity Tenant'
        })
        self.applicant = self.User.create({
            'name': 'Creator Applicant',
            'login': 'applicant@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]
        })
        self.compliance_officer = self.User.create({
            'name': 'Officer Compliance',
            'login': 'compliance@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]
        })

    def test_identity_federation_uniqueness(self):
        """External sub must be unique per IdP provider."""
        self.IdLink.create({
            'user_id': self.applicant.id,
            'tenant_id': self.tenant.id,
            'idp_provider': 'google',
            'external_sub': 'google-oauth2|123456789'
        })

        with self.assertRaises(Exception):
            self.IdLink.create({
                'user_id': self.compliance_officer.id,
                'tenant_id': self.tenant.id,
                'idp_provider': 'google',
                'external_sub': 'google-oauth2|123456789'
            })

    def test_verification_sod_enforcement(self):
        """Applicant cannot approve their own KYC/KYB submission."""
        case = self.Verification.with_user(self.applicant).create({
            'user_id': self.applicant.id,
            'tenant_id': self.tenant.id,
            'verification_level': 'tier_1_individual_kyc',
            'id_document_type': 'ktp',
            'evidence_vault_ref': 'VAULT-SHA256-KTP-DOCUMENT-HASH'
        })

        # Self-approval MUST fail
        with self.assertRaises(UserError):
            case.with_user(self.applicant).action_approve_verification()

        # Approval by compliance officer succeeds
        case.with_user(self.compliance_officer).action_approve_verification()
        self.assertEqual(case.status, 'verified')
        self.assertEqual(case.reviewed_by_id.id, self.compliance_officer.id)
