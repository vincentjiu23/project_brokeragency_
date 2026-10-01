# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields

class TestContractImmutability(TransactionCase):
    """
    Test suite for CONTRACT_VN immutability (ADR-003),
    Four-Eyes Segregation of Duties (ADR-005),
    Material Proposal Delta Invalidation (AC-03),
    and version lineage through Change Requests.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Contract = self.env['vin.contract']
        self.Proposal = self.env['vin.contract.proposal']
        self.Approval = self.env['vin.contract.approval']
        self.ChangeRequest = self.env['vin.contract.change.request']
        self.User = self.env['res.users']

        self.tenant = self.Tenant.create({'code': 'T_LEGAL', 'name': 'Legal Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_CORP_LEGAL',
            'name': 'Corporate Enterprise Corp',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_contact = self.Partner.create({'name': 'Vetted Production Studio'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })

        # Creator user and distinct independent approver user
        self.user_creator = self.env.user
        self.user_approver = self.User.create({
            'name': 'Independent Legal Counsel',
            'login': 'legal_counsel@vin.internal',
            'email': 'legal_counsel@vin.internal'
        })

        self.contract = self.Contract.create({
            'title': 'Master Design & Development Contract',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'partner_profile_id': self.partner_profile.id,
            'total_contract_value': 50000.0,
            'completion_deadline': fields.Date.today() + timedelta(days=90),
            'state': 'draft'
        })

    def test_four_eyes_approval_enforcement(self):
        """Creator cannot approve their own contract tier (ADR-005)."""
        self.contract.action_submit_for_approval()
        comm_tier = self.contract.approval_ids.filtered(lambda a: a.approval_tier == 'commercial')

        # Attempt to approve as creator must fail with UserError
        with self.assertRaises(UserError):
            comm_tier.with_user(self.user_creator).action_approve()

        # Approval by distinct independent user must succeed
        comm_tier.with_user(self.user_approver).action_approve()
        self.assertEqual(comm_tier.state, 'approved')

    def test_material_proposal_delta_invalidates_prior_approvals_ac03(self):
        """AC-03: Material proposal delta automatically invalidates prior approvals."""
        self.contract.action_submit_for_approval()
        comm_tier = self.contract.approval_ids.filtered(lambda a: a.approval_tier == 'commercial')
        comm_tier.with_user(self.user_approver).action_approve()
        self.assertEqual(comm_tier.state, 'approved')

        # Submit proposal with material delta (budget increased to 65,000)
        prop = self.Proposal.create({
            'contract_id': self.contract.id,
            'author_role': 'partner',
            'proposed_budget': 65000.0,
            'proposed_deadline': self.contract.completion_deadline,
            'state': 'draft'
        })
        prop.action_submit_proposal()

        # Verify commercial tier is automatically invalidated (AC-03)
        self.assertEqual(comm_tier.state, 'invalidated')
        self.assertIn("Material Proposal Delta", comm_tier.invalidation_reason)
        self.assertEqual(self.contract.state, 'in_review')

    def test_contract_immutability_when_active(self):
        """Active contracts cannot be modified directly via write() (ADR-003)."""
        self.contract.action_submit_for_approval()
        for app in self.contract.approval_ids:
            app.with_user(self.user_approver).action_approve()

        self.contract.action_activate()
        self.assertEqual(self.contract.state, 'active')
        self.assertTrue(self.contract.signed_hash)

        # Direct mutation of terms must raise UserError
        with self.assertRaises(UserError):
            self.contract.write({'total_contract_value': 75000.0})

        with self.assertRaises(UserError):
            self.contract.write({'completion_deadline': fields.Date.today() + timedelta(days=120)})

    def test_change_request_spawns_new_version(self):
        """Change request execution spawns next immutable contract version (e.g. v1.0 -> v1.1)."""
        self.contract.action_submit_for_approval()
        for app in self.contract.approval_ids:
            app.with_user(self.user_approver).action_approve()
        self.contract.action_activate()

        cr = self.ChangeRequest.create({
            'contract_id': self.contract.id,
            'scope_delta': 'Additional branding sub-assets',
            'budget_delta': 10000.0,
            'timeline_delta_days': 15,
            'state': 'draft'
        })
        cr.action_submit_for_review()
        cr.action_approve()
        cr.action_execute()

        # Old contract is marked as amended
        self.assertEqual(self.contract.state, 'amended')
        self.assertEqual(cr.state, 'executed')

        # New contract version is spawned
        new_contract = cr.resulting_contract_id
        self.assertTrue(new_contract)
        self.assertEqual(new_contract.version_no, 2)
        self.assertEqual(new_contract.parent_contract_id.id, self.contract.id)
        self.assertEqual(new_contract.total_contract_value, 60000.0)
        self.assertEqual(new_contract.state, 'active')
