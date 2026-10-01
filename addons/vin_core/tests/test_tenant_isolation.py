# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, AccessDenied

class TestTenantIsolation(TransactionCase):
    """Test suite enforcing server-side tenant isolation baseline."""

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Org = self.env['vin.organization']
        self.Membership = self.env['vin.membership']
        self.MasterProject = self.env['vin.master.project']
        self.Users = self.env['res.users']

        # Setup Tenant A and Organization A
        self.tenant_a = self.Tenant.create({
            'code': 'TENANT_A',
            'name': 'Tenant Alpha'
        })
        self.org_a = self.Org.create({
            'code': 'ORG_A',
            'name': 'Organization Alpha',
            'tenant_id': self.tenant_a.id
        })

        # Setup Tenant B and Organization B
        self.tenant_b = self.Tenant.create({
            'code': 'TENANT_B',
            'name': 'Tenant Beta'
        })
        self.org_b = self.Org.create({
            'code': 'ORG_B',
            'name': 'Organization Beta',
            'tenant_id': self.tenant_b.id
        })

        # User A belonging strictly to Org A
        self.user_a = self.Users.create({
            'name': 'Alice User A',
            'login': 'alice_a@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]
        })
        self.Membership.create({
            'organization_id': self.org_a.id,
            'user_id': self.user_a.id,
            'role': 'pic'
        })

        # User B belonging strictly to Org B
        self.user_b = self.Users.create({
            'name': 'Bob User B',
            'login': 'bob_b@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]
        })
        self.Membership.create({
            'organization_id': self.org_b.id,
            'user_id': self.user_b.id,
            'role': 'pic'
        })

    def test_tenant_boundary_isolation(self):
        """Ensure User A cannot query or read projects from Org B."""
        # Project in Org B
        proj_b = self.MasterProject.create({
            'name': 'Secret Project Beta',
            'organization_id': self.org_b.id
        })

        # Alice should NOT see Project Beta in her record rule search
        projects_for_alice = self.MasterProject.with_user(self.user_a).search([('id', '=', proj_b.id)])
        self.assertEqual(len(projects_for_alice), 0, "Security violation: Cross-tenant project was visible to unauthorized user!")

    def test_tenant_code_uniqueness(self):
        """Ensure tenant code is strictly unique across platform."""
        with self.assertRaises(Exception):
            self.Tenant.create({
                'code': 'TENANT_A',
                'name': 'Duplicate Code Tenant'
            })
