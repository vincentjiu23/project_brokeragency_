# -*- coding: utf-8 -*-
"""
Payment Reconciliation Repository.

Read-projection queries for payment reconciliation, reporting, and audit.
These are query-only operations — no mutations.
"""
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class PaymentReconciliationRepository:
    """Query objects for payment reporting and reconciliation."""

    def __init__(self, env):
        self.env = env

    def get_pending_payouts(self, tenant_id=None, provider_id=None):
        """Returns payouts awaiting approval or processing."""
        domain = [('state', 'in', ['draft', 'pending_approval', 'approved', 'submitted', 'processing'])]
        if tenant_id:
            domain.append(('tenant_id', '=', tenant_id))
        if provider_id:
            domain.append(('provider_id', '=', provider_id))
        return self.env['vin.payout'].search(domain, order='create_date asc')

    def get_failed_payouts_for_retry(self, tenant_id=None, max_retries=3):
        """Returns failed payouts eligible for retry."""
        domain = [
            ('state', '=', 'failed'),
            ('retry_count', '<', max_retries)
        ]
        if tenant_id:
            domain.append(('tenant_id', '=', tenant_id))
        return self.env['vin.payout'].search(domain, order='create_date asc')

    def get_escrow_reconciliation_report(self, escrow_account_id):
        """
        Generates an escrow reconciliation report:
          - Total funded (cash Dr)
          - Total released (liability_partner Cr)
          - Platform fees collected (platform_fee Cr)
          - Total disbursed (cash Cr from payouts)
          - Pending balance
        """
        account = self.env['vin.escrow.account'].browse(escrow_account_id)
        entries = account.ledger_entry_ids

        cash_entries = entries.filtered(lambda e: e.account_type == 'cash')
        liability_client = entries.filtered(lambda e: e.account_type == 'liability_client')
        liability_partner = entries.filtered(lambda e: e.account_type == 'liability_partner')
        platform_fee = entries.filtered(lambda e: e.account_type == 'platform_fee')

        total_funded = sum(cash_entries.mapped('debit'))
        total_disbursed = sum(cash_entries.mapped('credit'))
        total_released_to_partner = sum(liability_partner.mapped('credit'))
        total_platform_fees = sum(platform_fee.mapped('credit'))
        current_balance = total_funded - total_disbursed

        return {
            'account_number': account.account_number,
            'state': account.state,
            'total_funded': total_funded,
            'total_disbursed': total_disbursed,
            'total_released_to_partner': total_released_to_partner,
            'total_platform_fees': total_platform_fees,
            'current_cash_balance': current_balance,
            'derived_balance': account.calculated_balance,
            'entry_count': len(entries),
            'allocation_count': len(account.allocation_ids),
        }

    def get_unprocessed_webhooks(self, provider_code=None, limit=100):
        """Returns webhooks pending processing (for retry/dead-letter processing)."""
        domain = [('processing_state', '=', 'pending')]
        if provider_code:
            domain.append(('provider_code', '=', provider_code))
        return self.env['vin.webhook.log'].search(domain, order='received_at asc', limit=limit)

    def get_payout_summary_by_provider(self, tenant_id, date_from=None, date_to=None):
        """Aggregated payout summary grouped by provider."""
        domain = [('tenant_id', '=', tenant_id)]
        if date_from:
            domain.append(('create_date', '>=', date_from))
        if date_to:
            domain.append(('create_date', '<=', date_to))

        payouts = self.env['vin.payout'].search(domain)

        summary = {}
        for payout in payouts:
            provider_name = payout.provider_id.name if payout.provider_id else 'Unassigned'
            if provider_name not in summary:
                summary[provider_name] = {
                    'total_payouts': 0,
                    'total_gross': 0.0,
                    'total_net': 0.0,
                    'succeeded': 0,
                    'failed': 0,
                    'pending': 0,
                }
            summary[provider_name]['total_payouts'] += 1
            summary[provider_name]['total_gross'] += payout.gross_amount
            summary[provider_name]['total_net'] += payout.net_payout_amount
            if payout.state == 'succeeded':
                summary[provider_name]['succeeded'] += 1
            elif payout.state in ('failed', 'rejected'):
                summary[provider_name]['failed'] += 1
            else:
                summary[provider_name]['pending'] += 1

        return summary
