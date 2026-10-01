# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request, Response

class VinExecutionController(http.Controller):

    @http.route('/api/v1/deliverables/<string:deliverable_uuid>/submissions', type='json', auth='user', methods=['POST'])
    def submit_deliverable_version(self, deliverable_uuid, **kwargs):
        """Uploads an immutable deliverable submission version linked to Asset Vault."""
        data = request.jsonrequest or {}
        asset_hash = data.get('asset_hash')
        asset_object_id = data.get('asset_object_id')
        notes = data.get('notes', '')

        if not asset_hash or not asset_object_id:
            return {'status': 'error', 'message': 'Missing asset_hash or asset_object_id', 'code': 400}

        deliverable = request.env['vin.deliverable'].search([('uuid', '=', deliverable_uuid)], limit=1)
        if not deliverable:
            return {'status': 'error', 'message': 'Deliverable not found', 'code': 404}

        try:
            sub = request.env['vin.deliverable.submission'].create({
                'deliverable_id': deliverable.id,
                'asset_vault_ref': asset_hash,
                'asset_object_id': asset_object_id,
                'submission_notes': notes
            })
            return {
                'status': 'success',
                'submission_uuid': sub.uuid,
                'version_no': sub.version_no,
                'state': sub.state
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'code': 400}

    @http.route('/api/v1/deliverables/<string:deliverable_uuid>/acceptance', type='json', auth='user', methods=['POST'])
    def accept_deliverable(self, deliverable_uuid, **kwargs):
        """Formally accepts a deliverable submission (AC-05)."""
        data = request.jsonrequest or {}
        submission_uuid = data.get('submission_uuid')
        notes = data.get('notes', '')

        deliverable = request.env['vin.deliverable'].search([('uuid', '=', deliverable_uuid)], limit=1)
        if not deliverable:
            return {'status': 'error', 'message': 'Deliverable not found', 'code': 404}

        sub = request.env['vin.deliverable.submission'].search([('uuid', '=', submission_uuid)], limit=1) if submission_uuid else deliverable.latest_submission_id
        if not sub:
            return {'status': 'error', 'message': 'Submission not found', 'code': 404}

        try:
            acc = request.env['vin.deliverable.acceptance'].create({
                'deliverable_id': deliverable.id,
                'submission_id': sub.id,
                'acceptance_notes': notes
            })
            return {
                'status': 'success',
                'acceptance_uuid': acc.uuid,
                'deliverable_state': deliverable.state,
                'milestone_state': deliverable.milestone_id.state
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'code': 400}
