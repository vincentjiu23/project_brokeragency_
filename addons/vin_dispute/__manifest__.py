# -*- coding: utf-8 -*-
{
    'name': 'VIN Dispute — Tiered Acceptance Disputes & Arbitration',
    'version': '17.0.1.0.0',
    'category': 'Legal',
    'summary': 'Acceptance disputes, revision classification objections, and arbitration lock',
    'description': """Owns acceptance dispute state machines, revision classification objections, and evidence package linkages.""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_execution', 'vin_escrow', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
