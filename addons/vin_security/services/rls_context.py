# -*- coding: utf-8 -*-
class RlsContextHelper:
    """Helper to set and clear PostgreSQL Row-Level Security session variables."""

    @staticmethod
    def set_session_tenant(cr, tenant_uuid):
        """Sets PostgreSQL session variable app.current_tenant_id."""
        cr.execute("SET LOCAL app.current_tenant_id = %s;", (str(tenant_uuid),))

    @staticmethod
    def clear_session_tenant(cr):
        """Resets PostgreSQL session variable app.current_tenant_id."""
        cr.execute("RESET app.current_tenant_id;")
