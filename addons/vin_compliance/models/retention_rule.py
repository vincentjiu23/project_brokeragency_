# -*- coding: utf-8 -*-
"""
Data Retention Rule Model (Q137–Q146, Q250 Compliance Domain).
Enforces regulatory data retention periods per entity classification
(e.g., tax records 10 years, executed contracts 7 years, chat logs 2 years).
"""
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class VinRetentionRule(models.Model):
    """
    Data Retention Policy Definition.
    Configures lifecycle and retention constraints across the platform:
      - Tax & Financial: 10 years (UU KUP / Statutory tax requirement)
      - Executed Contracts & IP Deeds: 7-10 years (Civil code limitation)
      - Deliverables & Artifacts: 5 years (Archival to cold storage)
      - Operational & Communication Logs: 2 years
    """
    _name = 'vin.retention.rule'
    _description = 'VIN Data Retention Policy Rule'
    _order = 'sequence asc, id asc'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )
    name = fields.Char(string='Policy Name', required=True)
    code = fields.Char(string='Rule Code', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)

    target_category = fields.Selection([
        ('financial_ledger', 'Financial & Virtual Escrow Ledgers'),
        ('tax_record', 'Tax Profiles, Invoices & Withholding Certificates'),
        ('contract_legal', 'Contracts, Change Requests & IP Deeds'),
        ('deliverable_asset', 'Deliverable Submissions & Digital Vault Assets'),
        ('communication_chat', 'Project Communications & Notifications'),
        ('audit_event', 'Audit Trail & Hash Chains (WORM - Permanent)'),
    ], string='Target Category', required=True, index=True)

    target_model_name = fields.Char(
        string='Target Odoo Model', required=True,
        help="Technical name of model (e.g., vin.contract, vin.invoice, vin.escrow.ledger.entry)"
    )

    retention_period_days = fields.Integer(
        string='Retention Period (Days)', required=True, default=2555, # 7 years
        help="Number of days to retain records before eligible for archival or purge."
    )

    action_on_expiry = fields.Selection([
        ('archive_cold', 'Archive to Immutable WORM Cold Vault'),
        ('anonymize_dsar', 'Cryptographic Pseudonymization / Masking'),
        ('permanent_retention', 'Permanent Retention (Never Purged / WORM)'),
    ], string='Action Upon Expiry', default='archive_cold', required=True)

    legal_basis = fields.Char(
        string='Regulatory / Legal Basis',
        placeholder="e.g., Indonesian Tax Law UU KUP Art 28, GDPR Art 17(3)(b)"
    )
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description & Audit Scope')

    @api.constrains('retention_period_days', 'target_category')
    def _check_retention_minimums(self):
        """
        Enforce statutory minimums:
          - Financial & tax records: minimum 10 years (3650 days)
          - Contracts & IP deeds: minimum 7 years (2555 days)
          - Audit events: permanent only
        """
        for rec in self:
            if rec.target_category in ('financial_ledger', 'tax_record') and rec.retention_period_days < 3650:
                raise ValidationError(_(
                    "Statutory compliance rule: Financial and Tax retention period cannot be less than 3,650 days (10 years)."
                ))
            if rec.target_category == 'contract_legal' and rec.retention_period_days < 2555:
                raise ValidationError(_(
                    "Statutory compliance rule: Contract and Legal Deed retention period cannot be less than 2,555 days (7 years)."
                ))
            if rec.target_category == 'audit_event' and rec.action_on_expiry != 'permanent_retention':
                raise ValidationError(_(
                    "Audit event trail must be set to 'Permanent Retention' (immutable WORM compliance)."
                ))
