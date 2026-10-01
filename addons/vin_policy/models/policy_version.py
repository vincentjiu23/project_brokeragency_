# -*- coding: utf-8 -*-
import json
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinPolicyVersion(models.Model):
    _name = 'vin.policy.version'
    _description = 'VIN Policy Version Specification'
    _order = 'code asc, version_no desc'

    uuid = fields.Char(
        string='Policy Version UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    code = fields.Char(
        string='Policy Domain Code',
        required=True,
        index=True,
        help="Unique identifier for policy domain (e.g. POLICY_DELIVERABLE_REVISION, POLICY_COMMISSION_TAKE_RATE)"
    )
    version_no = fields.Integer(
        string='Version Number',
        required=True,
        default=1,
        index=True
    )
    name = fields.Char(
        string='Policy Title',
        required=True
    )
    effective_from = fields.Datetime(
        string='Effective From (UTC)',
        required=True,
        default=fields.Datetime.now,
        index=True
    )
    effective_to = fields.Datetime(
        string='Effective To (UTC)',
        index=True,
        help="End of validity window. Null indicates currently open-ended policy."
    )
    status = fields.Selection(
        [
            ('draft', 'Draft Proposal'),
            ('active', 'Active & Enforced'),
            ('superseded', 'Superseded')
        ],
        string='Status',
        required=True,
        default='draft',
        index=True
    )
    rules_json = fields.Text(
        string='Rules Definition (JSON)',
        required=True,
        default='{}'
    )
    description = fields.Text(
        string='Governance & Legal Justification'
    )

    _sql_constraints = [
        ('code_version_unique', 'unique(code, version_no)', 'Policy version number must be unique per policy code!'),
        ('policy_uuid_unique', 'unique(uuid)', 'Policy UUID must be unique!')
    ]

    def action_activate(self):
        """Activates this policy version and marks previous active versions as superseded."""
        for record in self:
            now = fields.Datetime.now()
            # Supersede current active version
            previous_active = self.search([
                ('code', '=', record.code),
                ('status', '=', 'active'),
                ('id', '!=', record.id)
            ])
            for prev in previous_active:
                prev.write({
                    'status': 'superseded',
                    'effective_to': now
                })

            record.write({
                'status': 'active',
                'effective_from': now
            })

            # Record audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='POLICY_ACTIVATED',
                subject_type='vin.policy.version',
                subject_id=record.uuid,
                payload={'code': record.code, 'version_no': record.version_no}
            )

    def write(self, vals):
        """Active and superseded policies are immutable to preserve historical logic pinning."""
        for record in self:
            if record.status in ['active', 'superseded'] and 'rules_json' in vals:
                raise UserError(_("Security Violation: Cannot mutate rules_json of an active or superseded policy. Create a new version!"))
        return super(VinPolicyVersion, self).write(vals)
