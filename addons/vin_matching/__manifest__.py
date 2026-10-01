# -*- coding: utf-8 -*-
{
    'name': 'VIN Matching — Discovery & Recommendation Engine',
    'version': '17.0.1.0.0',
    'category': 'Project',
    'summary': 'Creative Project Brief versioning, Hard Eligibility, and Contextual Ranking',
    'description': """Owns Creative Project Brief versions (BRIEF_VN), deterministic hard eligibility gates, and match snapshots.""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_partner', 'vin_policy', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
