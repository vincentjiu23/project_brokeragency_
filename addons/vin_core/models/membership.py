# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _

class VinMembership(models.Model):
    _name = 'vin.membership'
    _description = 'VIN User Organization Membership & RBAC Scope'
    _order = 'create_date desc'

    uuid = fields.Char(
        string='Membership UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    organization_id = fields.Many2one(
        'vin.organization',
        string='Organization',
        required=True,
        ondelete='cascade',
        index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='organization_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Odoo User',
        required=True,
        ondelete='restrict',
        index=True
    )
    role = fields.Selection(
        [
            ('owner', 'Owner / Director'),
            ('manager', 'Marketing Manager'),
            ('pic', 'Project PIC'),
            ('finance', 'Finance Officer'),
            ('legal', 'Legal Counsel'),
            ('member', 'Standard Member')
        ],
        string='Organization Role',
        required=True,
        default='member',
        index=True
    )
    status = fields.Selection(
        [
            ('active', 'Active'),
            ('invited', 'Invited'),
            ('revoked', 'Revoked')
        ],
        string='Status',
        required=True,
        default='active',
        index=True
    )

    _sql_constraints = [
        ('org_user_unique', 'unique(organization_id, user_id)', 'A user can only hold one membership per organization!'),
        ('membership_uuid_unique', 'unique(uuid)', 'Membership UUID must be unique!')
    ]
