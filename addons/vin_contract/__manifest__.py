# -*- coding: utf-8 -*-
{
    'name': 'VIN Contract — Immutable Contracts, Proposals & Approval Matrix',
    'version': '17.0.1.0.0',
    'category': 'Legal',
    'summary': 'Contract_VN, Proposal_VN, multi-tier approvals, and versioned change requests',
    'description': """Owns immutable versioned legal contracts (CONTRACT_VN), structured proposals, and approval matrix invalidation.""",
    'author': 'VIN Project Team',
    'depends': ['vin_core', 'vin_policy', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
