# -*- coding: utf-8 -*-
{
    'name': 'VIN Policy — Versioning & Non-Retroactive Rule Engine',
    'version': '17.0.1.0.0',
    'category': 'Governance',
    'summary': 'Policy versions, effective date resolution, and historical rule pinning for VIN Project',
    'description': """
        VIN Policy provides:
        - Versioned policy specifications (vin.policy.version)
        - Historical policy resolution by effective timestamp
        - Hard platform limits (e.g. max review days, min budget thresholds)
        - Non-retroactive policy pinning for contracts and transactions
    """,
    'author': 'VIN Project Team',
    'depends': ['base', 'vin_core', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'views/policy_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
