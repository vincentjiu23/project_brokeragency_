# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinTask(models.Model):
    _name = 'vin.task'
    _description = 'VIN Execution Task (Contractual vs Operational)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence asc, id asc'

    uuid = fields.Char(
        string='Task UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    name = fields.Char(
        string='Task Title',
        required=True,
        tracking=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    milestone_id = fields.Many2one(
        'vin.milestone',
        string='Parent Milestone',
        required=True,
        index=True,
        ondelete='cascade'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='milestone_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    task_type = fields.Selection(
        [
            ('contractual', 'Contractual Milestone Task'),
            ('operational', 'Internal Operational Work Item')
        ],
        string='Task Classification',
        required=True,
        default='contractual',
        index=True,
        help="Contractual tasks directly gate milestone sign-off; operational tasks are partner-internal."
    )
    preceding_task_ids = fields.Many2many(
        'vin.task',
        'vin_task_dependency_rel',
        'task_id',
        'preceding_id',
        string='Preceding Task Dependencies'
    )
    assigned_user_id = fields.Many2one(
        'res.users',
        string='Assigned Creative Lead / Contributor',
        index=True
    )
    deadline = fields.Date(
        string='Target Due Date'
    )
    state = fields.Selection(
        [
            ('blocked', 'Blocked by Preceding Tasks'),
            ('ready', 'Dependencies Resolved / Ready'),
            ('in_progress', 'In Execution'),
            ('in_review', 'Review'),
            ('done', 'Completed'),
            ('cancelled', 'Cancelled')
        ],
        string='Task State',
        required=True,
        default='blocked',
        tracking=True,
        index=True
    )

    @api.constrains('preceding_task_ids')
    def _check_task_dependency_acyclic(self):
        for record in self:
            visited = set()
            stack = list(record.preceding_task_ids)
            while stack:
                curr = stack.pop()
                if curr.id == record.id:
                    raise ValidationError(_("Task Dependency Cycle: Circular dependency detected in task '%s'!") % record.name)
                if curr.id not in visited:
                    visited.add(curr.id)
                    stack.extend(curr.preceding_task_ids)

    def action_resolve_dependencies(self):
        """Checks if all preceding tasks are completed and emits TASK_DEPENDENCY_RESOLVED."""
        for record in self:
            if record.state == 'blocked':
                all_done = all(t.state == 'done' for t in record.preceding_task_ids)
                if all_done:
                    record.write({'state': 'ready'})
                    # Emit TASK_DEPENDENCY_RESOLVED audit event
                    self.env['vin.audit.event'].sudo().record_event(
                        action='TASK_DEPENDENCY_RESOLVED',
                        subject_type='vin.task',
                        subject_id=record.uuid,
                        tenant_id=record.tenant_id.uuid,
                        payload={
                            'task_name': record.name,
                            'milestone_uuid': record.milestone_id.uuid
                        }
                    )
        return True

    def action_start(self):
        for record in self:
            if record.state not in ('ready', 'blocked'):
                raise UserError(_("Task cannot be started in state '%s'.") % record.state)
            record.action_resolve_dependencies()
            if record.state != 'ready':
                raise UserError(_("Cannot start task: Preceding tasks are not yet complete!"))
            record.write({'state': 'in_progress'})
        return True

    def action_complete(self):
        """Marks task as done and resolves dependent tasks."""
        for record in self:
            record.write({'state': 'done'})
            # Unblock downstream tasks
            downstream = self.search([
                ('preceding_task_ids', 'in', [record.id]),
                ('state', '=', 'blocked')
            ])
            for t in downstream:
                t.action_resolve_dependencies()
        return True
