# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _

class VinIdentityLink(models.Model):
    _name = 'vin.identity.link'
    _description = 'VIN External IdP Mapping & Federation'
    _order = 'create_date desc'

    uuid = fields.Char(
        string='Identity Link UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    user_id = fields.Many2one(
        'res.users',
        string='Odoo Internal User',
        required=True,
        ondelete='cascade',
        index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant Boundary',
        required=True,
        index=True
    )
    idp_provider = fields.Selection(
        [
            ('google', 'Google Workspace'),
            ('okta', 'Okta SSO'),
            ('azure_ad', 'Microsoft Entra ID (Azure AD)'),
            ('saml_custom', 'Custom Enterprise SAML 2.0'),
            ('oidc_generic', 'Generic OIDC Provider')
        ],
        string='Identity Provider',
        required=True,
        index=True
    )
    external_sub = fields.Char(
        string='External Subject Identifier (sub)',
        required=True,
        index=True,
        help="Immutable subject identifier issued by the upstream external IdP."
    )
    scim_external_id = fields.Char(
        string='SCIM External ID',
        index=True,
        help="SCIM 2.0 directory identifier for automated lifecycle provisioning."
    )
    jit_provisioned = fields.Boolean(
        string='JIT Provisioned',
        default=False,
        readonly=True
    )
    mfa_enforced = fields.Boolean(
        string='MFA Enforced by IdP',
        default=True
    )
    status = fields.Selection(
        [
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('revoked', 'Revoked')
        ],
        string='Federation Status',
        required=True,
        default='active',
        index=True
    )

    _sql_constraints = [
        ('provider_sub_unique', 'unique(idp_provider, external_sub)', 'The IdP subject identifier must be unique per provider!'),
        ('identity_uuid_unique', 'unique(uuid)', 'Identity link UUID must be unique!')
    ]
