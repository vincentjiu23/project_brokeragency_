# -*- coding: utf-8 -*-
{
    'name': 'VIN Core — Multi-Tenant & Organization Foundation',
    'version': '17.0.1.0.0',
    'category': 'Administration',
    'summary': 'Core multi-tenant, organization, membership, and project foundation for VIN Project',
    'description': """
        VIN Core provides:
        - Multi-tenant boundary (vin.tenant)
        - Commercial organization & legal entities (vin.organization, vin.legal.entity)
        - User membership and scoped roles (vin.membership)
        - Master Project aggregation root (vin.master.project)
        - Strict tenant isolation and RLS hooks
    """,
    'author': 'VIN Project Team',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/tenant_views.xml',
        'views/organization_views.xml',
        'views/master_project_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'Proprietary',
}
