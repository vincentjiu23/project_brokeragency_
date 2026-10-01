# -*- coding: utf-8 -*-
{
    'name': 'VIN Partner — Creative Partner Profile & Portfolio Governance',
    'version': '17.0.1.0.0',
    'category': 'Partner',
    'summary': 'Creative Partner profiles, qualification pipeline, portfolio items, and safe public projections',
    'description': """
        VIN Partner owns:
        - Creative Partner Profile (creative.partner.profile) extending res.partner
        - Agency vs Individual partner accounts and capabilities
        - Portfolio metadata and asset-level display rights (vin.portfolio.item)
        - Internal trust score isolation (never exposed via public API)
        - Sanitized public profile projection service
    """,
    'author': 'VIN Project Team',
    'depends': ['base', 'vin_core', 'vin_identity', 'vin_audit'],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'views/partner_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}
