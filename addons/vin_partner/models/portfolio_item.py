# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinPortfolioItem(models.Model):
    _name = 'vin.portfolio.item'
    _description = 'VIN Creative Partner Portfolio Showcase'
    _order = 'create_date desc'

    uuid = fields.Char(
        string='Portfolio Item UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    partner_profile_id = fields.Many2one(
        'creative.partner.profile',
        string='Creative Partner',
        required=True,
        ondelete='cascade',
        index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='partner_profile_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    title = fields.Char(
        string='Case Study / Project Title',
        required=True
    )
    description = fields.Text(
        string='Creative Challenge & Solution'
    )
    publication_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('pending_approval', 'Pending IP / NDA Review'),
            ('published', 'Published & Indexed'),
            ('blocked', 'Blocked (NDA / IP Conflict)')
        ],
        string='Publication State',
        required=True,
        default='draft',
        index=True
    )
    display_allowed = fields.Boolean(
        string='IP Display Allowed (PORTFOLIO_DISPLAY_ALLOWED)',
        default=False,
        help="Locked Rule Q124: Only items explicitly cleared by IP assignment addendum and NDA are indexable."
    )
    asset_vault_ref = fields.Char(
        string='Asset Vault Preview SHA-256 Hash',
        required=True
    )
    external_preview_url = fields.Char(
        string='External Showcase URL'
    )

    def action_publish(self):
        """Publishes portfolio item strictly if display_allowed gate is satisfied."""
        for record in self:
            if not record.display_allowed:
                raise UserError(_("Security / IP Gate: Cannot publish portfolio item without verified PORTFOLIO_DISPLAY_ALLOWED clearance!"))
            record.write({'publication_state': 'published'})
            self.env['vin.audit.event'].sudo().record_event(
                action='PORTFOLIO_PUBLISHED',
                subject_type='vin.portfolio.item',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={'title': record.title, 'display_allowed': True}
            )
