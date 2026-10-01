# -*- coding: utf-8 -*-
{
    'name': 'VIN Escrow — Virtual Escrow & Double-Entry Ledger',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Virtual escrow accounts, milestone allocations, and balanced double-entry ledger',
    'description': """Owns virtual escrow accounts, milestone allocations, locks, and balanced double-entry virtual ledger rows.""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_contract', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
