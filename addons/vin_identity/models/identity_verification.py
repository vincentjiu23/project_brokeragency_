# -*- coding: utf-8 -*-
import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class VinIdentityVerification(models.Model):
    _name = 'vin.identity.verification'
    _description = 'VIN Sensitive Identity Verification (KYC/KYB)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    uuid = fields.Char(
        string='Verification Case UUID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False
    )
    user_id = fields.Many2one(
        'res.users',
        string='Applicant User',
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
    verification_level = fields.Selection(
        [
            ('tier_0_unverified', 'Tier 0: Unverified'),
            ('tier_1_individual_kyc', 'Tier 1: Individual Creator (KTP/Passport)'),
            ('tier_2_corporate_kyb', 'Tier 2: Enterprise/Agency (NIB/NPWP/Deed)'),
            ('tier_3_accredited', 'Tier 3: Formally Accredited Entity')
        ],
        string='Verification Tier',
        required=True,
        default='tier_0_unverified',
        index=True
    )
    status = fields.Selection(
        [
            ('pending', 'Pending Submission'),
            ('in_review', 'Under Compliance Review'),
            ('verified', 'Verified & Approved'),
            ('rejected', 'Rejected'),
            ('expired', 'Expired (Requires Re-Verification)')
        ],
        string='Verification Status',
        required=True,
        default='pending',
        tracking=True,
        index=True
    )
    id_document_type = fields.Selection(
        [
            ('ktp', 'KTP (Indonesian National Identity)'),
            ('passport', 'International Passport'),
            ('npwp', 'NPWP (Tax Registration)'),
            ('nib_oss', 'NIB / OSS Business License'),
            ('company_deed', 'Corporate Deed of Establishment (Akta Notaris)')
        ],
        string='Identity Document Type',
        required=True
    )
    evidence_vault_ref = fields.Char(
        string='Asset Vault Evidence Reference (SHA-256)',
        required=True,
        help="Opaque SHA-256 content-addressable reference to encrypted Asset Vault evidence."
    )
    reviewed_by_id = fields.Many2one(
        'res.users',
        string='Reviewing Officer',
        readonly=True
    )
    verified_at = fields.Datetime(
        string='Verified Timestamp (UTC)',
        readonly=True
    )
    rejection_reason = fields.Text(
        string='Rejection Justification',
        tracking=True
    )

    def action_approve_verification(self):
        """Approves the KYC/KYB application with Segregation of Duties."""
        for record in self:
            current_user = self.env.user
            if record.user_id.id == current_user.id:
                raise UserError(_("Segregation of Duties Violation: You cannot approve your own identity verification!"))

            record.write({
                'status': 'verified',
                'reviewed_by_id': current_user.id,
                'verified_at': fields.Datetime.now(),
                'rejection_reason': False
            })

            # Append audit event
            self.env['vin.audit.event'].sudo().record_event(
                action='IDENTITY_VERIFIED',
                subject_type='vin.identity.verification',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'applicant_id': str(record.user_id.id),
                    'tier': record.verification_level,
                    'reviewer_id': str(current_user.id)
                }
            )

    def action_reject_verification(self, reason):
        """Rejects the verification case with mandatory reason."""
        for record in self:
            if not reason:
                raise UserError(_("Rejection requires an explicit justification for the applicant."))
            record.write({
                'status': 'rejected',
                'reviewed_by_id': self.env.user.id,
                'rejection_reason': reason
            })
            self.env['vin.audit.event'].sudo().record_event(
                action='IDENTITY_REJECTED',
                subject_type='vin.identity.verification',
                subject_id=record.uuid,
                tenant_id=record.tenant_id.uuid,
                payload={
                    'applicant_id': str(record.user_id.id),
                    'reason': reason
                }
            )
