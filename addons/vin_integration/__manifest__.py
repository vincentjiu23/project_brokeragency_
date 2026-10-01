# -*- coding: utf-8 -*-
{
    'name': 'VIN Integration — Resilience Gateway, Webhooks & Replay',
    'version': '17.0.1.0.0',
    'category': 'Technical',
    'summary': 'Integration resilience, circuit breakers, dead-letter queues, and event replay',
    'description': """Owns third-party integration resilience, circuit breakers, dead-letter queue, and safe event replay mechanisms.""",
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
