# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinMilestone(models.Model):
    _name = 'vin.milestone'
    _description = 'VIN Execution Milestone'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence asc, id asc'

    uuid = fields.Char(
        string='Milestone UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    name = fields.Char(
        string='Milestone Name',
        required=True,
        tracking=True
    )
    sequence = fields.Integer(
        string='Sequence Order',
        default=10
    )
    workstream_id = fields.Many2one(
        'vin.workstream',
        string='Workstream DAG Node',
        required=True,
        index=True,
        ondelete='cascade'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='workstream_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    target_deadline = fields.Date(
        string='Target Deadline',
        required=True,
        tracking=True
    )
    allocated_amount = fields.Monetary(
        string='Allocated Escrow Budget',
        currency_field='currency_id',
        required=True,
        default=0.0
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    prerequisite_milestone_ids = fields.Many2many(
        'vin.milestone',
        'vin_milestone_prereq_rel',
        'milestone_id',
        'prereq_id',
        string='Prerequisite Milestones'
    )
    task_ids = fields.One2many(
        'vin.task',
        'milestone_id',
        string='Tasks'
    )
    deliverable_ids = fields.One2many(
        'vin.deliverable',
        'milestone_id',
        string='Deliverables'
    )
    state = fields.Selection(
        [
            ('pending', 'Pending Prerequisites'),
            ('active', 'Active / In Progress'),
            ('submitted', 'Deliverables Submitted'),
            ('in_review', 'Under Client Review'),
            ('accepted', 'Accepted & Released (AC-05)'),
            ('disputed', 'Disputed / Frozen')
        ],
        string='Milestone State',
        required=True,
        default='pending',
        tracking=True,
        index=True
    )

    @api.constrains('prerequisite_milestone_ids')
    def _check_prerequisites_acyclic(self):
        for record in self:
            visited = set()
            stack = list(record.prerequisite_milestone_ids)
            while stack:
                curr = stack.pop()
                if curr.id == record.id:
                    raise ValidationError(_("Milestone Dependency Cycle: Circular prerequisite detected in milestone '%s'!") % record.name)
                if curr.id not in visited:
                    visited.add(curr.id)
                    stack.extend(curr.prerequisite_milestone_ids)

    def action_start(self):
        """Transitions milestone to active if all prerequisites are accepted."""
        for record in self:
            if record.state != 'pending':
                raise UserError(_("Only pending milestones can be started."))

            unmet_prereqs = record.prerequisite_milestone_ids.filtered(lambda m: m.state != 'accepted')
            if unmet_prereqs:
                raise UserError(_("Cannot start milestone: Prerequisite milestones %s are not yet accepted!") %
                                unmet_prereqs.mapped('name'))

            record.write({'state': 'active'})
            if record.workstream_id.state in ('draft', 'ready'):
                record.workstream_id.write({'state': 'in_progress'})

            # Record MILESTONE_STARTED audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='MILESTONE_STARTED',
                subject_type='vin.milestone',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'milestone_name': record.name,
                    'allocated_amount': float(record.allocated_amount),
                    'workstream_uuid': record.workstream_id.uuid
                }
            )

        return True

    def action_accept_milestone(self):
        """
        AC-05: Formal acceptance of milestone when all required deliverables are accepted.
        Triggers escrow release readiness and IP assignment.
        """
        for record in self:
            if record.state not in ('submitted', 'in_review'):
                raise UserError(_("Cannot accept milestone in state '%s'.") % record.state)

            pending_deliverables = record.deliverable_ids.filtered(lambda d: d.state != 'accepted')
            if pending_deliverables:
                raise UserError(_("Cannot accept milestone: Deliverables %s are not yet accepted!") %
                                pending_deliverables.mapped('name'))

            record.write({'state': 'accepted'})

            # Record MILESTONE_ACCEPTED audit event (AC-05)
            self.env['vin.audit.event'].sudo().record_event(
                action='MILESTONE_ACCEPTED',
                subject_type='vin.milestone',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'milestone_name': record.name,
                    'allocated_amount': float(record.allocated_amount),
                    'workstream_uuid': record.workstream_id.uuid
                }
            )

            # Auto-unblock downstream milestones in workstream
            downstream_milestones = self.search([
                ('prerequisite_milestone_ids', 'in', [record.id]),
                ('state', '=', 'pending')
            ])
            for next_m in downstream_milestones:
                if all(p.state == 'accepted' for p in next_m.prerequisite_milestone_ids):
                    next_m.action_start()

            # Check if all milestones in workstream are completed
            all_ws_accepted = all(m.state == 'accepted' for m in record.workstream_id.milestone_ids)
            if all_ws_accepted:
                record.workstream_id.write({'state': 'completed'})

        return True
