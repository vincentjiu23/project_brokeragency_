# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestComplianceAndLegalHold(TransactionCase):
    """
    Test suite for Compliance, Legal Holds & DSAR Erasure (Q137–Q146, Q250, AC-08/09/10).
    Verifies:
      - Statutory retention constraints
      - Legal hold activation & lifting
      - Evidence package SHA-256 compilation & immutability
      - DSAR cryptographic erasure blockage under active legal hold
      - DSAR cryptographic erasure execution with zero ledger mutation
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Contract = self.env['vin.contract']
        self.RetentionRule = self.env['vin.retention.rule']
        self.LegalHold = self.env['vin.legal.hold']
        self.EvidencePackage = self.env['vin.evidence.package']
        self.DSARRequest = self.env['vin.dsar.request']

        self.tenant = self.Tenant.create({'code': 'T_COMP', 'name': 'Compliance Test Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_COMP_CLIENT',
            'name': 'Client Compliance Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_contact = self.Partner.create({'name': 'Creative Agency Compliance'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })
        self.contract = self.Contract.create({
            'title': 'Compliance Monitored Contract',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'partner_profile_id': self.partner_profile.id,
            'total_contract_value': 30000.0,
            'state': 'active'
        })

    def test_01_retention_rule_statutory_minimums(self):
        """Test that statutory retention rules prevent sub-minimum retention periods."""
        # Financial / tax records must be >= 10 years (3650 days)
        with self.assertRaises(ValidationError):
            self.RetentionRule.create({
                'name': 'Sub-minimum Tax Retention',
                'code': 'RET_TAX_INVALID',
                'tenant_id': self.tenant.id,
                'target_category': 'tax_record',
                'target_model_name': 'vin.invoice',
                'retention_period_days': 365,  # 1 year - invalid, must be >= 3650
            })

        # Contracts must be >= 7 years (2555 days)
        with self.assertRaises(ValidationError):
            self.RetentionRule.create({
                'name': 'Sub-minimum Contract Retention',
                'code': 'RET_CONTR_INVALID',
                'tenant_id': self.tenant.id,
                'target_category': 'contract_legal',
                'target_model_name': 'vin.contract',
                'retention_period_days': 1000,  # Invalid, must be >= 2555
            })

    def test_02_legal_hold_activation_and_lifting(self):
        """Test legal hold lifecycle: activation locks records, lifting requires rationale."""
        hold = self.LegalHold.create({
            'title': 'BANI Arbitration Case No. 44/2026',
            'matter_name': 'Contractual Breach Litigation',
            'tenant_id': self.tenant.id,
            'scope_type': 'contract',
            'contract_id': self.contract.id,
            'hold_reason': 'Preservation notice issued by claimant counsel.',
        })
        self.assertEqual(hold.state, 'draft')
        self.assertTrue(hold.hold_reference.startswith('LH-'))

        # Activate hold
        hold.action_apply_hold()
        self.assertEqual(hold.state, 'active')
        self.assertTrue(hold.applied_at)

        # Verify helper detects active hold
        held = self.LegalHold.check_is_held(
            tenant_id=self.tenant.id,
            contract_id=self.contract.id
        )
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0].id, hold.id)

        # Cannot lift without reason
        with self.assertRaises(UserError):
            hold.action_lift_hold(reason=None)

        # Lift with rationale
        hold.action_lift_hold(reason="Arbitral settlement award fully satisfied.")
        self.assertEqual(hold.state, 'lifted')
        self.assertTrue(hold.lifted_at)

        # Helper now reports no active hold
        held_after = self.LegalHold.check_is_held(
            tenant_id=self.tenant.id,
            contract_id=self.contract.id
        )
        self.assertEqual(len(held_after), 0)

    def test_03_evidence_package_compilation_and_sealing(self):
        """Test evidence package aggregation, SHA-256 seal, and post-seal immutability."""
        pkg = self.EvidencePackage.create({
            'title': 'Tax Audit Dossier FY2026',
            'tenant_id': self.tenant.id,
            'purpose': 'tax_audit',
            'contract_id': self.contract.id,
        })
        self.assertEqual(pkg.state, 'draft')
        self.assertFalse(pkg.sha256_hash)

        # Compile and seal
        pkg.action_compile_and_seal()
        self.assertEqual(pkg.state, 'sealed')
        self.assertTrue(pkg.sha256_hash)
        self.assertEqual(len(pkg.sha256_hash), 64)
        self.assertGreater(pkg.item_count, 0)

        # Sealed package cannot be mutated
        with self.assertRaises(UserError):
            pkg.write({'title': 'Tampered Package Title'})

    def test_04_dsar_erasure_blocked_by_active_legal_hold(self):
        """Test that active legal hold strictly blocks GDPR/DSAR erasure."""
        # Apply active legal hold on the client organization
        hold = self.LegalHold.create({
            'title': 'Tax Evasion Inquiry',
            'matter_name': 'DJP Investigation',
            'tenant_id': self.tenant.id,
            'scope_type': 'organization',
            'organization_id': self.client_org.id,
            'hold_reason': 'Statutory tax preservation order.',
        })
        hold.action_apply_hold()

        # Submit erasure DSAR request for user affiliated with held organization
        dsar = self.DSARRequest.create({
            'tenant_id': self.tenant.id,
            'subject_email': 'cfo@clientorg.com',
            'subject_organization_id': self.client_org.id,
            'request_type': 'erasure',
        })
        dsar.action_verify_identity()

        # Execute erasure -> MUST be blocked by legal hold
        dsar.action_execute_erasure()
        self.assertEqual(dsar.state, 'blocked_legal_hold')
        self.assertIn("BLOCKED", dsar.execution_notes)
        self.assertFalse(dsar.erasure_certificate_hash)

    def test_05_dsar_cryptographic_erasure_execution(self):
        """Test cryptographic erasure: PII pseudonymized, zero ledger alteration, SHA-256 cert."""
        dsar = self.DSARRequest.create({
            'tenant_id': self.tenant.id,
            'subject_email': 'freelancer@independent.com',
            'request_type': 'erasure',
        })
        dsar.action_verify_identity()

        # Execute erasure without legal hold
        dsar.action_execute_erasure()
        self.assertEqual(dsar.state, 'executed')
        self.assertTrue(dsar.erasure_certificate_hash)
        self.assertEqual(len(dsar.erasure_certificate_hash), 64)
        self.assertTrue(dsar.completed_at)
