# -*- coding: utf-8 -*-
{
    'name': 'VIN Compliance — Data Retention, Legal Hold & GDPR/DSAR',
    'version': '17.0.1.0.0',
    'category': 'Compliance',
    'summary': 'Data retention lifecycles, legal hold locks, and cryptographic erasure',
    'description': """Owns data classification, retention rules, legal holds, and DSAR cryptographic erasure without mutating ledgers.""",
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
