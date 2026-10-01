# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinCrossTenantAccessLog(models.Model):
    _name = 'vin.cross.tenant.access.log'
    _description = 'VIN Immutable Cross-Tenant Access Audit Log'
    _order = 'id desc'

    uuid = fields.Char(
        string='Log UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    source_tenant_id = fields.Char(
        string='Source Tenant UUID',
        required=True,
        index=True,
        readonly=True
    )
    target_tenant_id = fields.Char(
        string='Target Tenant UUID',
        required=True,
        index=True,
        readonly=True
    )
    contractual_bridge_id = fields.Char(
        string='Contractual Bridge UUID (CONTRACT_VN)',
        required=True,
        index=True,
        readonly=True,
        help="UUID of the signed contract authorizing cross-tenant access."
    )
    actor_id = fields.Char(
        string='Actor UUID / ID',
        required=True,
        readonly=True
    )
    resource_type = fields.Char(
        string='Target Resource Model',
        required=True,
        readonly=True
    )
    resource_id = fields.Char(
        string='Target Resource UUID',
        required=True,
        readonly=True
    )
    action = fields.Char(
        string='Action Performed',
        required=True,
        readonly=True
    )
    timestamp_utc = fields.Datetime(
        string='Access Timestamp (UTC)',
        required=True,
        default=fields.Datetime.now,
        readonly=True
    )
    justification = fields.Text(
        string='Access Justification',
        readonly=True
    )

    def write(self, vals):
        raise UserError(_("Security Violation: Cross-tenant access logs are immutable!"))

    def unlink(self):
        raise UserError(_("Security Violation: Cross-tenant access logs cannot be deleted!"))

    @api.model
    def log_access(self, source_tenant_id, target_tenant_id, contractual_bridge_id,
                   actor_id, resource_type, resource_id, action, justification):
        return super(VinCrossTenantAccessLog, self.sudo()).create({
            'source_tenant_id': source_tenant_id,
            'target_tenant_id': target_tenant_id,
            'contractual_bridge_id': contractual_bridge_id,
            'actor_id': actor_id,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'action': action,
            'justification': justification
        })
