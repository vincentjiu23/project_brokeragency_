# -*- coding: utf-8 -*-
"""
Trust Score Calculator Service (Q137–Q146 Reputation Domain).
Recalculates internal trust scores from trust events with time-decay weighting,
and recomputes public review aggregates from revealed reviews.
"""
import json
import logging
import math
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ── Trust Event Score Deltas (default magnitudes) ──
TRUST_EVENT_DELTAS = {
    # Delivery (positive)
    'milestone_on_time': 5.0,
    'milestone_early': 8.0,
    'deliverable_accepted_first': 10.0,
    'quality_exceeds_expectations': 15.0,
    # Delivery (negative)
    'milestone_late': -10.0,
    'deliverable_revision_required': -3.0,
    # Payment (positive)
    'payment_on_time': 5.0,
    'chargeback_reversed': 10.0,
    # Payment (negative)
    'payment_late': -8.0,
    'chargeback_filed': -50.0,
    # Communication
    'response_within_sla': 3.0,
    'response_beyond_sla': -5.0,
    'professional_conduct': 5.0,
    'unprofessional_conduct': -15.0,
    # Compliance
    'kyc_verified': 10.0,
    'policy_violation': -30.0,
    'account_warning': -20.0,
    # Dispute
    'dispute_won': 10.0,
    'dispute_lost': -25.0,
    'dispute_settled': -5.0,
    # Platform
    'project_completed_successfully': 10.0,
    'repeat_engagement': 15.0,
}

# Time-decay half-life in days (events older than this are worth 50%)
DECAY_HALF_LIFE_DAYS = 180


class TrustScoreCalculator(models.AbstractModel):
    """
    Internal Trust Score Calculator.

    Responsibilities:
      1. Record trust events with appropriate score deltas
      2. Recalculate aggregate trust scores with exponential time-decay
      3. Recompute public review averages from revealed reviews
      4. Update trust tiers based on recalculated scores
    """
    _name = 'vin.trust.score.calculator'
    _description = 'VIN Trust Score Calculator Service'

    @api.model
    def record_trust_event(self, tenant_id, event_type, event_category,
                           subject_organization_id=None, subject_partner_id=None,
                           contract_id=None, milestone_id=None,
                           related_entity=None, notes=None,
                           score_delta_override=None):
        """
        Records a new trust event and triggers score recalculation.

        Args:
            tenant_id: int — Tenant ID
            event_type: str — Trust event type code
            event_category: str — Event category
            subject_organization_id: int — Organization subject (optional)
            subject_partner_id: int — Partner profile subject (optional)
            contract_id: int — Related contract (optional)
            milestone_id: int — Related milestone (optional)
            related_entity: str — Freeform reference to triggering entity
            notes: str — Internal notes
            score_delta_override: float — Override default score delta

        Returns:
            vin.trust.event record
        """
        # Determine score delta
        if score_delta_override is not None:
            score_delta = score_delta_override
        else:
            score_delta = TRUST_EVENT_DELTAS.get(event_type, 0.0)

        if score_delta == 0.0:
            _logger.warning(
                "Trust event '%s' has zero score delta. "
                "Consider adding it to TRUST_EVENT_DELTAS.",
                event_type
            )

        event = self.env['vin.trust.event'].create({
            'tenant_id': tenant_id,
            'event_type': event_type,
            'event_category': event_category,
            'subject_organization_id': subject_organization_id,
            'subject_partner_id': subject_partner_id,
            'contract_id': contract_id,
            'milestone_id': milestone_id,
            'related_entity': related_entity,
            'notes': notes,
            'score_delta': score_delta,
            'weight': 1.0,
        })

        # Trigger asynchronous recalculation
        self._recalculate_trust_score(
            tenant_id=tenant_id,
            organization_id=subject_organization_id,
            partner_id=subject_partner_id
        )

        # Emit audit event
        if 'vin.audit.event' in self.env:
            self.env['vin.audit.event'].sudo().create({
                'tenant_id': tenant_id,
                'actor_user_id': self.env.user.id,
                'event_type': 'TRUST_EVENT_RECORDED',
                'entity_name': 'vin.trust.event',
                'entity_id': str(event.id),
                'state_after': event_type,
                'payload': json.dumps({
                    'event_type': event_type,
                    'category': event_category,
                    'score_delta': score_delta,
                    'subject_org': subject_organization_id,
                    'subject_partner': subject_partner_id,
                })
            })

        return event

    @api.model
    def _recalculate_trust_score(self, tenant_id, organization_id=None, partner_id=None):
        """
        Recalculates the aggregate internal trust score using exponential time-decay.

        Score = clamp(500 + Σ(delta_i * decay_weight_i), 0, 1000)

        Where decay_weight_i = 2^(-age_in_days / DECAY_HALF_LIFE_DAYS)
        """
        ReputationScore = self.env['vin.reputation.score']
        TrustEvent = self.env['vin.trust.event']

        # Find or create reputation score record
        domain = [('tenant_id', '=', tenant_id)]
        if partner_id:
            domain.append(('partner_profile_id', '=', partner_id))
        elif organization_id:
            domain.append(('organization_id', '=', organization_id))
        else:
            return

        score_record = ReputationScore.search(domain, limit=1)
        if not score_record:
            score_record = ReputationScore.create({
                'tenant_id': tenant_id,
                'organization_id': organization_id,
                'partner_profile_id': partner_id,
            })

        # Fetch all trust events for this subject
        event_domain = [('tenant_id', '=', tenant_id)]
        if partner_id:
            event_domain.append(('subject_partner_id', '=', partner_id))
        elif organization_id:
            event_domain.append(('subject_organization_id', '=', organization_id))

        events = TrustEvent.search(event_domain)
        now = fields.Datetime.now()

        # Calculate time-decayed trust score
        base_score = 500.0
        total_weighted_delta = 0.0

        for event in events:
            if event.event_date:
                age_days = (now - event.event_date).total_seconds() / 86400.0
            else:
                age_days = 0.0

            # Exponential time-decay: recent events matter more
            decay_weight = math.pow(2, -age_days / DECAY_HALF_LIFE_DAYS)
            total_weighted_delta += event.score_delta * decay_weight

        # Clamp to [0, 1000]
        final_score = max(0.0, min(1000.0, base_score + total_weighted_delta))

        score_record.write({
            'internal_trust_score': final_score,
            'trust_events_count': len(events),
            'last_recalculated_at': now,
        })
        score_record._update_trust_tier()

        _logger.info(
            "Trust score recalculated: subject=%s, events=%d, score=%.4f, tier=%s",
            partner_id or organization_id,
            len(events),
            final_score,
            score_record.trust_tier
        )

    @api.model
    def recalculate_public_metrics(self, tenant_id, organization_id=None, partner_id=None):
        """
        Recomputes public review averages from revealed, non-redacted reviews.
        Called after review reveals or moderation actions.
        """
        Review = self.env['vin.review']
        ReputationScore = self.env['vin.reputation.score']

        # Find reputation score record
        domain = [('tenant_id', '=', tenant_id)]
        if partner_id:
            domain.append(('partner_profile_id', '=', partner_id))
        elif organization_id:
            domain.append(('organization_id', '=', organization_id))
        else:
            return

        score_record = ReputationScore.search(domain, limit=1)
        if not score_record:
            score_record = ReputationScore.create({
                'tenant_id': tenant_id,
                'organization_id': organization_id,
                'partner_profile_id': partner_id,
            })

        # Fetch revealed, non-redacted reviews for this subject
        review_domain = [
            ('tenant_id', '=', tenant_id),
            ('state', '=', 'revealed'),
        ]
        if partner_id:
            review_domain.append(('reviewee_partner_id', '=', partner_id))
        elif organization_id:
            review_domain.append(('reviewee_organization_id', '=', organization_id))

        reviews = Review.search(review_domain)
        count = len(reviews)

        if count == 0:
            score_record.write({
                'public_avg_rating': 0.0,
                'public_quality_avg': 0.0,
                'public_communication_avg': 0.0,
                'public_timeliness_avg': 0.0,
                'public_professionalism_avg': 0.0,
                'public_value_avg': 0.0,
                'total_reviews_received': 0,
            })
            return

        # Calculate averages
        def safe_avg(field_name):
            values = [getattr(r, field_name) for r in reviews if getattr(r, field_name, 0)]
            return sum(values) / len(values) if values else 0.0

        score_record.write({
            'public_avg_rating': safe_avg('overall_rating'),
            'public_quality_avg': safe_avg('quality_rating'),
            'public_communication_avg': safe_avg('communication_rating'),
            'public_timeliness_avg': safe_avg('timeliness_rating'),
            'public_professionalism_avg': safe_avg('professionalism_rating'),
            'public_value_avg': safe_avg('value_rating'),
            'total_reviews_received': count,
            'last_recalculated_at': fields.Datetime.now(),
        })

        _logger.info(
            "Public metrics recalculated: subject=%s, reviews=%d, avg=%.2f",
            partner_id or organization_id,
            count,
            score_record.public_avg_rating
        )
