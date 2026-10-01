# -*- coding: utf-8 -*-
{
    'name': 'VIN Partner — Creative Partner Profile & Portfolio',
    'version': '17.0.1.0.0',
    'category': 'Partner',
    'summary': 'Creative Partner Profile, agency/individual accounts, and portfolio metadata',
    'description': """Owns Creative Partner Profile, account types, verification workflows, expertise tags, and portfolio metadata.""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_identity', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
