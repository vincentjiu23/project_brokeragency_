# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo import fields
from ..services.policy_resolver import PolicyResolverService

class TestPolicyResolution(TransactionCase):
    """Test suite for policy versioning, non-retroactive historical pinning, and resolution."""

    def setUp(self):
        super().setUp()
        self.Policy = self.env['vin.policy.version']
        self.resolver = PolicyResolverService(self.env)

        # Create v1 policy
        self.policy_v1 = self.Policy.create({
            'code': 'POLICY_CLIENT_REVISION_QUOTA',
            'version_no': 1,
            'name': 'Client Revision Quota Standard v1',
            'rules_json': json.dumps({'default_quota': 3, 'max_window_days': 10}),
            'status': 'draft'
        })
        self.policy_v1.action_activate()

    def test_policy_activation_and_resolution(self):
        """Resolves active policy rules dynamically."""
        res = self.resolver.get_effective_policy('POLICY_CLIENT_REVISION_QUOTA')
        self.assertEqual(res['version_no'], 1)
        self.assertEqual(res['rules']['default_quota'], 3)

    def test_non_retroactive_pinning(self):
        """Active policy rules cannot be mutated in place; must create new version."""
        with self.assertRaises(UserError):
            self.policy_v1.write({'rules_json': json.dumps({'default_quota': 5})})

        # Create v2 policy
        policy_v2 = self.Policy.create({
            'code': 'POLICY_CLIENT_REVISION_QUOTA',
            'version_no': 2,
            'name': 'Client Revision Quota Standard v2',
            'rules_json': json.dumps({'default_quota': 4, 'max_window_days': 14}),
            'status': 'draft'
        })
        policy_v2.action_activate()

        # v1 is now superseded
        self.assertEqual(self.policy_v1.status, 'superseded')
        self.assertEqual(policy_v2.status, 'active')

        # Current resolution returns v2
        curr_res = self.resolver.get_effective_policy('POLICY_CLIENT_REVISION_QUOTA')
        self.assertEqual(curr_res['version_no'], 2)
        self.assertEqual(curr_res['rules']['default_quota'], 4)
