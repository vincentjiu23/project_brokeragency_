# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class VinDeliverableAcceptance(models.Model):
    _name = 'vin.deliverable.acceptance'
    _description = 'VIN Formal Deliverable Acceptance Sign-Off'
    _order = 'accepted_at desc'

    uuid = fields.Char(
        string='Acceptance UUID',
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
        index=True
    )
    submission_id = fields.Many2one(
        'vin.deliverable.submission',
        string='Accepted Submission Version',
        required=True,
        readonly=True,
        index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='deliverable_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    accepted_by = fields.Many2one(
        'res.users',
        string='Accepted By Client Signatory',
        required=True,
        readonly=True,
        default=lambda self: self.env.user
    )
    accepted_at = fields.Datetime(
        string='Acceptance Timestamp',
        required=True,
        readonly=True,
        default=fields.Datetime.now
    )
    acceptance_notes = fields.Text(
        string='Sign-Off Notes'
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for acc in records:
            submission = acc.submission_id
            deliverable = acc.deliverable_id

            if submission.state not in ('submitted', 'under_review'):
                raise UserError(_("Cannot accept submission in state '%s'.") % submission.state)

            submission.write({'state': 'accepted'})
            deliverable.write({'state': 'accepted'})

            # Check if all deliverables in milestone are accepted
            milestone = deliverable.milestone_id
            if all(d.state == 'accepted' for d in milestone.deliverable_ids):
                milestone.action_accept_milestone()

        return records


class VinDeliverableRevision(models.Model):
    _name = 'vin.deliverable.revision'
    _description = 'VIN Structured Deliverable Revision Request'
    _order = 'requested_at desc'

    uuid = fields.Char(
        string='Revision Request UUID',
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
        index=True
    )
    submission_id = fields.Many2one(
        'vin.deliverable.submission',
        string='Target Submission Version',
        required=True,
        readonly=True,
        index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant',
        string='Tenant',
        related='deliverable_id.tenant_id',
        store=True,
        readonly=True,
        index=True
    )
    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        required=True,
        readonly=True,
        default=lambda self: self.env.user
    )
    requested_at = fields.Datetime(
        string='Requested Timestamp',
        required=True,
        readonly=True,
        default=fields.Datetime.now
    )
    critique_feedback = fields.Text(
        string='Structured Creative Feedback & Required Revisions',
        required=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rev in records:
            deliverable = rev.deliverable_id
            submission = rev.submission_id

            # Invariant: Maximum allowable revision cycles before Change Request requirement
            max_revisions = 2
            if deliverable.revision_count >= max_revisions:
                raise UserError(_(
                    "Revision Limit Exceeded: Deliverable has reached maximum allowable revisions (%d). "
                    "Further scope adjustments require a formal Change Request (CR_VN)!"
                ) % max_revisions)

            submission.write({'state': 'revision_requested'})
            deliverable.write({
                'state': 'revision_requested',
                'revision_count': deliverable.revision_count + 1
            })

            # Revert milestone back to active for work
            milestone = deliverable.milestone_id
            if milestone.state in ('submitted', 'in_review'):
                milestone.write({'state': 'active'})

        return records
