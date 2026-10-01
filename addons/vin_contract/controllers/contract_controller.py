# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request, Response

class VinContractController(http.Controller):

    @http.route('/api/v1/contracts/<string:contract_uuid>/proposals', type='json', auth='user', methods=['POST'])
    def submit_contract_proposal(self, contract_uuid, **kwargs):
        """Submits structured proposal for a contract version."""
        data = request.jsonrequest or {}
        author_role = data.get('author_role', 'partner')
        proposed_budget = data.get('proposed_budget')
        proposed_deadline = data.get('proposed_deadline')
        delta_snapshot = data.get('delta_snapshot', {})

        contract = request.env['vin.contract'].search([('uuid', '=', contract_uuid)], limit=1)
        if not contract:
            return {'status': 'error', 'message': 'Contract not found', 'code': 404}

        try:
            prop = request.env['vin.contract.proposal'].create({
                'contract_id': contract.id,
                'author_role': author_role,
                'proposed_budget': proposed_budget or contract.total_contract_value,
                'proposed_deadline': proposed_deadline or contract.completion_deadline,
                'delta_snapshot': json.dumps(delta_snapshot)
            })
            prop.action_submit_proposal()
            return {
                'status': 'success',
                'proposal_uuid': prop.uuid,
                'proposal_state': prop.state,
                'contract_state': contract.state
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'code': 400}

    @http.route('/api/v1/change-requests', type='json', auth='user', methods=['POST'])
    def create_change_request(self, **kwargs):
        """Creates a versioned Change Request for an active contract."""
        data = request.jsonrequest or {}
        contract_uuid = data.get('contract_uuid')
        scope_delta = data.get('scope_delta', '')
        budget_delta = data.get('budget_delta', 0.0)
        timeline_delta_days = data.get('timeline_delta_days', 0)

        contract = request.env['vin.contract'].search([('uuid', '=', contract_uuid)], limit=1)
        if not contract:
            return {'status': 'error', 'message': 'Contract not found', 'code': 404}

        try:
            cr = request.env['vin.contract.change.request'].create({
                'contract_id': contract.id,
                'scope_delta': scope_delta,
                'budget_delta': budget_delta,
                'timeline_delta_days': timeline_delta_days,
                'state': 'draft'
            })
            return {
                'status': 'success',
                'cr_uuid': cr.uuid,
                'cr_number': cr.cr_number,
                'state': cr.state
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'code': 400}
