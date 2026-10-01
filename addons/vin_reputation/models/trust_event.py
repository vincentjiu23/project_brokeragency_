# -*- coding: utf-8 -*-
"""
Internal Trust Event Model (Q137–Q146 Reputation Domain).
Records platform-internal behavioral signals that contribute to hidden trust scores.
Trust events are NEVER exposed to public APIs — internal platform use only.
"""
import uuid
import json
from decimal import Decimal, ROUND_HALF_UP
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class VinTrustEvent(models.Model):
    """
    Internal Trust Scoring Event.
    Records behavioral signals (positive and negative) that feed the internal trust
    score calculator. These events are append-only and never visible to end users.

    Event Categories:
      - DELIVERY: On-time delivery, quality acceptance, revision count
      - PAYMENT: On-time payment, chargeback, payment disputes
      - COMMUNICATION: Response time, professionalism flags
      - COMPLIANCE: KYC/KYB completion, policy violations
      - DISPUTE: Dispute outcomes (won/lost/settled)
    """
    _name = 'vin.trust.event'
    _description = 'VIN Internal Trust Event (Hidden)'
    _order = 'event_date desc, id desc'
    _rec_name = 'event_type'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )

    # ── Subject ──
    subject_organization_id = fields.Many2one(
        'vin.organization', string='Subject Organization',
        index=True, readonly=True,
        help="Organization whose trust score is affected."
    )
    subject_partner_id = fields.Many2one(
        'creative.partner.profile', string='Subject Partner Profile',
        index=True, readonly=True,
        help="Creative partner whose trust score is affected."
    )

    # ── Event Classification ──
    event_category = fields.Selection([
        ('delivery', 'Delivery Performance'),
        ('payment', 'Payment Behavior'),
        ('communication', 'Communication Quality'),
        ('compliance', 'Compliance & Verification'),
        ('dispute', 'Dispute Outcome'),
        ('platform', 'Platform Engagement'),
    ], string='Event Category', required=True, index=True, readonly=True)

    event_type = fields.Selection([
        # Delivery
        ('milestone_on_time', 'Milestone Delivered On Time'),
        ('milestone_late', 'Milestone Delivered Late'),
        ('milestone_early', 'Milestone Delivered Early'),
        ('deliverable_accepted_first', 'Deliverable Accepted on First Submission'),
        ('deliverable_revision_required', 'Deliverable Required Revision'),
        ('quality_exceeds_expectations', 'Quality Exceeded Expectations'),
        # Payment
        ('payment_on_time', 'Payment Made On Time'),
        ('payment_late', 'Payment Made Late'),
        ('chargeback_filed', 'Chargeback Filed Against Transaction'),
        ('chargeback_reversed', 'Chargeback Reversed in Favor'),
        # Communication
        ('response_within_sla', 'Response Within SLA Window'),
        ('response_beyond_sla', 'Response Beyond SLA Window'),
        ('professional_conduct', 'Professional Conduct Noted'),
        ('unprofessional_conduct', 'Unprofessional Conduct Reported'),
        # Compliance
        ('kyc_verified', 'KYC/KYB Verification Completed'),
        ('policy_violation', 'Platform Policy Violation'),
        ('account_warning', 'Account Warning Issued'),
        # Dispute
        ('dispute_won', 'Dispute Resolved in Favor'),
        ('dispute_lost', 'Dispute Resolved Against'),
        ('dispute_settled', 'Dispute Settled by Mutual Agreement'),
        # Platform
        ('project_completed_successfully', 'Project Completed Successfully'),
        ('repeat_engagement', 'Repeat Client/Partner Engagement'),
    ], string='Trust Event Type', required=True, index=True, readonly=True)

    # ── Scoring Impact ──
    score_delta = fields.Float(
        string='Score Delta',
        required=True, readonly=True,
        help="Positive = trust increase, Negative = trust decrease. "
             "Magnitude reflects severity (e.g., chargeback = -50, on-time = +5)."
    )
    weight = fields.Float(
        string='Decay Weight',
        default=1.0, required=True, readonly=True,
        help="Time-decay weight factor. Recent events have weight=1.0; "
             "older events are decayed by the trust score calculator."
    )

    # ── Context ──
    contract_id = fields.Many2one(
        'vin.contract', string='Contract Reference',
        index=True, readonly=True
    )
    milestone_id = fields.Many2one(
        'vin.milestone', string='Milestone Reference',
        index=True, readonly=True
    )
    related_entity = fields.Char(
        string='Related Entity Reference',
        readonly=True,
        help="Freeform reference to the triggering entity (e.g., dispute ID, payout ID)."
    )

    event_date = fields.Datetime(
        string='Event Date', default=fields.Datetime.now,
        required=True, readonly=True, index=True
    )
    notes = fields.Text(string='Internal Notes', readonly=True)

    @api.constrains('score_delta')
    def _check_score_delta_range(self):
        """Ensure score delta is within reasonable bounds."""
        for rec in self:
            if abs(rec.score_delta) > 100:
                raise ValidationError(_(
                    "Trust event score delta must be between -100 and +100. Got: %s"
                ) % rec.score_delta)

    @api.constrains('subject_organization_id', 'subject_partner_id')
    def _check_subject_required(self):
        """At least one subject must be set."""
        for rec in self:
            if not rec.subject_organization_id and not rec.subject_partner_id:
                raise ValidationError(_(
                    "Trust event must have at least one subject "
                    "(organization or partner profile)."
                ))

    def write(self, vals):
        """Trust events are append-only — no modifications allowed."""
        # Allow only internal system fields to be written
        allowed_fields = {'weight'}  # Weight can be updated by decay process
        modifying_fields = set(vals.keys()) - allowed_fields
        if modifying_fields:
            raise ValidationError(_(
                "Trust events are append-only and cannot be modified. "
                "Attempted to modify: %s"
            ) % ', '.join(modifying_fields))
        return super().write(vals)

    def unlink(self):
        """Trust events cannot be deleted — append-only."""
        raise ValidationError(_("Trust events cannot be deleted. They are append-only records."))
