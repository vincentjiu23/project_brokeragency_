# -*- coding: utf-8 -*-
from odoo.exceptions import AccessDenied

class PartnerProfileProjectionService:
    """Produces sanitized public projections of partner profiles, filtering confidential data."""

    def __init__(self, env):
        self.env = env

    def get_public_projection(self, profile_uuid):
        """Generates safe read-only projection for external discovery & SEO."""
        profile = self.env['creative.partner.profile'].sudo().search([('uuid', '=', profile_uuid)], limit=1)
        if not profile or profile.verification_status not in ['verified', 'featured']:
            raise AccessDenied("Profile is either unverified or not accessible for public projection.")

        # Filter only approved portfolio items with display_allowed=True and published state
        portfolio_items = []
        for item in profile.portfolio_item_ids:
            if item.publication_state == 'published' and item.display_allowed:
                portfolio_items.append({
                    'uuid': item.uuid,
                    'title': item.title,
                    'description': item.description,
                    'asset_vault_ref': item.asset_vault_ref,
                    'external_preview_url': item.external_preview_url
                })

        # Return projection: Notice internal_trust_score, bank details, and KYC documents are STRICTLY EXCLUDED!
        return {
            'uuid': profile.uuid,
            'name': profile.partner_id.name,
            'account_type': profile.account_type,
            'verification_status': profile.verification_status,
            'target_market': profile.target_market,
            'public_rating': profile.public_rating,
            'completed_projects_count': profile.completed_projects_count,
            'on_time_delivery_rate': profile.on_time_delivery_rate,
            'response_sla_compliance_rate': profile.response_sla_compliance_rate,
            'expertise': [
                {'code': exp.code, 'name': exp.name, 'category': exp.category}
                for exp in profile.expertise_ids
            ],
            'portfolio': portfolio_items
        }
