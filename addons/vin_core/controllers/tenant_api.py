# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request, Response
from ..services.tenant_context import TenantContextService

class TenantApiController(http.Controller):
    """Transport adapter for tenant information API."""

    @http.route('/api/v1/tenants/current', type='http', auth='user', methods=['GET'], csrf=False)
    def get_current_tenant(self, **kwargs):
        try:
            tenant_id = TenantContextService.get_current_tenant_id(request.env)
            if not tenant_id:
                return Response(
                    json.dumps({'error': 'Superuser or no tenant scope.'}),
                    status=200,
                    mimetype='application/json'
                )
            tenant = request.env['vin.tenant'].browse(tenant_id)
            data = {
                'uuid': tenant.uuid,
                'code': tenant.code,
                'name': tenant.name,
                'status': tenant.status
            }
            return Response(json.dumps(data), status=200, mimetype='application/json')
        except Exception as e:
            return Response(json.dumps({'error': str(e)}), status=403, mimetype='application/json')
