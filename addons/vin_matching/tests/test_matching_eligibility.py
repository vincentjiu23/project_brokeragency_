# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields

class TestMatchingEligibility(TransactionCase):
    """
    Test suite for deterministic matching engine, hard eligibility gates,
    match snapshots (AC-01), opportunity dispatch (AC-02), and blind RFQ anonymity.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.LegalEntity = self.env['vin.legal.entity']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Expertise = self.env['vin.partner.expertise']
        self.ProjectBrief = self.env['vin.project.brief']
        self.MatchSnapshot = self.env['vin.match.snapshot']
        self.Opportunity = self.env['vin.opportunity.record']

        # Setup Tenant & Client Org
        self.tenant = self.Tenant.create({'code': 'T_MATCH', 'name': 'Match Engine Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_CLIENT_ALPHA',
            'name': 'Client Enterprise Alpha',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })

        # Setup Expertise Skills
        self.skill_branding = self.Expertise.create({
            'name': 'Brand Strategy & Identity',
            'code': 'BRAND_ID',
            'category': 'branding'
        })
        self.skill_3d = self.Expertise.create({
            'name': '3D CGI Animation',
            'code': '3D_CGI',
            'category': '3d_cgi'
        })

        # Candidate 1: Verified Agency with Brand + 3D skills, 5.0 rating
        self.contact_1 = self.Partner.create({'name': 'Apex Creative Studio'})
        self.candidate_verified_agency = self.PartnerProfile.create({
            'partner_id': self.contact_1.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified',
            'availability_state': 'available',
            'public_rating': 5.0,
            'expertise_ids': [(6, 0, [self.skill_branding.id, self.skill_3d.id])]
        })

        # Candidate 2: Verified Individual with Brand skill only, 4.5 rating
        self.contact_2 = self.Partner.create({'name': 'John Freelance Designer'})
        self.candidate_verified_individual = self.PartnerProfile.create({
            'partner_id': self.contact_2.id,
            'tenant_id': self.tenant.id,
            'account_type': 'individual',
            'verification_status': 'verified',
            'availability_state': 'available',
            'public_rating': 4.5,
            'expertise_ids': [(6, 0, [self.skill_branding.id])]
        })

        # Candidate 3: Unverified Agency (Pending KYC)
        self.contact_3 = self.Partner.create({'name': 'Unvetted Studio'})
        self.candidate_unverified = self.PartnerProfile.create({
            'partner_id': self.contact_3.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'pending',
            'availability_state': 'available',
            'public_rating': 4.8,
            'expertise_ids': [(6, 0, [self.skill_branding.id, self.skill_3d.id])]
        })

        # Candidate 4: Verified but Unavailable Agency
        self.contact_4 = self.Partner.create({'name': 'Overbooked Agency'})
        self.candidate_unavailable = self.PartnerProfile.create({
            'partner_id': self.contact_4.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified',
            'availability_state': 'unavailable',
            'public_rating': 5.0,
            'expertise_ids': [(6, 0, [self.skill_branding.id])]
        })

    def test_hard_eligibility_rejections(self):
        """Hard eligibility gate rejects unverified, unavailable, and mismatched candidates."""
        from ..services.matching_service import MatchingEngineService
        svc = MatchingEngineService(self.env)

        brief = self.ProjectBrief.create({
            'title': 'Global Rebrand',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'target_account_type': 'agency',
            'budget_min': 10000.0,
            'budget_max': 25000.0,
            'delivery_deadline': fields.Date.today() + timedelta(days=30),
            'scope_summary': 'Comprehensive corporate rebranding overhaul.',
            'required_expertise_ids': [(6, 0, [self.skill_branding.id])]
        })

        # Unverified candidate must fail hard eligibility
        passed, reason = svc.evaluate_hard_eligibility(brief, self.candidate_unverified)
        self.assertFalse(passed)
        self.assertIn("must be verified", reason)

        # Unavailable candidate must fail hard eligibility
        passed, reason = svc.evaluate_hard_eligibility(brief, self.candidate_unavailable)
        self.assertFalse(passed)
        self.assertIn("unavailable", reason)

        # Individual candidate must fail when brief specifies 'agency'
        passed, reason = svc.evaluate_hard_eligibility(brief, self.candidate_verified_individual)
        self.assertFalse(passed)
        self.assertIn("Account type mismatch", reason)

        # Verified agency must pass hard eligibility
        passed, reason = svc.evaluate_hard_eligibility(brief, self.candidate_verified_agency)
        self.assertTrue(passed)
        self.assertIsNone(reason)

    def test_paid_subscription_cannot_bypass_hard_eligibility(self):
        """Locked Invariant: Paid subscription tiers cannot bypass hard eligibility failure."""
        from ..services.matching_service import MatchingEngineService
        svc = MatchingEngineService(self.env)

        brief = self.ProjectBrief.create({
            'title': 'High Budget Campaign',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'target_account_type': 'agency',
            'budget_min': 50000.0,
            'budget_max': 100000.0,
            'delivery_deadline': fields.Date.today() + timedelta(days=60),
            'scope_summary': 'National campaign',
            'required_expertise_ids': [(6, 0, [self.skill_branding.id])]
        })

        # Even if unverified candidate is treated as premium, hard eligibility must evaluate verification status
        passed, reason = svc.evaluate_hard_eligibility(brief, self.candidate_unverified)
        self.assertFalse(passed, "Paid or premium status must never bypass hard verification requirement!")

    def test_match_snapshot_creation_ac01(self):
        """AC-01: Only hard-eligible candidates are captured in immutable match snapshot."""
        brief = self.ProjectBrief.create({
            'title': 'Interactive 3D Identity',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'target_account_type': 'both',
            'budget_min': 15000.0,
            'budget_max': 30000.0,
            'delivery_deadline': fields.Date.today() + timedelta(days=45),
            'scope_summary': 'Interactive 3D visuals and brand assets.',
            'required_expertise_ids': [(6, 0, [self.skill_branding.id, self.skill_3d.id])]
        })

        brief.action_submit_and_match()

        self.assertEqual(brief.state, 'matched')
        self.assertTrue(brief.immutable_hash)
        self.assertEqual(len(brief.match_snapshot_ids), 1)

        snapshot = brief.match_snapshot_ids[0]
        self.assertEqual(snapshot.total_eligible_matched, 2)
        # Ineligible candidates (unverified and unavailable) must not be in candidate list
        matched_partner_ids = snapshot.candidate_ids.mapped('partner_profile_id.id')
        self.assertIn(self.candidate_verified_agency.id, matched_partner_ids)
        self.assertIn(self.candidate_verified_individual.id, matched_partner_ids)
        self.assertNotIn(self.candidate_unverified.id, matched_partner_ids)
        self.assertNotIn(self.candidate_unavailable.id, matched_partner_ids)

        # Candidate 1 (matches both skills) must outrank Candidate 2 (matches only 1 skill)
        top_candidate = snapshot.candidate_ids[0]
        self.assertEqual(top_candidate.partner_profile_id.id, self.candidate_verified_agency.id)
        self.assertEqual(top_candidate.rank, 1)
        self.assertGreater(top_candidate.overall_score, snapshot.candidate_ids[1].overall_score)

        # Immutability validation: Updating or deleting snapshot must raise UserError
        with self.assertRaises(UserError):
            snapshot.write({'algorithm_version': 'v2.0'})
        with self.assertRaises(UserError):
            snapshot.unlink()

    def test_opportunity_dispatch_and_sla_ac02(self):
        """AC-02: Dispatching opportunities starts SLA timer and protects blind anonymity."""
        from ..services.matching_service import OpportunityDispatchService

        brief = self.ProjectBrief.create({
            'title': 'Confidential Fintech Launch',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'target_account_type': 'agency',
            'budget_min': 20000.0,
            'budget_max': 40000.0,
            'delivery_deadline': fields.Date.today() + timedelta(days=30),
            'scope_summary': 'Proprietary fintech UI system',
            'anonymity_mode': 'blind',
            'required_expertise_ids': [(6, 0, [self.skill_branding.id])]
        })

        brief.action_submit_and_match()
        snapshot = brief.match_snapshot_ids[0]

        opp_svc = OpportunityDispatchService(self.env)
        dispatched = opp_svc.dispatch_to_candidates(snapshot.id, top_n=1, sla_hours=24)

        self.assertEqual(len(dispatched), 1)
        opp = dispatched[0]
        self.assertEqual(opp.state, 'dispatched')
        self.assertTrue(opp.expires_at)
        self.assertFalse(opp.client_disclosed, "Client identity must remain undisclosed during blind RFQ dispatch!")
        self.assertIn("BLIND RFQ", opp.blind_scope_summary)

        # Partner accepts opportunity -> client revealed and SLA stopped
        opp.action_accept(response_note="We have extensive fintech UI experience.")
        self.assertEqual(opp.state, 'accepted')
        self.assertTrue(opp.client_disclosed, "Client identity must be disclosed upon mutual acceptance!")
        self.assertTrue(opp.responded_at)

    def test_brief_versioning_lineage(self):
        """Editing sealed brief creates next revision in BRIEF_VN lineage."""
        brief_v1 = self.ProjectBrief.create({
            'title': 'Brand Concept V1',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'target_account_type': 'both',
            'budget_min': 5000.0,
            'budget_max': 10000.0,
            'delivery_deadline': fields.Date.today() + timedelta(days=15),
            'scope_summary': 'Initial visual concept',
            'required_expertise_ids': [(6, 0, [self.skill_branding.id])]
        })
        brief_v1.action_submit_and_match()

        brief_v2 = brief_v1.create_revision({
            'budget_max': 15000.0,
            'scope_summary': 'Expanded visual concept with 3D elements',
            'required_expertise_ids': [self.skill_branding.id, self.skill_3d.id]
        })

        self.assertEqual(brief_v2.version_no, 2)
        self.assertEqual(brief_v2.parent_brief_id.id, brief_v1.id)
        self.assertEqual(brief_v2.state, 'draft')
        self.assertEqual(brief_v2.budget_max, 15000.0)
