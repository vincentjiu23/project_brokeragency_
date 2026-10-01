# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from decimal import Decimal
import logging
import uuid
from odoo import fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class VirtualEscrowService:
    """Orchestrates virtual escrow ledger postings, milestone releases, and dispute locks."""

    def __init__(self, env):
        self.env = env

    def fund_escrow_account(self, escrow_account_id, amount, fx_rate=1.0, reference="Deposit Funding"):
        """
        AC-04: Funds virtual escrow ledger with locked FX rate timestamp.
        Posts balanced double-entry:
          Dr: cash (Asset)
          Cr: liability_client (Liability)
        """
        account = self.env['vin.escrow.account'].browse(escrow_account_id)
        if not account.exists():
            raise UserError(_("Escrow account not found."))

        if amount <= 0:
            raise UserError(_("Funding deposit amount must be greater than zero."))

        fx_timestamp = fields.Datetime.now()
        tx_id = str(uuid.uuid4())

        # Post balanced double-entry
        entries = [
            {'account_type': 'cash', 'debit': amount, 'credit': 0.0},
            {'account_type': 'liability_client', 'debit': 0.0, 'credit': amount}
        ]
        self.env['vin.ledger.entry'].post_balanced_transaction(
            escrow_account=account,
            entries=entries,
            reference=f"{reference} (FX: {fx_rate:.4f})",
            transaction_id=tx_id
        )

        account.write({'state': 'funded'})

        # Record audit event (AC-04)
        self.env['vin.audit.event'].sudo().record_event(
            action='ESCROW_ALLOCATED',
            subject_type='vin.escrow.account',
            subject_id=account.uuid,
            tenant_id=account.tenant_id.uuid,
            payload={
                'account_number': account.account_number,
                'amount': float(amount),
                'fx_rate': float(fx_rate),
                'fx_locked_at': str(fx_timestamp),
                'transaction_id': tx_id
            }
        )

        return account

    def allocate_milestone(self, escrow_account_id, milestone_id, amount, fx_rate=1.0):
        """Creates milestone allocation tied to the virtual escrow account."""
        account = self.env['vin.escrow.account'].browse(escrow_account_id)
        allocation = self.env['vin.escrow.allocation'].create({
            'escrow_account_id': account.id,
            'milestone_id': milestone_id,
            'allocated_amount': amount,
            'fx_rate': fx_rate,
            'fx_locked_at': fields.Datetime.now(),
            'state': 'allocated'
        })
        return allocation

    def release_milestone_funds(self, allocation_id, take_rate=0.10):
        """
        AC-05: Releases escrow funds upon milestone acceptance.
        Balanced double-entry:
          Dr: liability_client (total amount)
          Cr: liability_partner (net payout)
          Cr: platform_fee (platform revenue take-rate)
        """
        alloc = self.env['vin.escrow.allocation'].browse(allocation_id)
        if not alloc.exists():
            raise UserError(_("Allocation not found."))

        if alloc.state == 'locked':
            raise UserError(_("Security Gate: Cannot release funds from a locked/frozen escrow allocation!"))
        if alloc.state == 'released':
            raise UserError(_("Allocation funds have already been released."))

        milestone = alloc.milestone_id
        if milestone.state != 'accepted':
            raise UserError(_("Cannot release escrow: Milestone '%s' is not accepted (state: %s)!") % (milestone.name, milestone.state))

        total_amount = Decimal(str(alloc.allocated_amount))
        commission_rate = Decimal(str(take_rate))
        platform_fee = (total_amount * commission_rate).quantize(Decimal('0.01'))
        partner_net = total_amount - platform_fee

        account = alloc.escrow_account_id
        tx_id = str(uuid.uuid4())

        entries = [
            {'account_type': 'liability_client', 'debit': float(total_amount), 'credit': 0.0},
            {'account_type': 'liability_partner', 'debit': 0.0, 'credit': float(partner_net)},
            {'account_type': 'platform_fee', 'debit': 0.0, 'credit': float(platform_fee)}
        ]

        self.env['vin.ledger.entry'].post_balanced_transaction(
            escrow_account=account,
            entries=entries,
            reference=f"Milestone Acceptance Release: {milestone.name}",
            transaction_id=tx_id
        )

        alloc.write({'state': 'released'})

        # Record audit event
        self.env['vin.audit.event'].sudo().record_event(
            action='ESCROW_RELEASED',
            subject_type='vin.escrow.allocation',
            subject_id=alloc.uuid,
            tenant_id=account.tenant_id.uuid,
            payload={
                'milestone_name': milestone.name,
                'total_released': float(total_amount),
                'partner_net': float(partner_net),
                'platform_fee': float(platform_fee),
                'transaction_id': tx_id
            }
        )

        return alloc
