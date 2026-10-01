# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class CreativePartnerProfile(models.Model):
    _name = 'creative.partner.profile'
    _description = 'VIN Creative Partner Professional Layer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'public_rating desc, create_date desc'

    uuid = fields.Char(
        string='Partner Profile UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner Entity',
        required=True,
        ondelete='cascade',
        index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        required=True,
        index=True
    )
    account_type = fields.Selection(
        [
            ('agency', 'Creative Agency / Studio'),
            ('individual', 'Individual Creative Professional')
        ],
        string='Account Type',
        required=True,
        default='agency',
        index=True
    )
    verification_status = fields.Selection(
        [
            ('pending', 'Pending Verification'),
            ('verified', 'Verified Partner'),
            ('featured', 'Featured Partner'),
            ('suspended', 'Suspended')
        ],
        string='Verification Status',
        required=True,
        default='pending',
        tracking=True,
        index=True
    )
    target_market = fields.Selection(
        [
            ('corporate', 'Corporate / Enterprise Clients'),
            ('individual', 'SMB / Individual Clients'),
            ('both', 'Both Corporate & SMB')
        ],
        string='Target Market',
        required=True,
        default='both',
        index=True
    )
    expertise_ids = fields.Many2many(
        'vin.partner.expertise',
        'vin_partner_expertise_rel',
        'profile_id',
        'expertise_id',
        string='Core Disciplines & Skills'
    )
    availability_state = fields.Selection(
        [
            ('available', 'Immediately Available'),
            ('busy', 'Currently Busy / Queue Full'),
            ('unavailable', 'Unavailable')
        ],
        string='Availability State',
        required=True,
        default='available',
        tracking=True,
        index=True,
        help="Hard eligibility constraint evaluated during talent matching."
    )
    internal_trust_score = fields.Float(
        string='Internal Trust Score (0.00-100.00)',
        digits=(5, 2),
        default=85.00,
        readonly=True,
        help="CONFIDENTIAL: Internal trust metric derived from dispute history, SLA performance, and compliance signals. Never exposed publicly."
    )
    public_rating = fields.Float(
        string='Public Star Rating (1.00-5.00)',
        digits=(3, 2),
        default=5.00,
        readonly=True,
        index=True
    )
    completed_projects_count = fields.Integer(
        string='Completed Projects Count',
        default=0,
        readonly=True
    )
    on_time_delivery_rate = fields.Float(
        string='On-Time Delivery Rate (%)',
        digits=(5, 2),
        default=100.00,
        readonly=True
    )
    response_sla_compliance_rate = fields.Float(
        string='Response SLA Compliance Rate (%)',
        digits=(5, 2),
        default=100.00,
        readonly=True
    )
    portfolio_item_ids = fields.One2many(
        'vin.portfolio.item',
        'partner_profile_id',
        string='Portfolio Showcases'
    )

    _sql_constraints = [
        ('partner_unique', 'unique(partner_id)', 'A res.partner can only have one Creative Partner Profile!'),
        ('profile_uuid_unique', 'unique(uuid)', 'Profile UUID must be unique!')
    ]

    def action_verify_partner(self):
        """Marks partner as verified following successful KYC/KYB and portfolio screening."""
        for record in self:
            record.write({'verification_status': 'verified'})
            self.env['vin.audit.event'].sudo().record_event(
                action='PARTNER_VERIFIED',
                subject_type='creative.partner.profile',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={'account_type': record.account_type, 'status': 'verified'}
            )

    def action_suspend_partner(self, reason="Policy Violation"):
        for record in self:
            record.write({'verification_status': 'suspended'})
            self.env['vin.audit.event'].sudo().record_event(
                action='PARTNER_SUSPENDED',
                subject_type='creative.partner.profile',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={'reason': reason}
            )
