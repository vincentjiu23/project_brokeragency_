# -*- coding: utf-8 -*-
from datetime import timedelta
from decimal import Decimal
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields

class TestEscrowVirtualLedger(TransactionCase):
    """
    Test suite for Double-Entry Virtual Escrow Ledger (ADR-002),
    Zero-Variance accounting, AC-04 locked FX funding,
    AC-05 milestone release, and dispute lock freeze.
    """

    def setUp(self):
        super().setUp()
        self.Tenant = self.env['vin.tenant']
        self.Organization = self.env['vin.organization']
        self.Partner = self.env['res.partner']
        self.PartnerProfile = self.env['creative.partner.profile']
        self.Contract = self.env['vin.contract']
        self.MasterProject = self.env['vin.master.project']
        self.Workstream = self.env['vin.workstream']
        self.Milestone = self.env['vin.milestone']
        self.EscrowAccount = self.env['vin.escrow.account']
        self.Allocation = self.env['vin.escrow.allocation']
        self.LedgerEntry = self.env['vin.ledger.entry']

        self.tenant = self.Tenant.create({'code': 'T_ESCROW', 'name': 'Escrow Tenant'})
        self.client_org = self.Organization.create({
            'code': 'ORG_ESC_CLIENT',
            'name': 'Client Escrow Org',
            'tenant_id': self.tenant.id,
            'org_type': 'client'
        })
        self.partner_contact = self.Partner.create({'name': 'Premier Design Studio'})
        self.partner_profile = self.PartnerProfile.create({
            'partner_id': self.partner_contact.id,
            'tenant_id': self.tenant.id,
            'account_type': 'agency',
            'verification_status': 'verified'
        })

        self.contract = self.Contract.create({
            'title': 'Creative Production Contract',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id,
            'partner_profile_id': self.partner_profile.id,
            'total_contract_value': 20000.0,
            'completion_deadline': fields.Date.today() + timedelta(days=60),
            'state': 'active'
        })

        self.project = self.MasterProject.create({
            'code': 'PRJ_ESC_01',
            'name': 'Production Project',
            'tenant_id': self.tenant.id,
            'client_organization_id': self.client_org.id
        })
        self.workstream = self.Workstream.create({
            'name': 'Execution Phase',
            'master_project_id': self.project.id,
            'contract_id': self.contract.id
        })
        self.milestone = self.Milestone.create({
            'name': 'Milestone 1: Deliverables Signoff',
            'workstream_id': self.workstream.id,
            'target_deadline': fields.Date.today() + timedelta(days=30),
            'allocated_amount': 20000.0,
            'state': 'active'
        })

        self.escrow_account = self.EscrowAccount.create({
            'contract_id': self.contract.id
        })

    def test_zero_variance_double_entry_enforcement(self):
        """Unbalanced debit/credit transactions raise ValidationError (ADR-002)."""
        unbalanced_entries = [
            {'account_type': 'cash', 'debit': 1000.0, 'credit': 0.0},
            {'account_type': 'liability_client', 'debit': 0.0, 'credit': 950.0} # $50 variance!
        ]
        with self.assertRaises(ValidationError):
            self.LedgerEntry.post_balanced_transaction(
                escrow_account=self.escrow_account,
                entries=unbalanced_entries,
                reference="Test Unbalanced Entry"
            )

    def test_funding_deposit_and_derived_balance_ac04(self):
        """AC-04: Funding deposit posts balanced double-entry with locked FX rate."""
        from ..services.escrow_service import VirtualEscrowService
        svc = VirtualEscrowService(self.env)

        deposit_amount = 20000.0
        locked_fx = 1.0850

        svc.fund_escrow_account(
            escrow_account_id=self.escrow_account.id,
            amount=deposit_amount,
            fx_rate=locked_fx,
            reference="Client Initial Escrow Funding"
        )

        self.assertEqual(self.escrow_account.state, 'funded')
        self.assertEqual(self.escrow_account.calculated_balance, deposit_amount)
        self.assertEqual(len(self.escrow_account.ledger_entry_ids), 2)

        # Immutability validation: modifying ledger row must raise UserError
        ledger_row = self.escrow_account.ledger_entry_ids[0]
        with self.assertRaises(UserError):
            ledger_row.write({'debit': 99999.0})
        with self.assertRaises(UserError):
            ledger_row.unlink()

    def test_milestone_acceptance_release_ac05(self):
        """AC-05: Milestone acceptance releases escrow to partner and platform commission."""
        from ..services.escrow_service import VirtualEscrowService
        svc = VirtualEscrowService(self.env)

        # 1. Fund escrow
        svc.fund_escrow_account(self.escrow_account.id, 20000.0, fx_rate=1.0)
        alloc = svc.allocate_milestone(self.escrow_account.id, self.milestone.id, 20000.0)

        # Cannot release if milestone is not yet accepted
        with self.assertRaises(UserError):
            svc.release_milestone_funds(alloc.id, take_rate=0.10)

        # Milestone accepted
        self.milestone.write({'state': 'accepted'})

        # Release milestone with 10% platform take-rate
        svc.release_milestone_funds(alloc.id, take_rate=0.10)

        self.assertEqual(alloc.state, 'released')
        # Total cash remains $20,000, client liability debited by $20,000,
        # partner payable credited by $18,000, platform fee credited by $2,000
        entries = self.escrow_account.ledger_entry_ids
        partner_payable_entries = entries.filtered(lambda e: e.account_type == 'liability_partner')
        platform_fee_entries = entries.filtered(lambda e: e.account_type == 'platform_fee')

        self.assertEqual(sum(partner_payable_entries.mapped('credit')), 18000.0)
        self.assertEqual(sum(platform_fee_entries.mapped('credit')), 2000.0)

    def test_dispute_lock_blocks_release(self):
        """Active dispute locks escrow and prevents fund release."""
        from ..services.escrow_service import VirtualEscrowService
        svc = VirtualEscrowService(self.env)

        svc.fund_escrow_account(self.escrow_account.id, 10000.0)
        alloc = svc.allocate_milestone(self.escrow_account.id, self.milestone.id, 10000.0)
        self.milestone.write({'state': 'accepted'})

        # Escrow is locked due to dispute
        self.escrow_account.action_lock_escrow("Deliverable authenticity challenge")
        self.assertEqual(self.escrow_account.state, 'locked')
        self.assertEqual(alloc.state, 'locked')

        # Fund release must be blocked by security gate
        with self.assertRaises(UserError):
            svc.release_milestone_funds(alloc.id)
