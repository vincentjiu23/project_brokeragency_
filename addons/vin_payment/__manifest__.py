# -*- coding: utf-8 -*-
{
    'name': 'VIN Payment — Provider Gateways, Webhooks & Payouts',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Payment provider abstraction, idempotent webhooks, and payout state machines',
    'description': """Owns payment provider abstraction, idempotent webhook processing, payout state machines, and reconciliation.""",
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
