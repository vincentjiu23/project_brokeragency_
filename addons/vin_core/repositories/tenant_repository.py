# -*- coding: utf-8 -*-
from odoo import models

class TenantRepository:
    """Encapsulates complex reads and tenant-scoped query objects."""

    def __init__(self, env):
        self.env = env

    def get_by_uuid(self, tenant_uuid):
        return self.env['vin.tenant'].sudo().search([('uuid', '=', tenant_uuid)], limit=1)

    def get_by_code(self, code):
        return self.env['vin.tenant'].sudo().search([('code', '=', code)], limit=1)

    def get_active_organizations(self, tenant_id):
        return self.env['vin.organization'].search([
            ('tenant_id', '=', tenant_id),
            ('status', '=', 'active')
        ])
