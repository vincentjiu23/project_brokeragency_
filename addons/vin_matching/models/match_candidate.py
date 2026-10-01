# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinMatchCandidate(models.Model):
    _name = 'vin.match.candidate'
    _description = 'VIN Evaluated Match Candidate'
    _order = 'rank asc, overall_score desc'

    uuid = fields.Char(
        string='Candidate UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    snapshot_id = fields.Many2one(
        'vin.match.snapshot',
        string='Match Snapshot',
        required=True,
        readonly=True,
        ondelete='cascade',
        index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='snapshot_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    partner_profile_id = fields.Many2one(
        'creative.partner.profile',
        string='Creative Partner Profile',
        required=True,
        readonly=True,
        index=True
    )
    rank = fields.Integer(
        string='Candidate Rank',
        readonly=True,
        default=0
    )
    overall_score = fields.Float(
        string='Match Score (0.00-100.00)',
        digits=(5, 2),
        readonly=True,
        default=0.0
    )
    expertise_match_score = fields.Float(
        string='Expertise Fit Score (0.00-100.00)',
        digits=(5, 2),
        readonly=True,
        default=0.0
    )
    reputation_score = fields.Float(
        string='Reputation Score (0.00-100.00)',
        digits=(5, 2),
        readonly=True,
        default=0.0
    )
    hard_eligibility_passed = fields.Boolean(
        string='Hard Eligibility Passed',
        readonly=True,
        default=False,
        help="Locked Rule: Hard eligibility must be True. Cannot be bypassed by subscription tier."
    )
    disqualification_reason = fields.Char(
        string='Disqualification Reason',
        readonly=True
    )
    opportunity_id = fields.Many2one(
        'vin.opportunity.record',
        string='Dispatched Opportunity Record',
        readonly=True
    )
