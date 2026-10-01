# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from decimal import Decimal
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class VinInvoice(models.Model):
    """
    Invoice Model (Q129–Q136, Q210).
    Manages client milestone billing, partner payout invoices,
    and platform fee invoicing with multi-jurisdiction tax breakdown,
    immutable digital signatures, and audit tracking.
    """
    _name = 'vin.invoice'
    _description = 'VIN Tax Compliant Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc, id desc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    invoice_number = fields.Char(string='Invoice Number', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', required=True, index=True, default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False)

    invoice_type = fields.Selection([
        ('client_milestone', 'Client Milestone Billing'),
        ('partner_payout', 'Partner Payout Disbursement'),
        ('subscription_fee', 'Platform Subscription Fee'),
        ('platform_commission', 'Platform Take-Rate Commission')
    ], string='Invoice Type', required=True, default='client_milestone', tracking=True)

    client_organization_id = fields.Many2one('vin.organization', string='Client Organization', index=True, tracking=True)
    partner_profile_id = fields.Many2one('creative.partner.profile', string='Creative Partner Profile', index=True, tracking=True)
    contract_id = fields.Many2one('vin.contract', string='Contract Reference', index=True, tracking=True)
    milestone_id = fields.Many2one('vin.milestone', string='Milestone Reference', index=True)
    escrow_allocation_id = fields.Many2one('vin.escrow.allocation', string='Escrow Allocation Reference', index=True)
    payout_id = fields.Many2one('vin.payout', string='Payout Reference', index=True)

    tax_profile_id = fields.Many2one('vin.tax.profile', string='Applied Tax Profile', tracking=True)
    issue_date = fields.Date(string='Issue Date', default=fields.Date.context_today, required=True, tracking=True)
    due_date = fields.Date(string='Due Date', tracking=True)

    currency = fields.Char(string='Currency', default='USD', required=True)
    subtotal_amount = fields.Float(string='Subtotal Amount', compute='_compute_totals', store=True, tracking=True)
    vat_rate = fields.Float(string='VAT Rate (%)', default=0.0)
    vat_amount = fields.Float(string='VAT Amount', compute='_compute_totals', store=True, tracking=True)
    wht_rate = fields.Float(string='WHT Rate (%)', default=0.0)
    wht_amount = fields.Float(string='WHT Withheld Amount', compute='_compute_totals', store=True, tracking=True)
    gross_total = fields.Float(string='Gross Total (Subtotal + VAT)', compute='_compute_totals', store=True, tracking=True)
    net_payable = fields.Float(string='Net Payable (Gross - WHT)', compute='_compute_totals', store=True, tracking=True)

    invoice_line_ids = fields.One2many('vin.invoice.line', 'invoice_id', string='Invoice Lines')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded')
    ], string='Status', default='draft', required=True, tracking=True)

    payment_reference = fields.Char(string='Payment Reference', copy=False)
    paid_at = fields.Datetime(string='Paid At', readonly=True)
    digital_signature_hash = fields.Char(string='SHA-256 Digital Hash', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('invoice_number', _('New')) == _('New'):
                prefix = 'INV-CLI' if vals.get('invoice_type') == 'client_milestone' else 'INV-PAY'
                vals['invoice_number'] = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
        return super().create(vals_list)

    @api.depends('invoice_line_ids.subtotal', 'invoice_line_ids.vat_amount', 'invoice_line_ids.wht_amount')
    def _compute_totals(self):
        for rec in self:
            subtotal = Decimal('0.00')
            vat = Decimal('0.00')
            wht = Decimal('0.00')
            for line in rec.invoice_line_ids:
                subtotal += Decimal(str(round(line.subtotal, 2)))
                vat += Decimal(str(round(line.vat_amount, 2)))
                wht += Decimal(str(round(line.wht_amount, 2)))
            
            gross = subtotal + vat
            net = gross - wht

            rec.subtotal_amount = float(subtotal)
            rec.vat_amount = float(vat)
            rec.wht_amount = float(wht)
            rec.gross_total = float(gross)
            rec.net_payable = float(net)

    def _generate_digital_signature(self):
        """Computes SHA-256 hash of immutable invoice snapshot for audit integrity."""
        self.ensure_one()
        payload = {
            'uuid': self.uuid,
            'invoice_number': self.invoice_number,
            'tenant_id': self.tenant_id.id,
            'type': self.invoice_type,
            'client_org': self.client_organization_id.id if self.client_organization_id else None,
            'partner': self.partner_profile_id.id if self.partner_profile_id else None,
            'subtotal': self.subtotal_amount,
            'vat': self.vat_amount,
            'wht': self.wht_amount,
            'net_payable': self.net_payable,
            'currency': self.currency,
            'issued_date': str(self.issue_date)
        }
        raw_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()

    def action_issue(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft invoices can be issued."))
            if not rec.invoice_line_ids:
                raise UserError(_("Cannot issue invoice without invoice lines."))
            sig_hash = rec._generate_digital_signature()
            rec.write({
                'state': 'issued',
                'digital_signature_hash': sig_hash
            })
            # Log audit event
            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'INVOICE_GENERATED',
                    'entity_name': 'vin.invoice',
                    'entity_id': str(rec.id),
                    'state_after': 'issued',
                    'payload': json.dumps({'invoice_number': rec.invoice_number, 'sha256': sig_hash})
                })
            rec.message_post(body=_("Invoice issued with SHA-256 signature: %s") % sig_hash)

    def action_mark_paid(self, payment_ref=None):
        for rec in self:
            if rec.state != 'issued':
                raise UserError(_("Only issued invoices can be marked as paid."))
            rec.write({
                'state': 'paid',
                'payment_reference': payment_ref or rec.payment_reference,
                'paid_at': fields.Datetime.now()
            })
            rec.message_post(body=_("Invoice marked as paid. Ref: %s") % (payment_ref or "Manual"))

    def action_cancel(self, reason=None):
        for rec in self:
            if rec.state in ['paid', 'refunded']:
                raise UserError(_("Paid or refunded invoices cannot be cancelled. Issue a credit note instead."))
            rec.write({'state': 'cancelled'})
            rec.message_post(body=_("Invoice cancelled. Reason: %s") % (reason or "Not specified"))


class VinInvoiceLine(models.Model):
    """Invoice Line Item with granular line-level tax calculation."""
    _name = 'vin.invoice.line'
    _description = 'VIN Invoice Line Item'

    invoice_id = fields.Many2one('vin.invoice', string='Invoice', required=True, ondelete='cascade', index=True)
    description = fields.Char(string='Description / Service Deliverable', required=True)
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    unit_price = fields.Float(string='Unit Price', default=0.0, required=True)
    subtotal = fields.Float(string='Subtotal', compute='_compute_totals', store=True)

    vat_rate = fields.Float(string='VAT Rate (%)', default=0.0)
    vat_amount = fields.Float(string='VAT Amount', compute='_compute_totals', store=True)
    wht_rate = fields.Float(string='WHT Rate (%)', default=0.0)
    wht_amount = fields.Float(string='WHT Amount', compute='_compute_totals', store=True)
    total = fields.Float(string='Total Payable', compute='_compute_totals', store=True)

    @api.depends('quantity', 'unit_price', 'vat_rate', 'wht_rate')
    def _compute_totals(self):
        for line in self:
            qty = Decimal(str(line.quantity))
            price = Decimal(str(line.unit_price))
            sub = qty * price
            
            vat_pct = Decimal(str(line.vat_rate)) / Decimal('100.0')
            vat = sub * vat_pct

            wht_pct = Decimal(str(line.wht_rate)) / Decimal('100.0')
            wht = sub * wht_pct

            tot = sub + vat - wht

            line.subtotal = float(round(sub, 2))
            line.vat_amount = float(round(vat, 2))
            line.wht_amount = float(round(wht, 2))
            line.total = float(round(tot, 2))
