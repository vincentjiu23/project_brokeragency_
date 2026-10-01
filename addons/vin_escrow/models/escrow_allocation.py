# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinEscrowAllocation(models.Model):
    _name = 'vin.escrow.allocation'
    _description = 'VIN Milestone Escrow Allocation'
    _order = 'create_date asc'

    uuid = fields.Char(
        string='Allocation UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    escrow_account_id = fields.Many2one(
        'vin.escrow.account',
        string='Virtual Escrow Account',
        required=True,
        readonly=True,
        index=True,
        ondelete='cascade'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='escrow_account_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    milestone_id = fields.Many2one(
        'vin.milestone',
        string='Target Milestone',
        required=True,
        index=True
    )
    allocated_amount = fields.Monetary(
        string='Allocated Milestone Amount',
        currency_field='currency_id',
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='escrow_account_id.currency_id',
        readonly=True
    )
    fx_rate = fields.Float(
        string='Locked FX Conversion Rate',
        digits=(12, 6),
        default=1.0,
        readonly=True,
        help="AC-04: Locked FX conversion rate captured upon funding."
    )
    fx_locked_at = fields.Datetime(
        string='FX Lock Timestamp',
        readonly=True,
        help="AC-04: Timestamp when FX rate was frozen into virtual ledger."
    )
    state = fields.Selection(
        [
            ('allocated', 'Funded & Allocated to Milestone'),
            ('locked', 'Locked (Dispute Freeze)'),
            ('released', 'Released to Partner Payable'),
            ('refunded', 'Refunded to Client')
        ],
        string='Allocation State',
        required=True,
        default='allocated',
        index=True
    )
