# -*- coding: utf-8 -*-
"""
Public Peer Review Model (Q137–Q146 Reputation Domain).
Two-way dual-blind review submitted after project completion.
Public star ratings derive from verified, platform-mediated reviews only.
"""
import uuid
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class VinReview(models.Model):
    """
    Dual-Blind Public Peer Review Record.
    After project completion, both client and partner submit independent reviews.
    Reviews remain sealed until both parties submit (dual-blind reveal).
    Once revealed, reviews are append-only and cannot be edited or deleted.
    """
    _name = 'vin.review'
    _description = 'VIN Public Peer Review'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )

    # ── Linkage ──
    contract_id = fields.Many2one(
        'vin.contract', string='Contract Reference',
        required=True, index=True, readonly=True
    )
    project_id = fields.Many2one(
        'vin.master.project', string='Master Project',
        related='contract_id.project_id', store=True, index=True
    )

    # ── Reviewer / Reviewee ──
    reviewer_organization_id = fields.Many2one(
        'vin.organization', string='Reviewer Organization',
        required=True, index=True, readonly=True
    )
    reviewee_organization_id = fields.Many2one(
        'vin.organization', string='Reviewee Organization',
        index=True, readonly=True
    )
    reviewee_partner_id = fields.Many2one(
        'creative.partner.profile', string='Reviewee Partner',
        index=True, readonly=True
    )
    review_direction = fields.Selection([
        ('client_to_partner', 'Client → Partner Review'),
        ('partner_to_client', 'Partner → Client Review'),
    ], string='Review Direction', required=True, readonly=True)

    # ── Ratings (1–5 scale, enforced by constraint) ──
    overall_rating = fields.Float(
        string='Overall Rating (1–5)', required=True,
        help="Primary public star rating."
    )
    quality_rating = fields.Float(string='Quality of Deliverables (1–5)')
    communication_rating = fields.Float(string='Communication & Responsiveness (1–5)')
    timeliness_rating = fields.Float(string='Timeliness & Deadline Adherence (1–5)')
    professionalism_rating = fields.Float(string='Professionalism (1–5)')
    value_rating = fields.Float(string='Value for Investment (1–5)')

    # ── Written Feedback ──
    public_comment = fields.Text(
        string='Public Review Comment',
        help="Visible to both parties and the platform after dual-blind reveal."
    )
    private_feedback = fields.Text(
        string='Private Platform Feedback',
        help="Visible only to platform administrators. Never exposed via public API."
    )

    # ── Dual-Blind Mechanism ──
    state = fields.Selection([
        ('sealed', 'Sealed (Awaiting Counter-Party Review)'),
        ('revealed', 'Revealed (Both Reviews Submitted)'),
        ('flagged', 'Flagged for Moderation'),
        ('redacted', 'Redacted by Platform Moderator'),
    ], string='Review Status', default='sealed', required=True, tracking=True)

    counterpart_review_id = fields.Many2one(
        'vin.review', string='Counter-Party Review',
        index=True, readonly=True,
        help="Link to the other party's review for the same contract."
    )
    revealed_at = fields.Datetime(string='Dual-Blind Reveal Timestamp', readonly=True)

    # ── Integrity ──
    sha256_hash = fields.Char(string='Review SHA-256 Seal', readonly=True, copy=False)

    @api.constrains('overall_rating', 'quality_rating', 'communication_rating',
                    'timeliness_rating', 'professionalism_rating', 'value_rating')
    def _check_rating_bounds(self):
        """Enforce 1.0–5.0 range for all rating fields."""
        rating_fields = [
            'overall_rating', 'quality_rating', 'communication_rating',
            'timeliness_rating', 'professionalism_rating', 'value_rating'
        ]
        for rec in self:
            for field_name in rating_fields:
                value = getattr(rec, field_name, 0.0)
                if value and (value < 1.0 or value > 5.0):
                    raise ValidationError(_(
                        "Rating '%s' must be between 1.0 and 5.0. Got: %s"
                    ) % (field_name, value))

    @api.model_create_multi
    def create(self, vals_list):
        """Seal review on creation with SHA-256 hash and check for dual-blind reveal."""
        records = super().create(vals_list)
        for rec in records:
            # Generate SHA-256 seal for immutability
            payload = {
                'uuid': rec.uuid,
                'contract_id': rec.contract_id.id,
                'direction': rec.review_direction,
                'overall_rating': rec.overall_rating,
                'quality_rating': rec.quality_rating or 0,
                'communication_rating': rec.communication_rating or 0,
                'timeliness_rating': rec.timeliness_rating or 0,
                'professionalism_rating': rec.professionalism_rating or 0,
                'value_rating': rec.value_rating or 0,
                'public_comment': rec.public_comment or '',
            }
            raw = json.dumps(payload, sort_keys=True)
            digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
            rec.write({'sha256_hash': digest})

            # Check for dual-blind reveal
            rec._check_dual_blind_reveal()

        return records

    def _check_dual_blind_reveal(self):
        """
        Dual-blind reveal: if both parties have submitted reviews for the same contract,
        reveal both simultaneously.
        """
        for rec in self:
            if rec.state != 'sealed':
                continue

            # Find counter-party review
            opposite_direction = (
                'partner_to_client' if rec.review_direction == 'client_to_partner'
                else 'client_to_partner'
            )
            counterpart = self.search([
                ('contract_id', '=', rec.contract_id.id),
                ('tenant_id', '=', rec.tenant_id.id),
                ('review_direction', '=', opposite_direction),
                ('state', '=', 'sealed'),
            ], limit=1)

            if counterpart:
                reveal_ts = fields.Datetime.now()
                # Reveal both reviews simultaneously
                rec.write({
                    'state': 'revealed',
                    'counterpart_review_id': counterpart.id,
                    'revealed_at': reveal_ts,
                })
                counterpart.write({
                    'state': 'revealed',
                    'counterpart_review_id': rec.id,
                    'revealed_at': reveal_ts,
                })

                # Emit REVIEW_REVEALED audit event
                if 'vin.audit.event' in self.env:
                    self.env['vin.audit.event'].sudo().create({
                        'tenant_id': rec.tenant_id.id,
                        'actor_user_id': self.env.user.id,
                        'event_type': 'REVIEW_REVEALED',
                        'entity_name': 'vin.review',
                        'entity_id': str(rec.id),
                        'state_after': 'revealed',
                        'payload': json.dumps({
                            'contract_id': rec.contract_id.id,
                            'review_uuid': rec.uuid,
                            'counterpart_uuid': counterpart.uuid,
                        })
                    })

    def action_flag_for_moderation(self, reason=None):
        """Flag review for platform moderator review."""
        for rec in self:
            if rec.state == 'redacted':
                raise UserError(_("Cannot flag a redacted review."))
            rec.write({'state': 'flagged'})
            rec.message_post(body=_(
                "Review flagged for moderation. Reason: %s"
            ) % (reason or "Reported by counter-party."))

    def action_redact(self, moderator_note=None):
        """Platform moderator redacts a fraudulent or abusive review."""
        for rec in self:
            rec.write({'state': 'redacted'})
            rec.message_post(body=_(
                "Review redacted by platform moderator. Note: %s"
            ) % (moderator_note or "Policy violation detected."))

            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'REVIEW_REDACTED',
                    'entity_name': 'vin.review',
                    'entity_id': str(rec.id),
                    'state_after': 'redacted',
                    'payload': json.dumps({
                        'review_uuid': rec.uuid,
                        'moderator_note': moderator_note or '',
                    })
                })

    def write(self, vals):
        """Prevent mutation of revealed/sealed reviews (append-only principle)."""
        immutable_fields = {'overall_rating', 'quality_rating', 'communication_rating',
                           'timeliness_rating', 'professionalism_rating', 'value_rating',
                           'public_comment', 'review_direction', 'contract_id'}
        mutating_fields = set(vals.keys()) & immutable_fields
        if mutating_fields:
            for rec in self:
                if rec.state in ('revealed', 'sealed') and rec.sha256_hash:
                    raise UserError(_(
                        "Cannot modify sealed/revealed review fields: %s. "
                        "Reviews are append-only once submitted."
                    ) % ', '.join(mutating_fields))
        return super().write(vals)
