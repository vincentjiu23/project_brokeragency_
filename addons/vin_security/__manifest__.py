# -*- coding: utf-8 -*-
{
    'name': 'VIN Security — RLS Baseline, Cross-Tenant Logging & Four-Eyes Governance',
    'version': '17.0.1.0.0',
    'category': 'Security',
    'summary': 'Server-side tenant isolation enforcement, SoD Four-Eyes engine, and cross-tenant auditing',
    'description': """
        VIN Security provides:
        - Immutable cross-tenant access logging (vin.cross.tenant.access.log)
        - Four-Eyes Segregation-of-Duties governance engine (vin.governance.override)
        - PostgreSQL RLS session context helper (app.current_tenant_id)
        - Step-up MFA verification gates for financial and legal transfers
    """,
    'author': 'VIN Project Team',
    'depends': ['base', 'vin_core', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'views/security_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
