# -*- coding: utf-8 -*-
from odoo.exceptions import AccessDenied

class TenantContextService:
    """Provides server-side evaluation of active tenant and organization context."""

    @staticmethod
    def get_current_tenant_id(env):
        """Resolves the current tenant context from user session or user membership."""
        user = env.user
        if user._is_superuser():
            return None

        # Resolve via active user membership
        membership = env['vin.membership'].sudo().search([
            ('user_id', '=', user.id),
            ('status', '=', 'active')
        ], limit=1)

        if not membership or not membership.tenant_id:
            raise AccessDenied("Active user does not belong to any authorized tenant.")

        return membership.tenant_id.id

    @staticmethod
    def validate_tenant_boundary(record, current_tenant_id):
        """Ensures that cross-tenant access is rejected immediately."""
        if hasattr(record, 'tenant_id') and record.tenant_id and current_tenant_id:
            if record.tenant_id.id != current_tenant_id:
                raise AccessDenied("Security Violation: Cross-tenant access rejected.")
