# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinDeliverable(models.Model):
    _name = 'vin.deliverable'
    _description = 'VIN Milestone Deliverable Specification'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id asc'

    uuid = fields.Char(
        string='Deliverable UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    name = fields.Char(
        string='Deliverable Title',
        required=True,
        tracking=True
    )
    milestone_id = fields.Many2one(
        'vin.milestone',
        string='Milestone',
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
    specification_summary = fields.Text(
        string='Technical & Creative Specification',
        required=True
    )
    acceptance_criteria = fields.Text(
        string='Objective Acceptance Criteria & Quality Gates',
        required=True
    )
    state = fields.Selection(
        [
            ('pending', 'Pending Submission'),
            ('submitted', 'Submission Uploaded'),
            ('under_review', 'Under Client Review'),
            ('revision_requested', 'Revision Requested'),
            ('accepted', 'Accepted by Client'),
            ('disputed', 'Disputed')
        ],
        string='Deliverable State',
        required=True,
        default='pending',
        tracking=True,
        index=True
    )
    submission_ids = fields.One2many(
        'vin.deliverable.submission',
        'deliverable_id',
        string='Submission Versions'
    )
    latest_submission_id = fields.Many2one(
        'vin.deliverable.submission',
        string='Latest Submission Version',
        readonly=True
    )
    revision_count = fields.Integer(
        string='Revisions Requested Count',
        default=0,
        readonly=True
    )
