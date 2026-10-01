# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinOpportunityRecord(models.Model):
    _name = 'vin.opportunity.record'
    _description = 'VIN Project Engagement Opportunity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'dispatched_at desc'

    uuid = fields.Char(
        string='Opportunity UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    brief_id = fields.Many2one(
        'vin.project.brief',
        string='Project Brief Version',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='brief_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    partner_profile_id = fields.Many2one(
        'creative.partner.profile',
        string='Creative Partner Candidate',
        required=True,
        readonly=True,
        index=True
    )
    state = fields.Selection(
        [
            ('dispatched', 'Dispatched / Awaiting Response'),
            ('accepted', 'Accepted (Bilateral Interest)'),
            ('declined', 'Declined by Partner'),
            ('expired', 'SLA Expired')
        ],
        string='Opportunity State',
        required=True,
        default='dispatched',
        tracking=True,
        index=True
    )
    dispatched_at = fields.Datetime(
        string='Dispatched Timestamp',
        default=fields.Datetime.now,
        readonly=True,
        required=True
    )
    expires_at = fields.Datetime(
        string='Response SLA Deadline',
        readonly=True,
        required=True
    )
    responded_at = fields.Datetime(
        string='Response Timestamp',
        readonly=True
    )
    response_note = fields.Text(
        string='Response Note / Pitch'
    )
    client_disclosed = fields.Boolean(
        string='Client Identity Disclosed',
        default=False,
        readonly=True,
        help="Locked Architecture Rule: True only after partner accepts opportunity."
    )
    blind_scope_summary = fields.Text(
        string='Blind Project Scope Preview',
        readonly=True,
        help="Sanitized brief scope without client identifying credentials."
    )

    def action_accept(self, response_note=None):
        """Partner accepts engagement opportunity, revealing client identity and starting SLA."""
        for record in self:
            if record.state != 'dispatched':
                raise UserError(_("Cannot accept opportunity: state is '%s'.") % record.state)
            
            # Check SLA expiration
            if record.expires_at and fields.Datetime.now() > record.expires_at:
                record.write({'state': 'expired'})
                raise UserError(_("Opportunity response SLA has expired!"))

            record.write({
                'state': 'accepted',
                'responded_at': fields.Datetime.now(),
                'response_note': response_note or record.response_note,
                'client_disclosed': True
            })

            # Record CONTACT_INITIATED audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='CONTACT_INITIATED',
                subject_type='vin.opportunity.record',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'brief_uuid': record.brief_id.uuid,
                    'partner_profile_uuid': record.partner_profile_id.uuid,
                    'state': 'accepted',
                    'client_disclosed': True
                }
            )

        return True

    def action_decline(self, reason=None):
        """Partner declines engagement opportunity."""
        for record in self:
            if record.state != 'dispatched':
                raise UserError(_("Cannot decline opportunity: state is '%s'.") % record.state)

            record.write({
                'state': 'declined',
                'responded_at': fields.Datetime.now(),
                'response_note': reason or record.response_note
            })
        return True

    def check_sla_expiry(self):
        """Scheduled action to expire opportunities that passed response SLA deadline."""
        now = fields.Datetime.now()
        expired_opps = self.search([
            ('state', '=', 'dispatched'),
            ('expires_at', '<', now)
        ])
        for opp in expired_opps:
            opp.write({'state': 'expired'})
