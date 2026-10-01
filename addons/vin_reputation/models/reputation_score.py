# -*- coding: utf-8 -*-
"""
Reputation Score Aggregate Model (Q137–Q146 Reputation Domain).
Maintains computed reputation scores per organization/partner.
Public metrics (average stars, completion rate) are separated from
internal trust scores (hidden from all public APIs).
"""
import uuid
from decimal import Decimal, ROUND_HALF_UP
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class VinReputationScore(models.Model):
    """
    Aggregate Reputation Score Record.
    Maintains both public-facing metrics and internal trust scores.

    Invariants:
      - Internal trust score is NEVER exposed via public API.
      - Public metrics derive only from revealed, non-redacted reviews.
      - Score recalculation is triggered by trust events and review reveals.
    """
    _name = 'vin.reputation.score'
    _description = 'VIN Reputation Score Aggregate'
    _order = 'public_avg_rating desc, id desc'
    _rec_name = 'display_name'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )

    # ── Subject (one of these must be set) ──
    organization_id = fields.Many2one(
        'vin.organization', string='Organization',
        index=True
    )
    partner_profile_id = fields.Many2one(
        'creative.partner.profile', string='Creative Partner',
        index=True
    )

    display_name = fields.Char(
        string='Display Name', compute='_compute_display_name', store=True
    )

    # ═══════════════════════════════════════════════════════
    # PUBLIC METRICS (Visible to all authenticated users)
    # ═══════════════════════════════════════════════════════
    public_avg_rating = fields.Float(
        string='Public Average Rating (1–5)',
        digits=(3, 2), readonly=True,
        help="Weighted average across all revealed, non-redacted reviews."
    )
    public_quality_avg = fields.Float(string='Avg Quality Rating', digits=(3, 2), readonly=True)
    public_communication_avg = fields.Float(string='Avg Communication Rating', digits=(3, 2), readonly=True)
    public_timeliness_avg = fields.Float(string='Avg Timeliness Rating', digits=(3, 2), readonly=True)
    public_professionalism_avg = fields.Float(string='Avg Professionalism Rating', digits=(3, 2), readonly=True)
    public_value_avg = fields.Float(string='Avg Value Rating', digits=(3, 2), readonly=True)

    total_reviews_received = fields.Integer(string='Total Reviews Received', readonly=True, default=0)
    total_projects_completed = fields.Integer(string='Total Projects Completed', readonly=True, default=0)
    on_time_delivery_rate = fields.Float(
        string='On-Time Delivery Rate (%)',
        digits=(5, 2), readonly=True,
        help="Percentage of milestones delivered on or before deadline."
    )
    first_submission_acceptance_rate = fields.Float(
        string='First-Submission Acceptance Rate (%)',
        digits=(5, 2), readonly=True,
        help="Percentage of deliverables accepted on the first submission."
    )
    repeat_client_rate = fields.Float(
        string='Repeat Client Rate (%)',
        digits=(5, 2), readonly=True,
        help="Percentage of engagements from returning clients."
    )

    # ═══════════════════════════════════════════════════════
    # INTERNAL TRUST SCORE (NEVER exposed to public APIs)
    # ═══════════════════════════════════════════════════════
    internal_trust_score = fields.Float(
        string='Internal Trust Score',
        digits=(8, 4), readonly=True, default=500.0,
        help="Internal platform trust score (0–1000). "
             "This value is NEVER exposed via public API. "
             "Used for platform-internal risk assessment and matching priority."
    )
    trust_tier = fields.Selection([
        ('untrusted', 'Untrusted (0–199)'),
        ('provisional', 'Provisional (200–399)'),
        ('standard', 'Standard (400–599)'),
        ('trusted', 'Trusted (600–799)'),
        ('elite', 'Elite (800–1000)'),
    ], string='Trust Tier', readonly=True, default='standard',
       help="Internal trust tier. NEVER exposed to public APIs."
    )
    trust_events_count = fields.Integer(
        string='Total Trust Events', readonly=True, default=0
    )
    last_recalculated_at = fields.Datetime(
        string='Last Recalculated At', readonly=True
    )

    @api.depends('organization_id', 'partner_profile_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_profile_id:
                rec.display_name = "Rep: %s" % rec.partner_profile_id.display_name
            elif rec.organization_id:
                rec.display_name = "Rep: %s" % rec.organization_id.name
            else:
                rec.display_name = "Rep: %s" % rec.uuid[:8]

    @api.constrains('organization_id', 'partner_profile_id')
    def _check_subject_required(self):
        for rec in self:
            if not rec.organization_id and not rec.partner_profile_id:
                raise ValidationError(_(
                    "Reputation score must have at least one subject "
                    "(organization or partner profile)."
                ))

    @api.constrains('internal_trust_score')
    def _check_trust_score_bounds(self):
        for rec in self:
            if rec.internal_trust_score < 0 or rec.internal_trust_score > 1000:
                raise ValidationError(_(
                    "Internal trust score must be between 0 and 1000. Got: %s"
                ) % rec.internal_trust_score)

    def _update_trust_tier(self):
        """Recalculate trust tier based on current internal trust score."""
        for rec in self:
            score = rec.internal_trust_score
            if score < 200:
                tier = 'untrusted'
            elif score < 400:
                tier = 'provisional'
            elif score < 600:
                tier = 'standard'
            elif score < 800:
                tier = 'trusted'
            else:
                tier = 'elite'
            if rec.trust_tier != tier:
                rec.write({'trust_tier': tier})
