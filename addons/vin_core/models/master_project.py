# -*- coding: utf-8 -*-
import uuid
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinMasterProject(models.Model):
    _name = 'vin.master.project'
    _description = 'VIN Master Project Aggregation Root'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    uuid = fields.Char(
        string='Master Project UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    name = fields.Char(
        string='Project Title',
        required=True,
        tracking=True
    )
    organization_id = fields.Many2one(
        'vin.organization',
        string='Client Organization',
        required=True,
        ondelete='restrict',
        index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='organization_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    reporting_currency_id = fields.Many2one(
        'res.currency',
        string='Reporting Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        help="Master project reporting currency for consolidated financial tracking."
    )
    brief_version_id = fields.Char(
        string='Active Brief Version UUID',
        index=True,
        help="Pinned snapshot of the active Creative Project Brief version."
    )
    state = fields.Selection(
        [
            ('draft', 'Draft Briefing'),
            ('matching', 'Partner Matching'),
            ('contracting', 'Contracting & Escrow Funding'),
            ('execution', 'Execution in Progress'),
            ('acceptance', 'Deliverable Acceptance'),
            ('financial_close', 'Financial Reconciliation'),
            ('completed', 'Completed (Pending Final 14-Day Closure)'),
            ('closed', 'Project Closed & Read-Only'),
            ('archived', 'Cold Archived')
        ],
        string='Project State',
        required=True,
        default='draft',
        tracking=True,
        index=True
    )

    # 5 System Closure Gates (Non-Negotiable Business Invariant)
    gate_workstreams_complete = fields.Boolean(
        string='Gate 1: Workstreams Completed',
        default=False,
        readonly=True
    )
    gate_escrow_zero_out = fields.Boolean(
        string='Gate 2: Escrow Ledger Zero-Out',
        default=False,
        readonly=True
    )
    gate_ip_transfer_complete = fields.Boolean(
        string='Gate 3: IP Transfer Signed/Completed',
        default=False,
        readonly=True
    )
    gate_tax_invoice_reconciled = fields.Boolean(
        string='Gate 4: Tax & Invoices Reconciled',
        default=False,
        readonly=True
    )
    gate_no_active_dispute = fields.Boolean(
        string='Gate 5: Zero Active Disputes',
        default=True,
        readonly=True
    )

    completed_at = fields.Datetime(
        string='Completed Timestamp (UTC)',
        readonly=True
    )
    final_closure_deadline = fields.Datetime(
        string='Final 14-Working-Day Closure Deadline',
        readonly=True
    )

    def action_verify_and_complete(self):
        """Evaluates the 5 locked system closure gates before transitioning to COMPLETED."""
        for record in self:
            if not (record.gate_workstreams_complete and
                    record.gate_escrow_zero_out and
                    record.gate_ip_transfer_complete and
                    record.gate_tax_invoice_reconciled and
                    record.gate_no_active_dispute):
                raise UserError(_(
                    "Cannot complete Master Project. All 5 system closure gates must pass: \n"
                    "1. Workstreams Complete: %s\n"
                    "2. Escrow Zero-Out: %s\n"
                    "3. IP Transfer Complete: %s\n"
                    "4. Tax/Invoices Reconciled: %s\n"
                    "5. No Active Dispute: %s"
                ) % (
                    record.gate_workstreams_complete,
                    record.gate_escrow_zero_out,
                    record.gate_ip_transfer_complete,
                    record.gate_tax_invoice_reconciled,
                    record.gate_no_active_dispute
                ))

            now = fields.Datetime.now()
            # 14 working days approx 20 calendar days or calculated via business calendar
            deadline = now + timedelta(days=20)
            record.write({
                'state': 'completed',
                'completed_at': now,
                'final_closure_deadline': deadline
            })

            # Record immutable audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='PROJECT_COMPLETED',
                subject_type='vin.master.project',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={'closure_gates_verified': True, 'final_closure_deadline': str(deadline)}
            )

    def action_finalize_closure(self):
        """Closes the project permanently into immutable read-only state."""
        for record in self:
            if record.state != 'completed':
                raise UserError(_("Only completed projects in the final closure window can be closed."))
            record.write({'state': 'closed'})
            self.env['vin.audit.event'].sudo().record_event(
                action='PROJECT_CLOSED',
                subject_type='vin.master.project',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={'status': 'closed', 'read_only': True}
            )
