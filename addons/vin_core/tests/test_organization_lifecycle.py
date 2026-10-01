# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestOrganizationLifecycle(TransactionCase):
    """Test suite for organization and project lifecycle transitions."""

    def setUp(self):
        super().setUp()
        self.tenant = self.env['vin.tenant'].create({
            'code': 'TENANT_CORP',
            'name': 'Corporate Tenant'
        })
        self.org = self.env['vin.organization'].create({
            'code': 'CORP_ORG',
            'name': 'Corp Org 1',
            'tenant_id': self.tenant.id
        })
        self.project = self.env['vin.master.project'].create({
            'name': 'Campaign Launch 2026',
            'organization_id': self.org.id,
            'state': 'acceptance'
        })

    def test_five_gate_closure_enforcement(self):
        """Action verify and complete must fail if all 5 closure gates are not satisfied."""
        with self.assertRaises(UserError):
            # Attempt to complete without gates being true
            self.project.action_verify_and_complete()

        # Satisfy all 5 gates
        self.project.write({
            'gate_workstreams_complete': True,
            'gate_escrow_zero_out': True,
            'gate_ip_transfer_complete': True,
            'gate_tax_invoice_reconciled': True,
            'gate_no_active_dispute': True
        })

        self.project.action_verify_and_complete()
        self.assertEqual(self.project.state, 'completed')
        self.assertTrue(bool(self.project.completed_at))
        self.assertTrue(bool(self.project.final_closure_deadline))
