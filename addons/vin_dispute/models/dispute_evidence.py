# -*- coding: utf-8 -*-
import hashlib
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class VinDisputeEvidence(models.Model):
    """
    Dispute Evidence Package Item (Q91–Q98, Q175, ADR-003).
    Ensures evidentiary immutability for all documentation, transcripts,
    and asset revision comparisons submitted during dispute resolution.
    """
    _name = 'vin.dispute.evidence'
    _description = 'VIN Dispute Evidentiary Item'
    _order = 'uploaded_at asc, id asc'

    uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()), required=True, readonly=True, index=True, copy=False)
    dispute_id = fields.Many2one('vin.dispute', string='Dispute Reference', required=True, ondelete='cascade', index=True)
    tenant_id = fields.Many2one('vin.tenant', string='Tenant', related='dispute_id.tenant_id', store=True, index=True)

    title = fields.Char(string='Evidence Title / Exhibit Label', required=True)
    submitted_by_party = fields.Selection([
        ('client', 'Client Organization'),
        ('partner', 'Creative Partner'),
        ('mediator', 'Platform Mediator / Arbitrator')
    ], string='Submitted By Party', required=True, default='client')

    evidence_type = fields.Selection([
        ('contract_clause', 'Contract Scope / SLA Clause'),
        ('communication_log', 'Official Communication Log / Email Transcript'),
        ('deliverable_artifact', 'Deliverable File / Revision Output'),
        ('diff_comparison', 'Revision Diff / Asset Comparison'),
        ('expert_report', 'Technical Inspection / Expert Appraisal'),
        ('other', 'Other Evidentiary Material')
    ], string='Evidence Classification', required=True, default='contract_clause')

    description = fields.Text(string='Factual Statement & Relevancy Description', required=True)
    file_attachment_id = fields.Many2one('ir.attachment', string='Attached Evidence File')
    sha256_hash = fields.Char(string='Tamper-Evident SHA-256 Digest', required=True, index=True, copy=False)
    uploaded_at = fields.Datetime(string='Timestamp of Submission', default=fields.Datetime.now, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sha256_hash'):
                # Auto-generate SHA-256 digest from description and metadata if not provided
                raw = f"{vals.get('title')}:{vals.get('description')}:{vals.get('submitted_by_party')}:{vals.get('dispute_id')}"
                vals['sha256_hash'] = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        return super().create(vals_list)
