# -*- coding: utf-8 -*-
from decimal import Decimal
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields

class TestDisputeFreeze(TransactionCase):
    """
    Test suite for Tiered Acceptance Disputes & Arbitration (Q91–Q98, Q175).
    Verifies automatic virtual escrow freeze/locking, tamper-evident evidence packages,
    multi-tier escalation, and zero-variance settlement resolution.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Contract = self.env['vin.contract']
        self.Workstream = self.env['vin.workstream']
        self.Milestone = self.env['vin.milestone']
        self.EscrowAccount = self.env['vin.escrow.account']
        self.Allocation = self.env['vin.escrow.allocation']
        self.Dispute = self.env['vin.dispute']
        self.Evidence = self.env['vin.dispute.evidence']
        self.Arbitration = self.env['vin.arbitration.case']

        self.tenant = self.Tenant.create({'code': 'T_DISP', 'name': 'Dispute Test Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_DISP_CLIENT',
            'name': 'Client Dispute Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_contact = self.Partner.create({'name': 'VFX Studio Partner'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })

        self.contract = self.Contract.create({
            'title': '3D CGI Production Contract',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'partner_profile_id': self.partner_profile.id,
            'total_contract_value': 25000.0,
            'state': 'active'
        })

        self.escrow_account = self.EscrowAccount.create({
            'contract_id': self.contract.id,
            'tenant_id': self.tenant.id,
            'currency': 'USD',
            'total_deposited': 25000.0,
            'state': 'funded'
        })

        self.allocation = self.Allocation.create({
            'escrow_account_id': self.escrow_account.id,
            'tenant_id': self.tenant.id,
            'amount': 10000.0,
            'currency': 'USD',
            'state': 'allocated'
        })

    def test_01_dispute_opening_locks_escrow(self):
        """Test that opening a dispute atomically locks the escrow allocation and account."""
        dispute = self.Dispute.create({
            'title': 'Milestone 2 Acceptance Rejection Dispute',
            'tenant_id': self.tenant.id,
            'description': 'Client rejected 3D model delivery alleging lighting flaws outside specifications.',
            'contract_id': self.contract.id,
            'escrow_allocation_id': self.allocation.id,
            'disputed_amount': 10000.0,
            'initiator_type': 'partner'
        })

        self.assertEqual(dispute.state, 'draft')
        self.assertEqual(self.allocation.state, 'allocated')
        self.assertEqual(self.escrow_account.state, 'funded')

        # Open dispute
        dispute.action_open()

        self.assertEqual(dispute.state, 'open')
        self.assertEqual(self.allocation.state, 'disputed')
        self.assertEqual(self.escrow_account.state, 'locked')
        self.assertTrue("FROZEN: Active dispute" in self.escrow_account.lock_reason)

    def test_02_evidence_submission_and_hash_integrity(self):
        """Test evidence items generate SHA-256 digests for evidentiary immutability."""
        dispute = self.Dispute.create({
            'title': 'Scope Creep Dispute',
            'tenant_id': self.tenant.id,
            'description': 'Excessive revision rounds demanded.',
            'contract_id': self.contract.id,
            'escrow_allocation_id': self.allocation.id,
            'disputed_amount': 10000.0,
            'initiator_type': 'partner'
        })
        dispute.action_open()

        evidence = self.Evidence.create({
            'dispute_id': dispute.id,
            'title': 'Approved Storyboard Exhibit A',
            'submitted_by_party': 'partner',
            'evidence_type': 'contract_clause',
            'description': 'Original signed storyboard defining only 2 revision passes.'
        })

        self.assertTrue(evidence.sha256_hash)
        self.assertEqual(len(evidence.sha256_hash), 64)

    def test_03_split_settlement_zero_variance_enforcement(self):
        """Test resolution split enforces refund + payout == disputed_amount and unlocks escrow."""
        dispute = self.Dispute.create({
            'title': 'Milestone Defect Settlement',
            'tenant_id': self.tenant.id,
            'description': 'Parties agreed to split settlement 60% partner, 40% client.',
            'contract_id': self.contract.id,
            'escrow_allocation_id': self.allocation.id,
            'disputed_amount': 10000.0,
            'initiator_type': 'client'
        })
        dispute.action_open()
        dispute.action_escalate_mediation()

        # Fails zero-variance check (6000 + 3000 != 10000)
        with self.assertRaises(ValidationError):
            dispute.action_resolve_settlement(
                resolution_type='split_settlement',
                client_refund=3000.0,
                partner_payout=6000.0
            )

        # Passes zero-variance check (4000 + 6000 == 10000)
        dispute.action_resolve_settlement(
            resolution_type='split_settlement',
            client_refund=4000.0,
            partner_payout=6000.0,
            summary="Agreed mediated settlement: $4k client refund, $6k partner release."
        )

        self.assertEqual(dispute.state, 'resolved')
        self.assertEqual(self.escrow_account.state, 'funded')  # unlocked
        self.assertEqual(self.allocation.state, 'released')

    def test_04_tier3_arbitration_flow(self):
        """Test escalation to binding arbitration tribunal and award enforcement."""
        dispute = self.Dispute.create({
            'title': 'Complex Contract Interpretation Dispute',
            'tenant_id': self.tenant.id,
            'description': 'Total deadlock on final acceptance.',
            'contract_id': self.contract.id,
            'escrow_allocation_id': self.allocation.id,
            'disputed_amount': 10000.0,
            'initiator_type': 'client'
        })
        dispute.action_open()
        dispute.action_escalate_arbitration()

        arb_case = self.Arbitration.create({
            'dispute_id': dispute.id,
            'arbitration_body': 'platform_panel',
            'arbitrator_lead_name': 'Hon. Panel Chair'
        })
        self.assertEqual(arb_case.state, 'filed')
        arb_case.write({'state': 'in_review'})

        # Render binding ruling: 100% to partner
        arb_case.action_render_binding_ruling(
            ruling_text="Deliverable met all contractual quality specifications. Partner awarded full compensation.",
            client_award_refund=0.0,
            partner_award_payout=10000.0
        )

        self.assertEqual(arb_case.state, 'enforced')
        self.assertEqual(dispute.state, 'resolved')
        self.assertEqual(self.escrow_account.state, 'funded')
