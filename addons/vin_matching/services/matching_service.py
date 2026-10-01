# -*- coding: utf-8 -*-
from datetime import timedelta
import logging
from odoo import fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class MatchingEngineService:
    """Deterministic Hard Eligibility Gate and Contextual Ranking Service for Project Briefs."""

    def __init__(self, env):
        self.env = env

    def evaluate_hard_eligibility(self, brief, partner_profile):
        """
        Evaluates deterministic hard eligibility criteria (AC-01 & Locked Decision Q26-Q40).
        CRITICAL INVARIANT: Hard eligibility CANNOT be bypassed by paid subscription tiers!
        """
        # 1. Tenant boundary check
        if partner_profile.tenant_id != brief.tenant_id:
            return False, "Cross-tenant mismatch: Partner profile outside brief tenant."

        # 2. Partner Verification Status Gate
        if partner_profile.verification_status not in ('verified', 'featured'):
            return False, f"Partner verification status is '{partner_profile.verification_status}' (must be verified or featured)."

        # 3. Availability State Gate
        if partner_profile.availability_state == 'unavailable':
            return False, "Partner availability state is currently 'unavailable'."

        # 4. Target Account Type Compatibility Gate
        if brief.target_account_type != 'both' and partner_profile.account_type != brief.target_account_type:
            return False, f"Account type mismatch: Brief requires '{brief.target_account_type}', partner is '{partner_profile.account_type}'."

        return True, None

    def compute_match_scores(self, brief, partner_profile):
        """Calculates multi-dimensional fit scores for an eligible candidate."""
        # A. Expertise overlap score
        req_skills = set(brief.required_expertise_ids.ids)
        if req_skills:
            partner_skills = set(partner_profile.expertise_ids.ids)
            overlap = len(req_skills.intersection(partner_skills))
            expertise_score = round((overlap / len(req_skills)) * 100.0, 2)
        else:
            expertise_score = 100.0

        # B. Public Reputation & SLA score
        rating = partner_profile.public_rating or 5.0
        reputation_score = round((rating / 5.0) * 100.0, 2)

        # C. Weighted overall score (60% skill fit, 40% reputation fit)
        overall_score = round((0.60 * expertise_score) + (0.40 * reputation_score), 2)

        return {
            'overall_score': overall_score,
            'expertise_match_score': expertise_score,
            'reputation_score': reputation_score
        }

    def execute_matching(self, brief_id):
        """
        Executes candidate screening against a project brief.
        AC-01: Only hard-eligible candidates are included in the finalized match snapshot.
        """
        brief = self.env['vin.project.brief'].browse(brief_id)
        if not brief.exists():
            raise UserError(_("Project brief %s not found.") % brief_id)

        # Retrieve all candidate partner profiles in this tenant
        candidates_pool = self.env['creative.partner.profile'].search([
            ('tenant_id', '=', brief.tenant_id.id)
        ])

        total_screened = len(candidates_pool)
        eligible_candidates = []

        for partner in candidates_pool:
            is_eligible, reason = self.evaluate_hard_eligibility(brief, partner)
            if is_eligible:
                scores = self.compute_match_scores(brief, partner)
                eligible_candidates.append({
                    'partner_profile_id': partner.id,
                    'hard_eligibility_passed': True,
                    'disqualification_reason': False,
                    **scores
                })

        # Rank eligible candidates descending by overall_score
        eligible_candidates.sort(key=lambda x: x['overall_score'], reverse=True)
        for idx, candidate in enumerate(eligible_candidates, start=1):
            candidate['rank'] = idx

        # Create immutable match snapshot
        snapshot = self.env['vin.match.snapshot'].create({
            'brief_id': brief.id,
            'tenant_id': brief.tenant_id.id,
            'total_candidates_screened': total_screened,
            'total_eligible_matched': len(eligible_candidates),
            'algorithm_version': 'v1.0.0-deterministic-ranker',
            'state': 'frozen',
            'candidate_ids': [(0, 0, cand) for cand in eligible_candidates]
        })

        # Record audit event
        self.env['vin.audit.event'].sudo().record_event(
            action='MATCH_SNAPSHOT_CREATED',
            subject_type='vin.match.snapshot',
            subject_id=snapshot.uuid,
            tenant_id=brief.tenant_id.uuid,
            payload={
                'brief_uuid': brief.uuid,
                'total_screened': total_screened,
                'total_eligible': len(eligible_candidates)
            }
        )

        return snapshot


class OpportunityDispatchService:
    """Dispatches blind RFQ opportunities to matched candidates with response SLA timers."""

    def __init__(self, env):
        self.env = env

    def dispatch_to_candidates(self, snapshot_id, top_n=5, sla_hours=48):
        """
        Dispatches opportunities to the top N candidates in a match snapshot.
        Enforces AC-02: Actionable notification emitted and response SLA timer started.
        """
        snapshot = self.env['vin.match.snapshot'].browse(snapshot_id)
        if not snapshot.exists():
            raise UserError(_("Match snapshot %s not found.") % snapshot_id)

        brief = snapshot.brief_id
        deadline = fields.Datetime.now() + timedelta(hours=sla_hours)

        # Prepare blind brief scope preview
        if brief.anonymity_mode == 'blind':
            blind_preview = (
                f"[BLIND RFQ - CLIENT ANONYMIZED]\n"
                f"Scope: {brief.scope_summary}\n"
                f"Budget: {brief.budget_min:,.2f} - {brief.budget_max:,.2f} {brief.currency_id.name}\n"
                f"Deadline: {brief.delivery_deadline}\n"
                f"Required Skills: {', '.join(brief.required_expertise_ids.mapped('name'))}"
            )
        else:
            blind_preview = (
                f"Client: {brief.client_organization_id.name}\n"
                f"Scope: {brief.scope_summary}\n"
                f"Budget: {brief.budget_min:,.2f} - {brief.budget_max:,.2f} {brief.currency_id.name}\n"
                f"Deadline: {brief.delivery_deadline}\n"
                f"Required Skills: {', '.join(brief.required_expertise_ids.mapped('name'))}"
            )

        dispatched_opportunities = self.env['vin.opportunity.record']
        target_candidates = snapshot.candidate_ids[:top_n]

        for cand in target_candidates:
            opp = self.env['vin.opportunity.record'].create({
                'brief_id': brief.id,
                'partner_profile_id': cand.partner_profile_id.id,
                'dispatched_at': fields.Datetime.now(),
                'expires_at': deadline,
                'state': 'dispatched',
                'blind_scope_summary': blind_preview,
                'client_disclosed': (brief.anonymity_mode == 'disclosed')
            })
            cand.write({'opportunity_id': opp.id})
            dispatched_opportunities |= opp

            # Record audit event (AC-02)
            self.env['vin.audit.event'].sudo().record_event(
                action='CONTACT_INITIATED',
                subject_type='vin.opportunity.record',
                subject_id=opp.uuid,
                tenant_id=brief.tenant_id.uuid,
                payload={
                    'brief_uuid': brief.uuid,
                    'partner_profile_uuid': cand.partner_profile_id.uuid,
                    'expires_at': str(deadline),
                    'anonymity_mode': brief.anonymity_mode
                }
            )

        brief.write({'state': 'shortlisted'})
        return dispatched_opportunities
