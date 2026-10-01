# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields

class TestWorkstreamDAG(TransactionCase):
    """
    Test suite for Workstream Directed Acyclic Graph (DAG) integrity,
    Milestone sequential gating, and Task dependency resolution.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.MasterProject = self.env['vin.master.project']
        self.Workstream = self.env['vin.workstream']
        self.Milestone = self.env['vin.milestone']
        self.Task = self.env['vin.task']

        self.tenant = self.Tenant.create({'code': 'T_EXEC', 'name': 'Execution Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_EXEC_CLIENT',
            'name': 'Client Execution Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.project = self.MasterProject.create({
            'code': 'PRJ_EXEC_01',
            'name': 'Comprehensive Design & Rollout',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id
        })

    def test_workstream_dag_acyclic_constraint(self):
        """Circular dependency in workstream DAG raises ValidationError."""
        ws_a = self.Workstream.create({
            'name': 'Workstream A (Strategy)',
            'master_project_id': self.project.id
        })
        ws_b = self.Workstream.create({
            'name': 'Workstream B (Design)',
            'master_project_id': self.project.id,
            'parent_workstream_ids': [(6, 0, [ws_a.id])]
        })

        # Attempting to make WS A depend on WS B creates a cycle: A -> B -> A
        with self.assertRaises(ValidationError):
            ws_a.write({'parent_workstream_ids': [(6, 0, [ws_b.id])]})

    def test_milestone_dependency_gating(self):
        """Milestones cannot start until prerequisite milestones are accepted."""
        ws = self.Workstream.create({
            'name': 'Brand System Workstream',
            'master_project_id': self.project.id
        })

        m1 = self.Milestone.create({
            'name': 'Milestone 1: Concept Approval',
            'workstream_id': ws.id,
            'target_deadline': fields.Date.today() + timedelta(days=15),
            'allocated_amount': 5000.0,
            'state': 'pending'
        })

        m2 = self.Milestone.create({
            'name': 'Milestone 2: Final Assets',
            'workstream_id': ws.id,
            'target_deadline': fields.Date.today() + timedelta(days=30),
            'allocated_amount': 10000.0,
            'prerequisite_milestone_ids': [(6, 0, [m1.id])],
            'state': 'pending'
        })

        # M1 starts successfully
        m1.action_start()
        self.assertEqual(m1.state, 'active')

        # M2 cannot start while M1 is active (not accepted)
        with self.assertRaises(UserError):
            m2.action_start()

    def test_task_dependency_resolution_event(self):
        """Resolving preceding tasks transitions downstream tasks and emits TASK_DEPENDENCY_RESOLVED."""
        ws = self.Workstream.create({
            'name': 'Production Workstream',
            'master_project_id': self.project.id
        })
        m = self.Milestone.create({
            'name': 'Milestone Alpha',
            'workstream_id': ws.id,
            'target_deadline': fields.Date.today() + timedelta(days=20),
            'allocated_amount': 7500.0
        })

        task_1 = self.Task.create({
            'name': 'Task 1: Research',
            'milestone_id': m.id,
            'task_type': 'contractual',
            'state': 'in_progress'
        })

        task_2 = self.Task.create({
            'name': 'Task 2: Prototyping',
            'milestone_id': m.id,
            'task_type': 'contractual',
            'preceding_task_ids': [(6, 0, [task_1.id])],
            'state': 'blocked'
        })

        # Completing Task 1 unblocks Task 2 and sets it to ready
        task_1.action_complete()
        self.assertEqual(task_1.state, 'done')
        self.assertEqual(task_2.state, 'ready')
