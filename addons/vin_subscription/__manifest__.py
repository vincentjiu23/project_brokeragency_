# -*- coding: utf-8 -*-
{
    'name': 'VIN Subscription — Tier Plans, Usage Billing & Commission Rules',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Client/Partner subscription plans, usage add-ons, and commission rule profiles',
    'description': """Owns organization subscription tiers, usage-based billing, take-rate discounts, and commission rule profiles.""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_partner', 'vin_escrow', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
