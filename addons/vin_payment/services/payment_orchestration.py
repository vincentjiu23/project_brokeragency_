# -*- coding: utf-8 -*-
"""
Payment Orchestration Service.

Orchestrates the end-to-end payout lifecycle:
  Escrow Release → Payout Creation → Provider Submission → Settlement → Ledger Posting

This service bridges the vin_escrow domain with the vin_payment domain,
coordinating the flow from milestone acceptance through actual disbursement.
"""
import logging
import uuid
from decimal import Decimal
from odoo import fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaymentOrchestrationService:
    """Orchestrates payouts from escrow release through provider settlement."""

    def __init__(self, env):
        self.env = env

    def initiate_payout_from_allocation(self, allocation_id, provider_id=None, tax_withholding=0.0):
        """
        Creates a payout record from a released escrow allocation.
        
        Preconditions:
          - Allocation must be in 'released' state (milestone accepted & escrow released)
          - Escrow account must not be locked
          
        Args:
            allocation_id: ID of the vin.escrow.allocation record
            provider_id: Optional specific payment provider ID. If None, auto-selects.
            tax_withholding: WHT amount to deduct before payout (default 0)
            
        Returns:
            vin.payout record in 'draft' state
        """
        alloc = self.env['vin.escrow.allocation'].browse(allocation_id)
        if not alloc.exists():
            raise UserError(_("Escrow allocation not found."))

        if alloc.state != 'released':
            raise UserError(_(
                "Cannot initiate payout: Allocation '%s' is not in 'released' state (current: %s). "
                "Milestone must be accepted and escrow released first."
            ) % (alloc.uuid, alloc.state))

        account = alloc.escrow_account_id
        if account.state == 'locked':
            raise UserError(_(
                "Cannot initiate payout: Escrow account '%s' is locked. "
                "Reason: %s"
            ) % (account.account_number, account.lock_reason))

        # Auto-select provider if not specified
        if not provider_id:
            provider = self._select_provider(account.tenant_id, account.currency_id)
            provider_id = provider.id if provider else None

        if not provider_id:
            raise UserError(_("No active payment provider available for this currency and tenant."))

        # Calculate gross from released allocation
        gross = Decimal(str(alloc.allocated_amount))
        # Apply take-rate deduction (already handled in escrow release, partner_net is the allocation)
        # Tax withholding is applied on top
        wht = Decimal(str(tax_withholding))

        payout = self.env['vin.payout'].create({
            'tenant_id': account.tenant_id.id,
            'escrow_account_id': account.id,
            'allocation_id': alloc.id,
            'provider_id': provider_id,
            'gross_amount': float(gross),
            'tax_withholding': float(wht),
            'currency_id': account.currency_id.id,
            'initiated_by_id': self.env.user.id,
            'state': 'draft',
        })

        _logger.info(
            "Payout %s created for allocation %s, gross=%s, wht=%s",
            payout.reference, alloc.uuid, gross, wht
        )

        return payout

    def submit_payout_to_provider(self, payout_id):
        """
        Submits an approved payout to the external payment provider.
        
        This method interfaces with the payment gateway service abstraction.
        In production, this calls the provider's API. Here we simulate the
        provider submission and return a provider transaction reference.
        
        Preconditions:
          - Payout must be in 'approved' state
          - Provider must be in 'live' or 'test' state
        """
        payout = self.env['vin.payout'].browse(payout_id)
        if not payout.exists():
            raise UserError(_("Payout not found."))

        if payout.state != 'approved':
            raise UserError(_(
                "Cannot submit: Payout '%s' is not in 'approved' state (current: %s)."
            ) % (payout.reference, payout.state))

        provider = payout.provider_id
        if not provider or provider.state not in ('live', 'test'):
            raise UserError(_(
                "Payment provider '%s' is not active (state: %s)."
            ) % (provider.name if provider else 'None', provider.state if provider else 'N/A'))

        # --- Provider Gateway Abstraction ---
        # In production, this delegates to the payment_gateway service
        # which calls the actual provider API (Stripe, Xendit, etc.)
        provider_tx_id = f"{provider.code}-{uuid.uuid4().hex[:12]}"

        payout.action_mark_submitted(provider_tx_id)

        _logger.info(
            "Payout %s submitted to provider %s, tx_id=%s",
            payout.reference, provider.name, provider_tx_id
        )

        return {
            'payout_id': payout.id,
            'provider_transaction_id': provider_tx_id,
            'status': 'submitted'
        }

    def process_provider_callback(self, payout_id, status, provider_ref=None,
                                   raw_response=None, failure_code=None, failure_message=None):
        """
        Processes a payment provider callback/webhook result.
        
        This is called by the webhook controller after signature verification
        and idempotent deduplication.
        
        Args:
            payout_id: ID of the vin.payout record
            status: Provider status ('succeeded', 'failed', 'processing')
            provider_ref: External provider reference
            raw_response: Raw provider JSON response
            failure_code: Error code if failed
            failure_message: Error description if failed
        """
        payout = self.env['vin.payout'].browse(payout_id)
        if not payout.exists():
            raise UserError(_("Payout not found for provider callback."))

        if status == 'processing':
            payout.action_mark_processing()
        elif status == 'succeeded':
            payout.action_mark_succeeded(
                provider_ref=provider_ref,
                raw_response=raw_response
            )
        elif status == 'failed':
            payout.action_mark_failed(
                failure_code=failure_code,
                failure_message=failure_message,
                raw_response=raw_response
            )
        else:
            _logger.warning(
                "Unknown provider callback status '%s' for payout %s",
                status, payout.reference
            )

    def initiate_refund(self, payout_id, reason="Client-initiated refund"):
        """
        Initiates a refund for a succeeded payout.
        
        Refund flow:
          succeeded → refund_pending → refund_processing → refunded
          
        Posts reversal entries to the escrow ledger:
          Dr: cash (restore cash asset)
          Cr: liability_client (restore client liability for re-refund)
        """
        payout = self.env['vin.payout'].browse(payout_id)
        if not payout.exists():
            raise UserError(_("Payout not found."))

        if payout.state != 'succeeded':
            raise UserError(_(
                "Can only refund succeeded payouts. Current state: %s"
            ) % payout.state)

        payout._validate_transition('refund_pending')
        payout.write({'state': 'refund_pending'})
        payout._record_event('refund_initiated')

        # Audit
        self.env['vin.audit.event'].sudo().record_event(
            action='PAYOUT_REFUND_INITIATED',
            subject_type='vin.payout',
            subject_id=payout.uuid,
            tenant_id=payout.tenant_id.uuid,
            payload={
                'reference': payout.reference,
                'amount': float(payout.net_payout_amount),
                'reason': reason,
            }
        )

        return payout

    def complete_refund(self, payout_id, provider_ref=None, raw_response=None):
        """
        Marks refund as completed and posts reversal ledger entries.
        
        Reversal double-entry:
          Dr: cash (money returned to escrow)
          Cr: liability_client (restore client deposit)
        """
        payout = self.env['vin.payout'].browse(payout_id)
        if payout.state == 'refund_pending':
            payout.write({'state': 'refund_processing'})
            payout._record_event('refund_processing')

        if payout.state != 'refund_processing':
            raise UserError(_(
                "Cannot complete refund: Payout '%s' is not in refund_processing state."
            ) % payout.reference)

        payout.write({'state': 'refunded'})
        payout._record_event('refund_succeeded', provider_ref=provider_ref, raw_response=raw_response)

        # Post reversal ledger entries
        net = Decimal(str(payout.net_payout_amount))
        account = payout.escrow_account_id

        entries = [
            {'account_type': 'cash', 'debit': float(net), 'credit': 0.0},
            {'account_type': 'liability_client', 'debit': 0.0, 'credit': float(net)},
        ]
        self.env['vin.ledger.entry'].post_balanced_transaction(
            escrow_account=account,
            entries=entries,
            reference=f"Refund Reversal: {payout.reference}",
            transaction_id=str(uuid.uuid4())
        )

        # Update allocation state
        alloc = payout.allocation_id
        if alloc.state == 'released':
            alloc.write({'state': 'refunded'})

        # Audit
        self.env['vin.audit.event'].sudo().record_event(
            action='PAYOUT_REFUNDED',
            subject_type='vin.payout',
            subject_id=payout.uuid,
            tenant_id=payout.tenant_id.uuid,
            payload={
                'reference': payout.reference,
                'refunded_amount': float(net),
                'provider_ref': provider_ref,
            }
        )

        return payout

    def _select_provider(self, tenant, currency):
        """
        Auto-selects the highest-priority active payment provider
        for the given tenant and currency.
        """
        providers = self.env['vin.payment.provider'].search([
            ('tenant_id', '=', tenant.id),
            ('state', 'in', ['live', 'test']),
            ('supported_currency_ids', 'in', [currency.id])
        ], order='sequence asc', limit=1)
        return providers[0] if providers else None
