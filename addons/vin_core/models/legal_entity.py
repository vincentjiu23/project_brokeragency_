# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _

class VinLegalEntity(models.Model):
    _name = 'vin.legal.entity'
    _description = 'VIN Jurisdiction Legal Entity'
    _order = 'name asc'

    uuid = fields.Char(
        string='Legal Entity UUID',
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
    name = fields.Char(
        string='Legal Entity Name',
        required=True
    )
    registration_number = fields.Char(
        string='Registration / Company Number',
        required=True
    )
    tax_id = fields.Char(
        string='Tax ID (NPWP / VAT / EIN)',
        required=True
    )
    jurisdiction = fields.Char(
        string='Jurisdiction Country Code',
        size=3,
        default='IDN',
        required=True,
        help="ISO 3166-1 alpha-3 country code for legal framework and tax resolution."
    )
    is_primary = fields.Boolean(
        string='Is Primary Entity',
        default=True
    )

    _sql_constraints = [
        ('legal_entity_uuid_unique', 'unique(uuid)', 'Legal entity UUID must be unique!')
    ]
