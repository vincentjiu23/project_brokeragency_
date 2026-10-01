# -*- coding: utf-8 -*-
from odoo.exceptions import AccessDenied

class FourEyesValidatorService:
    """Enforces Segregation of Duties across critical platform mutations."""

    @staticmethod
    def validate_segregation(creator_user_id, approver_user_id, operation_name="Operation"):
        """Ensures that creator and approver are distinct individuals."""
        if str(creator_user_id) == str(approver_user_id):
            raise AccessDenied(
                f"Four-Eyes Segregation of Duties Violation: "
                f"User {creator_user_id} attempted to self-approve {operation_name}."
            )
        return True
