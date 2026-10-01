# -*- coding: utf-8 -*-
from decimal import Decimal
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinLedgerEntry(models.Model):
    _name = 'vin.ledger.entry'
    _description = 'VIN Immutable Double-Entry Virtual Escrow Ledger Line'
    _order = 'timestamp asc, id asc'

    uuid = fields.Char(
        string='Ledger Entry UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    transaction_id = fields.Char(
        string='Transaction Batch UUID',
        required=True,
        readonly=True,
        index=True
    )
    escrow_account_id = fields.Many2one(
        'vin.escrow.account',
        string='Virtual Escrow Account',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='escrow_account_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    account_type = fields.Selection(
        [
            ('cash', 'Escrow Bank / Cash Asset (Dr increases balance)'),
            ('liability_client', 'Client Escrow Deposit Liability (Cr increases liability)'),
            ('liability_partner', 'Partner Milestone Payable (Cr increases payable)'),
            ('platform_fee', 'Platform Brokerage Revenue (Cr platform take-rate)')
        ],
        string='Virtual Sub-Account Type',
        required=True,
        readonly=True,
        index=True
    )
    debit = fields.Monetary(
        string='Debit (Dr)',
        currency_field='currency_id',
        required=True,
        default=0.0,
        readonly=True
    )
    credit = fields.Monetary(
        string='Credit (Cr)',
        currency_field='currency_id',
        required=True,
        default=0.0,
        readonly=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        readonly=True
    )
    reference = fields.Char(
        string='Transaction Description / Journal Memo',
        required=True,
        readonly=True
    )
    timestamp = fields.Datetime(
        string='Entry Timestamp (UTC)',
        required=True,
        readonly=True,
        default=fields.Datetime.now
    )

    def write(self, vals):
        """Locked Architecture Decision (ADR-002 / ADR-003): Virtual ledger rows are strictly immutable."""
        raise UserError(_("Security Violation: Virtual ledger rows are append-only and cannot be modified!"))

    def unlink(self):
        """Locked Architecture Decision (ADR-002 / ADR-003): Virtual ledger rows cannot be deleted."""
        raise UserError(_("Security Violation: Virtual ledger rows cannot be deleted!"))

    @api.model
    def post_balanced_transaction(self, escrow_account, entries, reference, transaction_id=None):
        """
        Atomically writes a set of balanced double-entry ledger rows.
        CRITICAL INVARIANT: Total Debits MUST EXACTLY equal Total Credits (Zero Variance).
        """
        tx_id = transaction_id or str(uuid.uuid4())
        total_debit = sum(Decimal(str(e.get('debit', 0.0))) for e in entries)
        total_credit = sum(Decimal(str(e.get('credit', 0.0))) for e in entries)

        if total_debit != total_credit:
            raise ValidationError(_(
                "Zero-Variance Accounting Violation: Total Debits (%s) do not equal Total Credits (%s)!"
            ) % (total_debit, total_credit))

        created_entries = self.env['vin.ledger.entry']
        for e in entries:
            entry = self.create({
                'transaction_id': tx_id,
                'escrow_account_id': escrow_account.id,
                'account_type': e['account_type'],
                'debit': float(e.get('debit', 0.0)),
                'credit': float(e.get('credit', 0.0)),
                'currency_id': escrow_account.currency_id.id,
                'reference': reference,
                'timestamp': fields.Datetime.now()
            })
            created_entries |= entry

        return created_entries
