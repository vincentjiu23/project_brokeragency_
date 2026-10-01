# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestReputationReview(TransactionCase):
    """
    Test suite for Public Peer Reviews (Q137–Q146 Reputation Domain).
    Validates dual-blind reveal mechanism, SHA-256 sealing, rating bounds,
    moderation lifecycle, and append-only immutability.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Contract = self.env['vin.contract']
        self.Review = self.env['vin.review']

        self.tenant = self.Tenant.create({'code': 'T_REP', 'name': 'Reputation Test Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_REP_CLIENT',
            'name': 'Client Review Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_org = self.Organization.create({
            'code': 'ORG_REP_PARTNER',
            'name': 'Partner Review Org',
            'tenant_id': self.tenant.id,
            'org_type': 'partner'
        })
        self.partner_contact = self.Partner.create({'name': 'UX Studio'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })
        self.contract = self.Contract.create({
            'title': 'UX Design Project for Review',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'partner_profile_id': self.partner_profile.id,
            'total_contract_value': 10000.0,
            'state': 'completed'
        })

    def test_01_review_sealed_on_creation(self):
        """Test that a single review is sealed until counter-party submits."""
        review = self.Review.create({
            'tenant_id': self.tenant.id,
            'contract_id': self.contract.id,
            'reviewer_organization_id': self.client_org.id,
            'reviewee_partner_id': self.partner_profile.id,
            'review_direction': 'client_to_partner',
            'overall_rating': 4.5,
            'quality_rating': 5.0,
            'communication_rating': 4.0,
            'public_comment': 'Excellent design work, highly recommended.',
        })

        self.assertEqual(review.state, 'sealed')
        self.assertTrue(review.sha256_hash)
        self.assertEqual(len(review.sha256_hash), 64)
        self.assertFalse(review.counterpart_review_id)

    def test_02_dual_blind_reveal(self):
        """Test dual-blind reveal when both parties submit reviews."""
        # Client → Partner review
        client_review = self.Review.create({
            'tenant_id': self.tenant.id,
            'contract_id': self.contract.id,
            'reviewer_organization_id': self.client_org.id,
            'reviewee_partner_id': self.partner_profile.id,
            'review_direction': 'client_to_partner',
            'overall_rating': 4.5,
            'public_comment': 'Great creative work.',
        })
        self.assertEqual(client_review.state, 'sealed')

        # Partner → Client review (triggers reveal)
        partner_review = self.Review.create({
            'tenant_id': self.tenant.id,
            'contract_id': self.contract.id,
            'reviewer_organization_id': self.partner_org.id,
            'reviewee_organization_id': self.client_org.id,
            'review_direction': 'partner_to_client',
            'overall_rating': 4.0,
            'public_comment': 'Professional client, clear briefs.',
        })

        # Both should be revealed
        client_review.refresh()
        self.assertEqual(client_review.state, 'revealed')
        self.assertEqual(partner_review.state, 'revealed')
        self.assertTrue(client_review.revealed_at)
        self.assertTrue(partner_review.revealed_at)
        self.assertEqual(client_review.counterpart_review_id.id, partner_review.id)
        self.assertEqual(partner_review.counterpart_review_id.id, client_review.id)

    def test_03_rating_bounds_enforcement(self):
        """Test that ratings outside 1.0–5.0 are rejected."""
        with self.assertRaises(ValidationError):
            self.Review.create({
                'tenant_id': self.tenant.id,
                'contract_id': self.contract.id,
                'reviewer_organization_id': self.client_org.id,
                'reviewee_partner_id': self.partner_profile.id,
                'review_direction': 'client_to_partner',
                'overall_rating': 6.0,  # Invalid
            })

        with self.assertRaises(ValidationError):
            self.Review.create({
                'tenant_id': self.tenant.id,
                'contract_id': self.contract.id,
                'reviewer_organization_id': self.client_org.id,
                'reviewee_partner_id': self.partner_profile.id,
                'review_direction': 'client_to_partner',
                'overall_rating': 0.5,  # Invalid
            })

    def test_04_review_immutability_after_seal(self):
        """Test that sealed reviews cannot be modified (append-only)."""
        review = self.Review.create({
            'tenant_id': self.tenant.id,
            'contract_id': self.contract.id,
            'reviewer_organization_id': self.client_org.id,
            'reviewee_partner_id': self.partner_profile.id,
            'review_direction': 'client_to_partner',
            'overall_rating': 4.0,
            'public_comment': 'Good work.',
        })

        with self.assertRaises(UserError):
            review.write({'overall_rating': 5.0})

        with self.assertRaises(UserError):
            review.write({'public_comment': 'Changed my mind.'})

    def test_05_moderation_lifecycle(self):
        """Test flag and redact moderation workflow."""
        review = self.Review.create({
            'tenant_id': self.tenant.id,
            'contract_id': self.contract.id,
            'reviewer_organization_id': self.client_org.id,
            'reviewee_partner_id': self.partner_profile.id,
            'review_direction': 'client_to_partner',
            'overall_rating': 1.0,
            'public_comment': 'Abusive content.',
        })

        review.action_flag_for_moderation(reason="Inappropriate language")
        self.assertEqual(review.state, 'flagged')

        review.action_redact(moderator_note="Violates content policy.")
        self.assertEqual(review.state, 'redacted')

    def test_06_cannot_flag_redacted_review(self):
        """Test that redacted reviews cannot be re-flagged."""
        review = self.Review.create({
            'tenant_id': self.tenant.id,
            'contract_id': self.contract.id,
            'reviewer_organization_id': self.client_org.id,
            'reviewee_partner_id': self.partner_profile.id,
            'review_direction': 'client_to_partner',
            'overall_rating': 2.0,
        })
        review.action_redact()

        with self.assertRaises(UserError):
            review.action_flag_for_moderation()


class TestTrustScoreCalculator(TransactionCase):
    """
    Test suite for Internal Trust Score Calculator (Q137–Q146).
    Validates trust event recording, time-decay score calculation,
    trust tier transitions, and public metric aggregation.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Contract = self.env['vin.contract']
        self.Calculator = self.env['vin.trust.score.calculator']
        self.ReputationScore = self.env['vin.reputation.score']
        self.TrustEvent = self.env['vin.trust.event']

        self.tenant = self.Tenant.create({'code': 'T_TRUST', 'name': 'Trust Test Tenant'})
        self.org = self.Organization.create({
            'code': 'ORG_TRUST',
            'name': 'Trusted Agency Org',
            'tenant_id': self.tenant.id,
            'org_type': 'partner'
        })
        self.partner_contact = self.Partner.create({'name': 'Trusted Agency'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })

    def test_01_record_positive_trust_event(self):
        """Test recording a positive trust event increases score above baseline."""
        event = self.Calculator.record_trust_event(
            tenant_id=self.tenant.id,
            event_type='milestone_on_time',
            event_category='delivery',
            subject_partner_id=self.partner_profile.id,
        )

        self.assertTrue(event)
        self.assertEqual(event.event_type, 'milestone_on_time')
        self.assertGreater(event.score_delta, 0)

        # Verify reputation score was created/updated
        score = self.ReputationScore.search([
            ('tenant_id', '=', self.tenant.id),
            ('partner_profile_id', '=', self.partner_profile.id),
        ])
        self.assertTrue(score)
        self.assertGreater(score.internal_trust_score, 500.0)  # Above baseline

    def test_02_record_negative_trust_event(self):
        """Test negative trust event decreases score below baseline."""
        self.Calculator.record_trust_event(
            tenant_id=self.tenant.id,
            event_type='chargeback_filed',
            event_category='payment',
            subject_partner_id=self.partner_profile.id,
        )

        score = self.ReputationScore.search([
            ('tenant_id', '=', self.tenant.id),
            ('partner_profile_id', '=', self.partner_profile.id),
        ])
        self.assertLess(score.internal_trust_score, 500.0)  # Below baseline

    def test_03_trust_tier_transitions(self):
        """Test that trust tier updates correctly based on score."""
        # Record many positive events to push to 'trusted' tier
        for _ in range(30):
            self.Calculator.record_trust_event(
                tenant_id=self.tenant.id,
                event_type='project_completed_successfully',
                event_category='platform',
                subject_partner_id=self.partner_profile.id,
            )

        score = self.ReputationScore.search([
            ('tenant_id', '=', self.tenant.id),
            ('partner_profile_id', '=', self.partner_profile.id),
        ])
        self.assertIn(score.trust_tier, ['trusted', 'elite'])
        self.assertGreaterEqual(score.internal_trust_score, 600.0)

    def test_04_trust_event_append_only(self):
        """Test that trust events cannot be modified or deleted."""
        event = self.Calculator.record_trust_event(
            tenant_id=self.tenant.id,
            event_type='kyc_verified',
            event_category='compliance',
            subject_partner_id=self.partner_profile.id,
        )

        # Cannot modify
        with self.assertRaises(ValidationError):
            event.write({'score_delta': 100.0})

        # Cannot delete
        with self.assertRaises(ValidationError):
            event.unlink()

    def test_05_trust_event_requires_subject(self):
        """Test that trust event must have at least one subject."""
        with self.assertRaises(ValidationError):
            self.TrustEvent.sudo().create({
                'tenant_id': self.tenant.id,
                'event_type': 'milestone_on_time',
                'event_category': 'delivery',
                'score_delta': 5.0,
                # No subject
            })

    def test_06_score_delta_range_validation(self):
        """Test that score delta exceeding ±100 is rejected."""
        with self.assertRaises(ValidationError):
            self.TrustEvent.sudo().create({
                'tenant_id': self.tenant.id,
                'event_type': 'milestone_on_time',
                'event_category': 'delivery',
                'subject_partner_id': self.partner_profile.id,
                'score_delta': 150.0,  # Exceeds max
            })

    def test_07_public_metrics_recalculation(self):
        """Test public metrics recomputation from revealed reviews."""
        Review = self.env['vin.review']
        client_org = self.Organization.create({
            'code': 'ORG_METRICS_CLIENT',
            'name': 'Metrics Client Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        contract = self.Contract.create({
            'title': 'Metrics Test Contract',
            'tenant_id': self.tenant.id,
            'client_organization_id': client_org.id,
            'partner_profile_id': self.partner_profile.id,
            'total_contract_value': 5000.0,
            'state': 'completed'
        })

        # Submit both reviews to trigger dual-blind reveal
        Review.create({
            'tenant_id': self.tenant.id,
            'contract_id': contract.id,
            'reviewer_organization_id': client_org.id,
            'reviewee_partner_id': self.partner_profile.id,
            'review_direction': 'client_to_partner',
            'overall_rating': 4.5,
            'quality_rating': 5.0,
            'communication_rating': 4.0,
        })
        Review.create({
            'tenant_id': self.tenant.id,
            'contract_id': contract.id,
            'reviewer_organization_id': self.org.id,
            'reviewee_organization_id': client_org.id,
            'review_direction': 'partner_to_client',
            'overall_rating': 4.0,
        })

        # Recalculate public metrics for the partner
        self.Calculator.recalculate_public_metrics(
            tenant_id=self.tenant.id,
            partner_id=self.partner_profile.id,
        )

        score = self.ReputationScore.search([
            ('tenant_id', '=', self.tenant.id),
            ('partner_profile_id', '=', self.partner_profile.id),
        ])
        self.assertEqual(score.total_reviews_received, 1)  # Only client→partner review
        self.assertEqual(score.public_avg_rating, 4.5)
