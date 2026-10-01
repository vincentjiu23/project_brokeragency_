# -*- coding: utf-8 -*-
{
    'name': 'VIN Identity — External IdP & Verification Mapping',
    'version': '17.0.1.0.0',
    'category': 'Authentication',
    'summary': 'External IdP, SSO/SCIM/JIT, and sensitive identity verification boundary',
    'description': """Owns external identity mapping, SSO/SCIM integration contracts, and sensitive KYC/KYB identity verification states.""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
