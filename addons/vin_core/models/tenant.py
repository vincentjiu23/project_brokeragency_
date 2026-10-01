# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class VinTenant(models.Model):
    _name = 'vin.tenant'
    _description = 'VIN Tenant Isolation Boundary'
    _order = 'name asc'

    uuid = fields.Char(
        string='Tenant UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False,
        help="Canonical UUID for distributed system identification."
    )
    code = fields.Char(
        string='Tenant Code',
        size=64,
        required=True,
        index=True,
        help="Unique human-readable tenant identifier code."
    )
    name = fields.Char(
        string='Tenant Name',
        required=True
    )
    status = fields.Selection(
        [
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('archived', 'Archived')
        ],
        string='Status',
        required=True,
        default='active',
        index=True
    )
    organization_ids = fields.One2many(
        'vin.organization',
        'tenant_id',
        string='Organizations'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The tenant code must be globally unique!'),
        ('uuid_unique', 'unique(uuid)', 'The tenant UUID must be globally unique!')
    ]

    def suspend_tenant(self, reason="Administrative Action"):
        """Suspends all operational activity within the tenant boundary."""
        for record in self:
            record.write({'status': 'suspended'})
            # Notify audit event service
            self.env['vin.audit.event'].sudo().record_event(
                action='TENANT_SUSPENDED',
                subject_type='vin.tenant',
                subject_id=record.uuid,
                tenant_id=record.uuid,
                payload={'reason': reason}
            )
