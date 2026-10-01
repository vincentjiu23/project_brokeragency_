# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinDeliverableSubmission(models.Model):
    _name = 'vin.deliverable.submission'
    _description = 'VIN Immutable Deliverable Submission Version'
    _order = 'version_no desc, create_date desc'

    uuid = fields.Char(
        string='Submission UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    deliverable_id = fields.Many2one(
        'vin.deliverable',
        string='Deliverable',
        required=True,
        readonly=True,
        index=True,
        ondelete='cascade'
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='deliverable_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    version_no = fields.Integer(
        string='Submission Version',
        required=True,
        readonly=True,
        default=1,
        index=True
    )
    asset_vault_ref = fields.Char(
        string='Asset Vault SHA-256 Digest',
        size=64,
        required=True,
        readonly=True,
        index=True,
        help="Content-addressable SHA-256 hash of deliverable archive stored in Asset Vault."
    )
    asset_object_id = fields.Char(
        string='Asset Vault Object UUID',
        required=True,
        readonly=True
    )
    submission_notes = fields.Text(
        string='Submission Notes & Release Summary',
        readonly=True
    )
    submitted_by = fields.Many2one(
        'res.users',
        string='Submitted By',
        readonly=True,
        default=lambda self: self.env.user
    )
    submitted_at = fields.Datetime(
        string='Submitted Timestamp',
        readonly=True,
        default=fields.Datetime.now
    )
    state = fields.Selection(
        [
            ('submitted', 'Submitted for Review'),
            ('accepted', 'Accepted by Client'),
            ('revision_requested', 'Revision Requested'),
            ('superseded', 'Superseded by Newer Revision'),
            ('disputed', 'Disputed')
        ],
        string='Submission State',
        required=True,
        default='submitted',
        index=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Creates immutable submission, updates deliverable state, and records audit event."""
        submissions = super().create(vals_list)
        for sub in submissions:
            deliverable = sub.deliverable_id
            # Set version number
            prior_count = self.search_count([('deliverable_id', '=', deliverable.id), ('id', '!=', sub.id)])
            sub.version_no = prior_count + 1

            # Update deliverable pointer & state
            deliverable.write({
                'latest_submission_id': sub.id,
                'state': 'submitted'
            })

            # Check if milestone can transition to submitted/in_review
            milestone = deliverable.milestone_id
            if milestone.state == 'active':
                milestone.write({'state': 'in_review'})

            # Emit DELIVERABLE_SUBMITTED audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='DELIVERABLE_SUBMITTED',
                subject_type='vin.deliverable.submission',
                subject_id=sub.uuid,
                tenant_id=sub.tenant_id.uuid,
                payload={
                    'deliverable_uuid': deliverable.uuid,
                    'milestone_uuid': milestone.uuid,
                    'version_no': sub.version_no,
                    'asset_vault_ref': sub.asset_vault_ref,
                    'asset_object_id': sub.asset_object_id
                }
            )
        return submissions

    def write(self, vals):
        """
        Locked Architecture Invariant (ADR-003):
        Deliverable submissions are append-only. Only 'state' can be updated by review workflows.
        Asset hashes and version metadata are immutable.
        """
        forbidden_fields = {'asset_vault_ref', 'asset_object_id', 'version_no', 'deliverable_id', 'tenant_id'}
        if any(f in vals for f in forbidden_fields):
            raise UserError(_("Locked Architecture Invariant: Deliverable submission evidence is immutable!"))
        return super().write(vals)

    def unlink(self):
        """Submissions are permanent legal audit artifacts and cannot be deleted."""
        raise UserError(_("Security Violation: Deliverable submissions are immutable and cannot be deleted!"))
