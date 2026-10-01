# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from decimal import Decimal
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class VinTaxCertificate(models.Model):
    """
    Tax Certificate / Bukti Pemotongan Pajak (Q129–Q136, Q210).
    Issues and archives legally binding withholding tax receipts
    for Creative Partners, ensuring full audit readiness and tax authority compliance.
    """
    _name = 'vin.tax.certificate'
    _description = 'VIN Withholding Tax Certificate (Bukti Potong)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'tax_year desc, tax_period desc, id desc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    certificate_number = fields.Char(string='Certificate Number', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', required=True, index=True, default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False)

    invoice_id = fields.Many2one('vin.invoice', string='Underlying Invoice', index=True, tracking=True)
    tax_profile_id = fields.Many2one('vin.tax.profile', string='Partner Tax Profile', required=True, tracking=True)
    partner_profile_id = fields.Many2one('creative.partner.profile', string='Creative Partner Profile', index=True, tracking=True)

    tax_year = fields.Integer(string='Tax Year', required=True, default=lambda self: fields.Date.today().year)
    tax_period = fields.Selection([
        ('01', 'January'), ('02', 'February'), ('03', 'March'),
        ('04', 'April'), ('05', 'May'), ('06', 'June'),
        ('07', 'July'), ('08', 'August'), ('09', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='Tax Period (Month)', required=True, default=lambda self: f"{fields.Date.today().month:02d}")

    withholding_party_name = fields.Char(string='Withholding Agent Name', required=True, default='VIN Platform Operations PT')
    withholding_party_tax_id = fields.Char(string='Withholding Agent NPWP/TIN', required=True, default='01.234.567.8-012.000')

    withheld_party_name = fields.Char(string='Beneficiary / Partner Name', required=True)
    withheld_party_tax_id = fields.Char(string='Beneficiary NPWP/TIN', required=True)

    tax_article = fields.Char(string='Tax Article Law Ref', default='PPh Pasal 23 (2%)', required=True)
    currency = fields.Char(string='Currency', default='USD', required=True)

    gross_amount = fields.Float(string='Gross Compensation Amount', required=True, tracking=True)
    tax_rate = fields.Float(string='Applied Tax Rate (%)', default=2.0, required=True)
    tax_withheld_amount = fields.Float(string='Withheld Tax Amount', required=True, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated & Digitally Signed'),
        ('reported', 'Reported to Authority (e-Bupot)'),
        ('void', 'Voided')
    ], string='Certificate Status', default='draft', required=True, tracking=True)

    sha256_hash = fields.Char(string='Evidentiary SHA-256 Hash', readonly=True, copy=False)
    signature_date = fields.Datetime(string='Signed At', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('certificate_number', _('New')) == _('New'):
                year = vals.get('tax_year', fields.Date.today().year)
                month = vals.get('tax_period', '01')
                vals['certificate_number'] = f"BP-{year}{month}-{uuid.uuid4().hex[:6].upper()}"
        return super().create(vals_list)

    def action_generate_and_sign(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft certificates can be signed."))
            
            payload = {
                'uuid': rec.uuid,
                'cert_no': rec.certificate_number,
                'tenant_id': rec.tenant_id.id,
                'tax_year': rec.tax_year,
                'tax_period': rec.tax_period,
                'withholding_agent': rec.withholding_party_tax_id,
                'beneficiary': rec.withheld_party_tax_id,
                'gross': rec.gross_amount,
                'withheld': rec.tax_withheld_amount,
                'article': rec.tax_article
            }
            raw = json.dumps(payload, sort_keys=True)
            cert_hash = hashlib.sha256(raw.encode('utf-8')).hexdigest()

            rec.write({
                'state': 'generated',
                'sha256_hash': cert_hash,
                'signature_date': fields.Datetime.now()
            })

            # Audit event
            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'TAX_RESOLVED',
                    'entity_name': 'vin.tax.certificate',
                    'entity_id': str(rec.id),
                    'state_after': 'generated',
                    'payload': json.dumps({'cert_number': rec.certificate_number, 'sha256': cert_hash})
                })
            rec.message_post(body=_("Tax certificate generated and digitally sealed. SHA-256: %s") % cert_hash)

    def action_mark_reported(self):
        for rec in self:
            if rec.state != 'generated':
                raise UserError(_("Only generated certificates can be marked as reported to authority."))
            rec.write({'state': 'reported'})
            rec.message_post(body=_("Reported to official tax authority e-filing system."))

    def action_void(self, reason=None):
        for rec in self:
            rec.write({'state': 'void'})
            rec.message_post(body=_("Tax certificate voided. Reason: %s") % (reason or "Not specified"))
