# -*- coding: utf-8 -*-
{
    'name': 'VIN Tax & Invoice — Multi-Jurisdiction Compliance & Invoicing',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Tax resolver, VAT/PPN, WHT/PPh, partner invoices, and tax certificates',
    'description': """Owns tax profiles, invoice orchestration, tax resolver integrations, and immutable tax certificate payloads.""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_escrow', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
