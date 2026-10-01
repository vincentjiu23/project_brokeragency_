# -*- coding: utf-8 -*-
{
    'name': 'VIN Reputation — Public Ratings & Internal Trust Score',
    'version': '17.0.1.0.0',
    'category': 'Reputation',
    'summary': 'Two-way dual-blind reviews, public metrics, and internal trust event scoring',
    'description': """Owns public star ratings, completion/on-time metrics, and internal trust score pipeline (hidden from public).""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_partner', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
