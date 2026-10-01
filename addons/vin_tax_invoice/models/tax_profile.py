# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class VinTaxProfile(models.Model):
    """
    Tax Profile model (Q129–Q136, Q210).
    Manages multi-jurisdiction tax identification, entity classification,
    VAT/PPN status, and Withholding Tax (WHT/PPh) determination.
    """
    _name = 'vin.tax.profile'
    _description = 'VIN Tax Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    name = fields.Char(string='Profile Name', required=True, tracking=True)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', required=True, index=True, default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False)
    
    organization_id = fields.Many2one('vin.organization', string='Client Organization', index=True, tracking=True)
    partner_profile_id = fields.Many2one('creative.partner.profile', string='Creative Partner Profile', index=True, tracking=True)
    legal_entity_id = fields.Many2one('vin.legal.entity', string='Legal Entity')

    tax_id_number = fields.Char(string='Tax Identification Number (NPWP/TIN/VAT)', required=True, tracking=True)
    jurisdiction = fields.Selection([
        ('ID', 'Indonesia (DGT / Dirjen Pajak)'),
        ('US', 'United States (IRS)'),
        ('SG', 'Singapore (IRAS)'),
        ('GB', 'United Kingdom (HMRC)'),
        ('EU', 'European Union (VAT)'),
        ('OTHER', 'Other / Cross-Border')
    ], string='Tax Jurisdiction', default='ID', required=True, tracking=True)

    entity_type = fields.Selection([
        ('corporate', 'Corporate / Badan Usaha'),
        ('individual_business', 'Individual Business (PKP Orang Pribadi)'),
        ('individual_freelance', 'Individual Freelancer (Non-PKP)'),
        ('non_resident', 'Non-Resident Foreign Entity (WPLN)')
    ], string='Entity Classification', default='corporate', required=True, tracking=True)

    vat_registered = fields.Boolean(string='VAT/PPN Registered (Pengusaha Kena Pajak)', default=True, tracking=True)
    default_vat_rate = fields.Float(string='Default VAT Rate (%)', default=11.0, tracking=True)
    default_wht_rate = fields.Float(string='Default WHT Rate (%)', default=2.0, tracking=True)

    wht_article = fields.Selection([
        ('pph_23', 'PPh Pasal 23 (2% Domestic Corporate Services)'),
        ('pph_21', 'PPh Pasal 21 (Individual Freelance Progressive)'),
        ('pph_26', 'PPh Pasal 26 (20% Foreign Non-Resident WHT)'),
        ('pph_26_treaty', 'PPh Pasal 26 Treaty / DGT Reduced Rate (10%)'),
        ('w8_w9', 'US Backup Withholding (W-8BEN / W-9)'),
        ('zero_rated', 'Zero-Rated / Tax Exempt')
    ], string='WHT Category', default='pph_23', required=True, tracking=True)

    tax_exemption_number = fields.Char(string='SKB / Exemption Certificate Ref')
    has_npwp = fields.Boolean(string='Has Valid Tax ID', default=True, compute='_compute_has_npwp', store=True)

    effective_date = fields.Date(string='Effective Date', default=fields.Date.context_today, required=True)
    expiry_date = fields.Date(string='Expiry Date')

    status = fields.Selection([
        ('draft', 'Draft'),
        ('verified', 'Verified & Active'),
        ('expired', 'Expired'),
        ('rejected', 'Rejected')
    ], string='Verification Status', default='draft', required=True, tracking=True)

    verification_notes = fields.Text(string='Verification Notes')
    verified_by_user_id = fields.Many2one('res.users', string='Verified By', readonly=True)
    verified_at = fields.Datetime(string='Verified At', readonly=True)

    @api.depends('tax_id_number')
    def _compute_has_npwp(self):
        for rec in self:
            rec.has_npwp = bool(rec.tax_id_number and len(rec.tax_id_number.strip()) >= 5)

    @api.constrains('default_vat_rate', 'default_wht_rate')
    def _check_rates(self):
        for rec in self:
            if rec.default_vat_rate < 0.0 or rec.default_vat_rate > 100.0:
                raise ValidationError(_("VAT rate must be between 0% and 100%."))
            if rec.default_wht_rate < 0.0 or rec.default_wht_rate > 100.0:
                raise ValidationError(_("WHT rate must be between 0% and 100%."))

    def action_verify(self):
        for rec in self:
            if not rec.tax_id_number:
                raise UserError(_("Tax ID Number is required for verification."))
            rec.write({
                'status': 'verified',
                'verified_by_user_id': self.env.user.id,
                'verified_at': fields.Datetime.now()
            })
            rec.message_post(body=_("Tax profile verified and activated by %s") % self.env.user.name)

    def action_reject(self, reason=None):
        for rec in self:
            rec.write({
                'status': 'rejected',
                'verification_notes': reason or _("Tax documentation rejected upon review.")
            })
            rec.message_post(body=_("Tax profile marked rejected: %s") % (reason or "No reason provided"))
