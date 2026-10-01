# -*- coding: utf-8 -*-
import json
from odoo import fields
from odoo.exceptions import UserError

class PolicyResolverService:
    """Resolves historical policy rules based on effective timestamp or policy UUID."""

    def __init__(self, env):
        self.env = env

    def get_effective_policy(self, policy_code, target_time=None):
        """Resolves the policy active at the specific historical point in time."""
        target = target_time or fields.Datetime.now()
        domain = [
            ('code', '=', policy_code),
            ('effective_from', '<=', target),
            '|',
            ('effective_to', '=', False),
            ('effective_to', '>', target)
        ]
        policy = self.env['vin.policy.version'].sudo().search(domain, order='version_no desc', limit=1)
        if not policy:
            raise UserError(f"No active policy found for code '{policy_code}' at timestamp {target}.")

        return {
            'policy_uuid': policy.uuid,
            'version_no': policy.version_no,
            'rules': json.loads(policy.rules_json or '{}')
        }
