# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinEscrowAccount(models.Model):
    _name = 'vin.escrow.account'
    _description = 'VIN Virtual Escrow Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    uuid = fields.Char(
        string='Escrow Account UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    account_number = fields.Char(
        string='Escrow Account Reference',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: f"ESC-{uuid.uuid4().hex[:8].upper()}"
    )
    contract_id = fields.Many2one(
        'vin.contract',
        string='Governing Contract (CONTRACT_VN)',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='contract_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    client_organization_id = fields.Many2one(
        'vin.organization',
        string='Client Organization',
        related='contract_id.client_organization_id',
        store=True,
        readonly=True
    )
    partner_profile_id = fields.Many2one(
        'creative.partner.profile',
        string='Creative Partner',
        related='contract_id.partner_profile_id',
        store=True,
        readonly=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    state = fields.Selection(
        [
            ('draft', 'Awaiting Initial Funding'),
            ('funded', 'Funded & Active'),
            ('locked', 'Locked (Dispute / Compliance Hold)'),
            ('disbursing', 'Disbursements In Progress'),
            ('closed', 'Closed & Fully Settled')
        ],
        string='Escrow State',
        required=True,
        default='draft',
        tracking=True,
        index=True
    )
    lock_reason = fields.Char(
        string='Hold / Dispute Lock Reason',
        readonly=True,
        tracking=True
    )
    ledger_entry_ids = fields.One2many(
        'vin.ledger.entry',
        'escrow_account_id',
        string='Double-Entry Virtual Ledger Lines',
        readonly=True
    )
    allocation_ids = fields.One2many(
        'vin.escrow.allocation',
        'escrow_account_id',
        string='Milestone Allocations'
    )
    calculated_balance = fields.Monetary(
        string='Derived Virtual Balance',
        currency_field='currency_id',
        compute='_compute_derived_balance',
        store=False,
        help="Locked Architecture Rule (ADR-002): Derived strictly from double-entry ledger rows. Never stored as a mutable float!"
    )

    def _compute_derived_balance(self):
        """
        Derives authoritative escrow cash balance from balanced double-entry ledger lines.
        Total Cash Balance = SUM(Dr cash) - SUM(Cr cash)
        """
        for record in self:
            cash_entries = record.ledger_entry_ids.filtered(lambda l: l.account_type == 'cash')
            debit_total = sum(cash_entries.mapped('debit'))
            credit_total = sum(cash_entries.mapped('credit'))
            record.calculated_balance = debit_total - credit_total

    def action_lock_escrow(self, reason):
        """Locks escrow account during active dispute or legal hold."""
        for record in self:
            record.write({
                'state': 'locked',
                'lock_reason': reason
            })
            # Also lock allocations
            record.allocation_ids.filtered(lambda a: a.state == 'allocated').write({'state': 'locked'})

    def action_unlock_escrow(self):
        """Unlocks escrow account upon dispute resolution."""
        for record in self:
            if record.state != 'locked':
                raise UserError(_("Account is not locked."))
            record.write({
                'state': 'funded',
                'lock_reason': False
            })
            record.allocation_ids.filtered(lambda a: a.state == 'locked').write({'state': 'allocated'})
