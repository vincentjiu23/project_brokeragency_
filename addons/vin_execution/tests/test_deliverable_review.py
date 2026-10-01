# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields

class TestDeliverableReview(TransactionCase):
    """
    Test suite for immutable deliverable submissions,
    formal acceptance workflows (AC-05), and structured revision limits.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.MasterProject = self.env['vin.master.project']
        self.Workstream = self.env['vin.workstream']
        self.Milestone = self.env['vin.milestone']
        self.Deliverable = self.env['vin.deliverable']
        self.Submission = self.env['vin.deliverable.submission']
        self.Acceptance = self.env['vin.deliverable.acceptance']
        self.Revision = self.env['vin.deliverable.revision']

        self.tenant = self.Tenant.create({'code': 'T_REVIEW', 'name': 'Review Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_REV_CLIENT',
            'name': 'Client Review Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.project = self.MasterProject.create({
            'code': 'PRJ_REV_01',
            'name': 'Brand Design Project',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id
        })
        self.workstream = self.Workstream.create({
            'name': 'Visual Assets Workstream',
            'master_project_id': self.project.id
        })
        self.milestone = self.Milestone.create({
            'name': 'Milestone 1: Identity Guide',
            'workstream_id': self.workstream.id,
            'target_deadline': fields.Date.today() + timedelta(days=20),
            'allocated_amount': 8000.0,
            'state': 'pending'
        })
        self.milestone.action_start()

        self.deliverable = self.Deliverable.create({
            'name': 'Final Vector Logo Suite',
            'milestone_id': self.milestone.id,
            'specification_summary': 'Vector logo in AI, EPS, SVG, and high-res PNG formats',
            'acceptance_criteria': 'All colorways, responsive marks, clear color profiles'
        })

    def test_immutable_submission_creation(self):
        """Deliverable submission creates immutable version and records audit event."""
        sub = self.Submission.create({
            'deliverable_id': self.deliverable.id,
            'asset_vault_ref': 'sha256_mock_asset_vault_hash_778899',
            'asset_object_id': 'obj-vault-uuid-001',
            'submission_notes': 'Initial release candidate 1'
        })

        self.assertEqual(sub.version_no, 1)
        self.assertEqual(self.deliverable.latest_submission_id.id, sub.id)
        self.assertEqual(self.deliverable.state, 'submitted')
        self.assertEqual(self.milestone.state, 'in_review')

        # Immutability validation: Updating protected fields or deleting must fail
        with self.assertRaises(UserError):
            sub.write({'asset_vault_ref': 'altered_hash'})

        with self.assertRaises(UserError):
            sub.unlink()

    def test_deliverable_acceptance_triggers_milestone_acceptance_ac05(self):
        """AC-05: Deliverable acceptance triggers milestone acceptance."""
        sub = self.Submission.create({
            'deliverable_id': self.deliverable.id,
            'asset_vault_ref': 'sha256_accepted_asset_hash',
            'asset_object_id': 'obj-vault-uuid-002',
            'submission_notes': 'Complete delivery package'
        })

        # Client accepts deliverable
        self.Acceptance.create({
            'deliverable_id': self.deliverable.id,
            'submission_id': sub.id,
            'acceptance_notes': 'Fully matches specification and aesthetic standards.'
        })

        self.assertEqual(sub.state, 'accepted')
        self.assertEqual(self.deliverable.state, 'accepted')
        # Parent milestone is automatically accepted (AC-05)
        self.assertEqual(self.milestone.state, 'accepted')

    def test_structured_revision_limit_cap(self):
        """Revision limit enforcement caps at 2 before requiring Change Request."""
        sub1 = self.Submission.create({
            'deliverable_id': self.deliverable.id,
            'asset_vault_ref': 'sha256_hash_v1',
            'asset_object_id': 'obj-v1'
        })

        # Revision 1
        self.Revision.create({
            'deliverable_id': self.deliverable.id,
            'submission_id': sub1.id,
            'critique_feedback': 'Colors need higher contrast for WCAG AA compliance.'
        })
        self.assertEqual(self.deliverable.revision_count, 1)
        self.assertEqual(self.deliverable.state, 'revision_requested')

        sub2 = self.Submission.create({
            'deliverable_id': self.deliverable.id,
            'asset_vault_ref': 'sha256_hash_v2',
            'asset_object_id': 'obj-v2'
        })

        # Revision 2
        self.Revision.create({
            'deliverable_id': self.deliverable.id,
            'submission_id': sub2.id,
            'critique_feedback': 'Icon mark sizing in mobile view is slightly distorted.'
        })
        self.assertEqual(self.deliverable.revision_count, 2)

        sub3 = self.Submission.create({
            'deliverable_id': self.deliverable.id,
            'asset_vault_ref': 'sha256_hash_v3',
            'asset_object_id': 'obj-v3'
        })

        # Revision 3 must exceed cap and raise UserError
        with self.assertRaises(UserError):
            self.Revision.create({
                'deliverable_id': self.deliverable.id,
                'submission_id': sub3.id,
                'critique_feedback': 'Completely change the logo concept to a circle.'
            })
