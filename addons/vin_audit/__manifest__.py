# -*- coding: utf-8 -*-
{
    'name': 'VIN Audit — Tamper-Evident Lineage & Cryptographic Hash Chain',
    'version': '17.0.1.0.0',
    'category': 'Security',
    'summary': 'Immutable append-only audit events and cryptographic hash chaining for VIN Project',
    'description': """
        VIN Audit provides:
        - Append-only audit events (vin.audit.event)
        - SHA-256 tamper-evident hash chaining
        - Correlation and distributed trace lineage
        - Strict no-delete and no-update invariants
    """,
    'author': 'VIN Project Team',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/audit_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
