# -*- coding: utf-8 -*-
import uuid
from odoo.exceptions import UserError, AccessDenied

class MasterProjectLifecycleService:
    """Orchestrates deterministic lifecycle transitions for Master Project."""

    def __init__(self, env):
        self.env = env

    def create_project(self, name, organization_id, reporting_currency_id=None, brief_version_id=None):
        org = self.env['vin.organization'].browse(organization_id)
        if not org.exists() or org.status != 'active':
            raise UserError("Cannot create project under non-existent or inactive organization.")

        currency_id = reporting_currency_id or self.env.company.currency_id.id

        project = self.env['vin.master.project'].create({
            'name': name,
            'organization_id': org.id,
            'reporting_currency_id': currency_id,
            'brief_version_id': brief_version_id,
            'state': 'draft'
        })

        # Append audit event
        self.env['vin.audit.event'].sudo().record_event(
            action='MASTER_PROJECT_CREATED',
            subject_type='vin.master.project',
            subject_id=project.uuid,
            tenant_id=org.tenant_id.uuid,
            payload={'name': name, 'organization_id': org.uuid}
        )

        return project
