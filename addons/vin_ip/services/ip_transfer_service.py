# -*- coding: utf-8 -*-
"""
IP Transfer Orchestration Service (Q137–Q146, AC-05).
Bridges vin_execution (milestone acceptance), vin_escrow (escrow release verification),
and vin_ip (deed execution + portfolio grant creation).
"""
import json
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IPTransferService(models.AbstractModel):
    """
    Orchestrates the payment-gated IP transfer workflow:
      1. Verify milestone has been accepted
      2. Verify escrow allocation has been released
      3. Execute IP assignment deed (SHA-256 sealed)
      4. Auto-create portfolio display grant if permitted
      5. Emit IP_TRANSFER_COMPLETED audit event
    """
    _name = 'vin.ip.transfer.service'
    _description = 'VIN IP Transfer Orchestration Service'

    @api.model
    def execute_transfer(self, ip_assignment_id):
        """
        Executes the full payment-gated IP transfer workflow.

        Args:
            ip_assignment_id: int — ID of the vin.ip.assignment deed to execute.

        Returns:
            dict — Result payload with deed number, SHA-256 hash, and portfolio grant status.

        Raises:
            UserError: If preconditions (milestone acceptance, escrow release) are not met.
        """
        assignment = self.env['vin.ip.assignment'].browse(ip_assignment_id)
        if not assignment.exists():
            raise UserError(_("IP Assignment deed not found."))

        if assignment.state != 'pending_payment':
            raise UserError(_("IP Assignment deed must be in 'pending_payment' state to execute transfer."))

        # ── Gate 1: Verify milestone acceptance ──
        milestone = assignment.milestone_id
        if milestone:
            if not hasattr(milestone, 'state') or milestone.state not in ('accepted', 'completed'):
                raise UserError(_(
                    "Cannot transfer IP: Milestone '%s' has not been accepted. "
                    "Current state: %s"
                ) % (milestone.display_name, getattr(milestone, 'state', 'unknown')))

        # ── Gate 2: Verify escrow release (if escrow module available) ──
        if 'vin.escrow.allocation' in self.env:
            escrow_allocations = self.env['vin.escrow.allocation'].search([
                ('milestone_id', '=', milestone.id if milestone else False),
                ('tenant_id', '=', assignment.tenant_id.id),
            ])
            if escrow_allocations:
                unreleased = escrow_allocations.filtered(
                    lambda a: getattr(a, 'state', 'locked') != 'released'
                )
                if unreleased:
                    raise UserError(_(
                        "Cannot transfer IP: %d escrow allocation(s) are still locked. "
                        "All milestone payments must be released before IP transfer."
                    ) % len(unreleased))

        # ── Gate 3: Execute the assignment deed ──
        assignment.action_execute_assignment()
        _logger.info(
            "IP Transfer executed: deed=%s, hash=%s, grant_type=%s",
            assignment.assignment_number,
            assignment.sha256_hash,
            assignment.grant_type
        )

        # ── Gate 4: Auto-create portfolio display grant ──
        portfolio_grant = None
        if assignment.portfolio_display_permitted and assignment.partner_profile_id:
            grant_vals = {
                'tenant_id': assignment.tenant_id.id,
                'partner_profile_id': assignment.partner_profile_id.id,
                'contract_id': assignment.contract_id.id,
                'deliverable_id': assignment.deliverable_id.id if assignment.deliverable_id else False,
                'status': 'pending',
            }
            # Apply embargo if configured on assignment
            if assignment.portfolio_embargo_date:
                grant_vals['embargo_date'] = assignment.portfolio_embargo_date
                grant_vals['status'] = 'embargoed'

            portfolio_grant = self.env['vin.portfolio.display.grant'].create(grant_vals)
            _logger.info(
                "Portfolio display grant auto-created: grant=%s, status=%s",
                portfolio_grant.uuid,
                portfolio_grant.status
            )

        # ── Gate 5: Emit IP_TRANSFER_COMPLETED audit event ──
        if 'vin.audit.event' in self.env:
            self.env['vin.audit.event'].sudo().create({
                'tenant_id': assignment.tenant_id.id,
                'actor_user_id': self.env.user.id,
                'event_type': 'IP_TRANSFER_COMPLETED',
                'entity_name': 'vin.ip.assignment',
                'entity_id': str(assignment.id),
                'state_after': 'assigned',
                'payload': json.dumps({
                    'assignment_number': assignment.assignment_number,
                    'grant_type': assignment.grant_type,
                    'sha256_seal': assignment.sha256_hash,
                    'portfolio_grant_created': bool(portfolio_grant),
                    'portfolio_grant_uuid': portfolio_grant.uuid if portfolio_grant else None,
                })
            })

        return {
            'assignment_number': assignment.assignment_number,
            'sha256_hash': assignment.sha256_hash,
            'state': assignment.state,
            'portfolio_grant_id': portfolio_grant.id if portfolio_grant else None,
            'portfolio_grant_status': portfolio_grant.status if portfolio_grant else None,
        }

    @api.model
    def revoke_on_chargeback(self, ip_assignment_id, reason=None):
        """
        Revokes IP assignment deed due to payment chargeback or breach.
        Also revokes any associated portfolio display grants.

        Args:
            ip_assignment_id: int — ID of the vin.ip.assignment deed.
            reason: str — Reason for revocation.
        """
        assignment = self.env['vin.ip.assignment'].browse(ip_assignment_id)
        if not assignment.exists():
            raise UserError(_("IP Assignment deed not found."))

        if assignment.state != 'assigned':
            raise UserError(_("Can only revoke assigned deeds."))

        # Revoke deed
        revocation_reason = reason or _("Payment chargeback or contractual breach detected.")
        assignment.action_revoke(reason=revocation_reason)

        # Revoke all associated portfolio display grants
        grants = self.env['vin.portfolio.display.grant'].search([
            ('contract_id', '=', assignment.contract_id.id),
            ('partner_profile_id', '=', assignment.partner_profile_id.id),
            ('status', 'in', ['approved', 'embargoed', 'pending']),
        ])
        for grant in grants:
            grant.action_reject_nda(reason=_(
                "Portfolio display revoked: IP assignment '%s' has been revoked due to: %s"
            ) % (assignment.assignment_number, revocation_reason))

        # Audit event
        if 'vin.audit.event' in self.env:
            self.env['vin.audit.event'].sudo().create({
                'tenant_id': assignment.tenant_id.id,
                'actor_user_id': self.env.user.id,
                'event_type': 'IP_TRANSFER_REVOKED',
                'entity_name': 'vin.ip.assignment',
                'entity_id': str(assignment.id),
                'state_after': 'revoked',
                'payload': json.dumps({
                    'assignment_number': assignment.assignment_number,
                    'reason': revocation_reason,
                    'grants_revoked': len(grants),
                })
            })

        _logger.warning(
            "IP Assignment revoked: deed=%s, reason=%s, grants_revoked=%d",
            assignment.assignment_number,
            revocation_reason,
            len(grants)
        )
