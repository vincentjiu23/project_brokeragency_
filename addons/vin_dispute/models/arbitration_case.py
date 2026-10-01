# -*- coding: utf-8 -*-
import hashlib
import json
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinArbitrationCase(models.Model):
    """
    Tier 3 Binding Arbitration Case Model (Q91–Q98, Q175).
    Coordinates formal third-party legal arbitration or platform panel adjudication,
    rendering legally binding awards that enforce automated escrow settlement.
    """
    _name = 'vin.arbitration.case'
    _description = 'VIN Binding Arbitration Case'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'filing_date desc, id desc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    case_reference = fields.Char(string='Arbitration Docket Ref', required=True, copy=False, readonly=True, default=lambda self: _('New'), index=True)
    dispute_id = fields.Many2one('vin.dispute', string='Underlying Dispute', required=True, ondelete='cascade', index=True)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', related='dispute_id.tenant_id', store=True, index=True)

    arbitration_body = fields.Selection([
        ('platform_panel', 'VIN Platform Senior Adjudication Panel'),
        ('basyarnas', 'Badan Arbitrase Syariah Nasional (Basyarnas)'),
        ('bani', 'Badan Arbitrase Nasional Indonesia (BANI)'),
        ('siac', 'Singapore International Arbitration Centre (SIAC)'),
        ('aaa', 'American Arbitration Association / ICDR'),
        ('independent_expert', 'Certified Independent Industry Expert')
    ], string='Arbitration Tribunal / Body', required=True, default='platform_panel', tracking=True)

    arbitrator_lead_name = fields.Char(string='Presiding Arbitrator', required=True, default='Chief Legal Officer')
    arbitration_fee = fields.Float(string='Arbitration Administration Fee', default=500.0)
    filing_date = fields.Date(string='Formal Docket Filing Date', default=fields.Date.context_today, required=True)
    hearing_date = fields.Date(string='Arbitration Hearing Date', tracking=True)

    binding_ruling_summary = fields.Text(string='Binding Award & Ruling Text', tracking=True)
    ruling_sha256 = fields.Char(string='Cryptographic Digest of Ruling', readonly=True, copy=False)
    ruling_rendered_at = fields.Datetime(string='Ruling Date', readonly=True)

    state = fields.Selection([
        ('filed', 'Docket Filed'),
        ('in_review', 'Tribunal Reviewing Evidence'),
        ('hearing', 'Formal Oral / Written Hearing'),
        ('ruling_rendered', 'Binding Ruling Rendered'),
        ('enforced', 'Enforced in Escrow')
    ], string='Arbitration Status', default='filed', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('case_reference', _('New')) == _('New'):
                vals['case_reference'] = f"ARB-{uuid.uuid4().hex[:8].upper()}"
        return super().create(vals_list)

    def action_render_binding_ruling(self, ruling_text, client_award_refund, partner_award_payout):
        """
        Renders binding final arbitral award and executes automatic escrow ledger settlement.
        """
        self.ensure_one()
        if self.state not in ['in_review', 'hearing']:
            raise UserError(_("Ruling can only be rendered after tribunal review or hearing."))

        # Compute SHA-256 digest of final arbitral award
        raw = f"{self.case_reference}:{ruling_text}:{client_award_refund}:{partner_award_payout}:{fields.Datetime.now()}"
        digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()

        self.write({
            'state': 'ruling_rendered',
            'binding_ruling_summary': ruling_text,
            'ruling_sha256': digest,
            'ruling_rendered_at': fields.Datetime.now()
        })

        # Automatically execute resolution on the parent dispute
        resolution_type = 'split_settlement'
        if client_award_refund == 0.0:
            resolution_type = 'full_release_to_partner'
        elif partner_award_payout == 0.0:
            resolution_type = 'full_refund_to_client'

        self.dispute_id.action_resolve_settlement(
            resolution_type=resolution_type,
            client_refund=client_award_refund,
            partner_payout=partner_award_payout,
            summary=f"Arbitration Binding Award ({self.case_reference}): {ruling_text}"
        )

        self.write({'state': 'enforced'})
        self.message_post(body=_("Binding Arbitral Award rendered and enforced. SHA-256: %s") % digest)
