# -*- coding: utf-8 -*-
{
    'name': 'VIN Execution — Workstream DAG, Milestones & Deliverables',
    'version': '17.0.1.0.0',
    'category': 'Project',
    'summary': 'Workstream DAG execution, milestones, tasks, deliverables, and submissions',
    'description': """Owns Workstream DAG, milestones, operational vs contractual tasks, deliverables, and immutable submissions.""",
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
