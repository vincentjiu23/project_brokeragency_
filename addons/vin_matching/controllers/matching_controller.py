# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request, Response

class VinMatchingController(http.Controller):

    @http.route('/api/v1/projects/<string:brief_uuid>/matches', type='http', auth='user', methods=['GET'], csrf=False)
    def get_project_matches(self, brief_uuid, **kwargs):
        """Retrieves candidate match snapshot for a project brief (AC-01)."""
        brief = request.env['vin.project.brief'].search([('uuid', '=', brief_uuid)], limit=1)
        if not brief:
            return Response(
                json.dumps({'error': 'Project brief not found'}),
                status=404,
                mimetype='application/json'
            )

        snapshot = brief.match_snapshot_ids and brief.match_snapshot_ids[0]
        if not snapshot:
            return Response(
                json.dumps({'error': 'No match snapshot generated for this brief'}),
                status=404,
                mimetype='application/json'
            )

        candidates = []
        for cand in snapshot.candidate_ids:
            candidates.append({
                'rank': cand.rank,
                'candidate_uuid': cand.uuid,
                'partner_name': cand.partner_profile_id.partner_id.name,
                'overall_score': cand.overall_score,
                'expertise_match_score': cand.expertise_match_score,
                'reputation_score': cand.reputation_score,
                'hard_eligibility_passed': cand.hard_eligibility_passed
            })

        payload = {
            'snapshot_uuid': snapshot.uuid,
            'brief_uuid': brief.uuid,
            'snapshot_time': str(snapshot.snapshot_time),
            'algorithm_version': snapshot.algorithm_version,
            'total_screened': snapshot.total_candidates_screened,
            'total_eligible': snapshot.total_eligible_matched,
            'candidates': candidates
        }
        return Response(json.dumps(payload), status=200, mimetype='application/json')

    @http.route('/api/v1/opportunities/<string:opportunity_uuid>/respond', type='json', auth='user', methods=['POST'])
    def respond_to_opportunity(self, opportunity_uuid, **kwargs):
        """Handles partner response to engagement opportunity (AC-02)."""
        data = request.jsonrequest or {}
        action = data.get('action')
        note = data.get('note', '')

        opp = request.env['vin.opportunity.record'].search([('uuid', '=', opportunity_uuid)], limit=1)
        if not opp:
            return {'status': 'error', 'message': 'Opportunity not found', 'code': 404}

        try:
            if action == 'accept':
                opp.action_accept(response_note=note)
                return {
                    'status': 'success',
                    'opportunity_state': opp.state,
                    'client_disclosed': opp.client_disclosed,
                    'client_name': opp.brief_id.client_organization_id.name
                }
            elif action == 'decline':
                opp.action_decline(reason=note)
                return {
                    'status': 'success',
                    'opportunity_state': opp.state
                }
            else:
                return {'status': 'error', 'message': "Invalid action. Must be 'accept' or 'decline'.", 'code': 400}
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'code': 400}
