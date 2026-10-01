# -*- coding: utf-8 -*-
{
    'name': 'VIN Identity — External IdP & Verification Mapping',
    'version': '17.0.1.0.0',
    'category': 'Authentication',
    'summary': 'External IdP mapping, enterprise SSO/SCIM/JIT, and secure identity verification boundary',
    'description': """
        VIN Identity owns:
        - External identity mapping (vin.identity.link)
        - Enterprise SSO/SCIM/JIT integration contracts
        - Identity verification status and restricted evidence references
        - Strict isolation preventing identity documents from public/partner API leakage
    """,
    'author': 'VIN Project Team',
    'depends': ['base', 'vin_core', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/identity_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
