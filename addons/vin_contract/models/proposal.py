# -*- coding: utf-8 -*-
import json
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinContractProposal(models.Model):
    _name = 'vin.contract.proposal'
    _description = 'VIN Structured Proposal & Delta Snapshot'
    _order = 'version_no desc, create_date desc'

    uuid = fields.Char(
        string='Proposal UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    contract_id = fields.Many2one(
        'vin.contract',
        string='Contract Lineage',
        required=True,
        readonly=True,
        index=True,
        ondelete='cascade'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='contract_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    version_no = fields.Integer(
        string='Proposal Version',
        default=1,
        readonly=True
    )
    author_role = fields.Selection(
        [
            ('client', 'Client Initiated'),
            ('partner', 'Partner Counter-Proposal')
        ],
        string='Author Role',
        required=True
    )
    proposed_budget = fields.Monetary(
        string='Proposed Total Budget',
        currency_field='currency_id',
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='contract_id.currency_id',
        readonly=True
    )
    proposed_deadline = fields.Date(
        string='Proposed Completion Deadline',
        required=True
    )
    delta_snapshot = fields.Text(
        string='Scope / Terms Delta JSON'
    )
    state = fields.Selection(
        [
            ('draft', 'Draft Proposal'),
            ('submitted', 'Submitted for Review'),
            ('accepted', 'Accepted into Contract'),
            ('superseded', 'Superseded by Newer Revision'),
            ('rejected', 'Rejected')
        ],
        string='Proposal State',
        required=True,
        default='draft',
        index=True
    )

    def action_submit_proposal(self):
        """
        Submits structured proposal.
        AC-03: Material change to budget/timeline triggers automatic invalidation of prior approvals.
        """
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft proposals can be submitted."))
            
            contract = record.contract_id
            
            # Check for material delta
            budget_delta = abs(record.proposed_budget - contract.total_contract_value)
            timeline_changed = (record.proposed_deadline != contract.completion_deadline)
            is_material = (budget_delta > 0) or timeline_changed

            record.write({'state': 'submitted'})

            # Emit PROPOSAL_SUBMITTED audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='PROPOSAL_SUBMITTED',
                subject_type='vin.contract.proposal',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'contract_uuid': contract.uuid,
                    'proposed_budget': float(record.proposed_budget),
                    'is_material': is_material
                }
            )

            # Invalidate prior approvals if material delta detected (AC-03)
            if is_material:
                reason = f"Material Proposal Delta: Budget delta={budget_delta}, Timeline changed={timeline_changed}"
                contract.invalidate_prior_approvals(reason)

        return True

    def action_accept_proposal(self):
        """Accepts proposal and integrates terms into draft contract."""
        for record in self:
            if record.state != 'submitted':
                raise UserError(_("Only submitted proposals can be accepted."))
            
            contract = record.contract_id
            if contract.state in ('active', 'amended', 'completed', 'terminated'):
                raise UserError(_("Cannot accept proposal on an active or finalized contract. Use Change Requests."))

            contract.write({
                'total_contract_value': record.proposed_budget,
                'completion_deadline': record.proposed_deadline
            })
            record.write({'state': 'accepted'})
            
            # Mark other pending proposals as superseded
            other_proposals = contract.proposal_ids.filtered(lambda p: p.id != record.id and p.state in ('draft', 'submitted'))
            other_proposals.write({'state': 'superseded'})
        return True
