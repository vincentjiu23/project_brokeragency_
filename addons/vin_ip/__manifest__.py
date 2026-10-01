# -*- coding: utf-8 -*-
{
    'name': 'VIN IP — Asset-Level Rights & License Assignments',
    'version': '17.0.1.0.0',
    'category': 'Legal',
    'summary': 'Asset-level IP ownership, pass-through licenses, and portfolio display gates',
    'description': """Owns asset-level intellectual property assignments, perpetual licenses, and portfolio display policy gates.""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_execution', 'vin_escrow', 'vin_audit', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/ip_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
