# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinWorkstream(models.Model):
    _name = 'vin.workstream'
    _description = 'VIN Workstream DAG'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence asc, id asc'

    uuid = fields.Char(
        string='Workstream UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    name = fields.Char(
        string='Workstream Name',
        required=True,
        tracking=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    master_project_id = fields.Many2one(
        'vin.master.project',
        string='Master Project',
        required=True,
        index=True,
        ondelete='cascade'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='master_project_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    contract_id = fields.Many2one(
        'vin.contract',
        string='Governing Contract (CONTRACT_VN)',
        index=True,
        ondelete='restrict'
    )
    parent_workstream_ids = fields.Many2many(
        'vin.workstream',
        'vin_workstream_dag_rel',
        'child_id',
        'parent_id',
        string='Preceding Workstream Dependencies'
    )
    child_workstream_ids = fields.Many2many(
        'vin.workstream',
        'vin_workstream_dag_rel',
        'parent_id',
        'child_id',
        string='Dependent Downstream Workstreams'
    )
    milestone_ids = fields.One2many(
        'vin.milestone',
        'workstream_id',
        string='Milestones'
    )
    state = fields.Selection(
        [
            ('draft', 'Draft Workstream'),
            ('ready', 'Dependencies Satisfied / Ready'),
            ('in_progress', 'In Execution'),
            ('blocked', 'Blocked by Upstream Workstream'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled')
        ],
        string='Workstream State',
        required=True,
        default='draft',
        tracking=True,
        index=True
    )

    @api.constrains('parent_workstream_ids')
    def _check_dag_acyclic(self):
        """Enforces Directed Acyclic Graph (DAG) integrity — no circular dependencies."""
        for record in self:
            visited = set()
            stack = list(record.parent_workstream_ids)
            while stack:
                curr = stack.pop()
                if curr.id == record.id:
                    raise ValidationError(_("DAG Violation: Circular dependency detected in workstream '%s'!") % record.name)
                if curr.id not in visited:
                    visited.add(curr.id)
                    stack.extend(curr.parent_workstream_ids)

    def check_and_activate(self):
        """Transitions workstream to ready/in_progress if all parent workstreams are completed."""
        for record in self:
            if record.state in ('draft', 'blocked'):
                parents_completed = all(p.state == 'completed' for p in record.parent_workstream_ids)
                if parents_completed:
                    record.write({'state': 'ready'})
                else:
                    record.write({'state': 'blocked'})
