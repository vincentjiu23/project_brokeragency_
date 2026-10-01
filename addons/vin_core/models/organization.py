# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class VinOrganization(models.Model):
    _name = 'vin.organization'
    _description = 'VIN Commercial Organization Root'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    uuid = fields.Char(
        string='Organization UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        required=True,
        ondelete='restrict',
        index=True
    )
    name = fields.Char(
        string='Organization Name',
        required=True,
        tracking=True
    )
    code = fields.Char(
        string='Organization Code',
        size=64,
        required=True,
        index=True
    )
    legal_entity_mode = fields.Selection(
        [
            ('single', 'Single Entity'),
            ('multi', 'Multi-Jurisdiction / Multi-Entity')
        ],
        string='Legal Entity Mode',
        required=True,
        default='single',
        index=True
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
        tracking=True,
        index=True
    )
    legal_entity_ids = fields.One2many(
        'vin.legal.entity',
        'organization_id',
        string='Legal Entities'
    )
    membership_ids = fields.One2many(
        'vin.membership',
        'organization_id',
        string='Memberships'
    )
    master_project_ids = fields.One2many(
        'vin.master.project',
        'organization_id',
        string='Master Projects'
    )

    _sql_constraints = [
        ('org_code_tenant_unique', 'unique(tenant_id, code)', 'The organization code must be unique per tenant!'),
        ('org_uuid_unique', 'unique(uuid)', 'The organization UUID must be globally unique!')
    ]
