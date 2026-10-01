# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinMatchSnapshot(models.Model):
    _name = 'vin.match.snapshot'
    _description = 'VIN Deterministic Candidate Match Snapshot'
    _order = 'snapshot_time desc'

    uuid = fields.Char(
        string='Snapshot UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    brief_id = fields.Many2one(
        'vin.project.brief',
        string='Project Brief Version',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        required=True,
        readonly=True,
        index=True
    )
    snapshot_time = fields.Datetime(
        string='Snapshot Timestamp',
        default=fields.Datetime.now,
        readonly=True,
        required=True
    )
    algorithm_version = fields.Char(
        string='Scoring Engine Algorithm Version',
        default='v1.0.0-deterministic-ranker',
        readonly=True,
        required=True
    )
    total_candidates_screened = fields.Integer(
        string='Total Partners Screened',
        readonly=True,
        default=0
    )
    total_eligible_matched = fields.Integer(
        string='Total Hard-Eligible Candidates',
        readonly=True,
        default=0
    )
    candidate_ids = fields.One2many(
        'vin.match.candidate',
        'snapshot_id',
        string='Screened Candidates',
        readonly=True
    )
    state = fields.Selection(
        [
            ('frozen', 'Frozen / Finalized'),
            ('archived', 'Archived')
        ],
        string='Snapshot State',
        default='frozen',
        readonly=True,
        required=True
    )

    def write(self, vals):
        """Locked Architecture Decision: Match snapshots are immutable audit records."""
        raise UserError(_("Security Violation: Match snapshots are strictly immutable and cannot be updated!"))

    def unlink(self):
        """Locked Architecture Decision: Match snapshots cannot be deleted."""
        raise UserError(_("Security Violation: Match snapshots cannot be deleted!"))
