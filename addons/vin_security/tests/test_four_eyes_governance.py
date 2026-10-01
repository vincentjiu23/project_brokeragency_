# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields

class TestFourEyesGovernance(TransactionCase):
    """Test suite enforcing Segregation of Duties (SoD) / Four-Eyes principle."""

    def setUp(self):
        super().setUp()
        self.Override = self.env['vin.governance.override']
        self.Users = self.env['res.users']

        self.requester_user = self.Users.create({
            'name': 'Requester Officer',
            'login': 'requester@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]
        })

        self.approver_user = self.Users.create({
            'name': 'Approver Director',
            'login': 'approver@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]
        })

    def test_self_approval_prohibited(self):
        """Requester can NEVER approve their own override request."""
        override = self.Override.with_user(self.requester_user).create({
            'override_domain': 'financial',
            'legal_evidence_ref': 'ASSET-SHA256-LEGAL-AFFIDAVIT-999',
            'justification': 'Emergency escrow unlock due to verified court order',
            'expiry_timestamp': fields.Datetime.now() + timedelta(hours=4),
            'rollback_instructions': 'Relock escrow allocation and notify Legal Counsel'
        })

        # Self approval attempt MUST raise UserError
        with self.assertRaises(UserError):
            override.with_user(self.requester_user).action_approve_override()

    def test_independent_dual_approval_success(self):
        """Distinct approver can successfully approve the override."""
        override = self.Override.with_user(self.requester_user).create({
            'override_domain': 'financial',
            'legal_evidence_ref': 'ASSET-SHA256-LEGAL-AFFIDAVIT-999',
            'justification': 'Emergency escrow unlock due to verified court order',
            'expiry_timestamp': fields.Datetime.now() + timedelta(hours=4),
            'rollback_instructions': 'Relock escrow allocation and notify Legal Counsel'
        })

        override.with_user(self.approver_user).action_approve_override()
        self.assertEqual(override.state, 'approved')
        self.assertEqual(override.approved_by_id.id, self.approver_user.id)
