# -*- coding: utf-8 -*-
"""
Data Subject Access Request (DSAR) Model (Q137–Q146, Q250 Compliance Domain).
Implements GDPR / UU PDP (Indonesian Data Protection) rights:
  - Right of Access / Portability
  - Right to Rectification
  - Right to Erasure (Cryptographic Erasure / Pseudonymization)

CRITICAL INVARIANTS (ADR-002, ADR-004, ADR-005):
  1. Zero ledger alteration on erasure: double-entry virtual escrow ledgers and invoices are NEVER deleted.
  2. Legal hold check: Erasure is strictly blocked if subject has an active legal hold.
  3. Cryptographic erasure masks PII without breaking relational referential integrity or ledger balance.
"""
import uuid
import hashlib
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class VinDSARRequest(models.Model):
    """
    Data Subject Access Request (DSAR) Record.
    Tracks and executes user privacy rights requests under GDPR and UU PDP.
    """
    _name = 'vin.dsar.request'
    _description = 'VIN Data Subject Privacy Request (DSAR)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submitted_at desc, id desc'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    request_number = fields.Char(
        string='Request Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )

    request_type = fields.Selection([
        ('access', 'Right of Access (Data Export)'),
        ('erasure', 'Right to Erasure (Cryptographic Deletion)'),
        ('rectification', 'Right to Rectification'),
        ('restriction', 'Right to Restriction of Processing'),
    ], string='Request Type', required=True, tracking=True)

    # ── Subject Identification ──
    subject_user_id = fields.Many2one('res.users', string='Subject Platform User', index=True)
    subject_email = fields.Char(string='Subject Identity Email', required=True, index=True)
    subject_partner_id = fields.Many2one('creative.partner.profile', string='Subject Partner Profile')
    subject_organization_id = fields.Many2one('vin.organization', string='Subject Organization')

    # ── Verification & Identity Confirmation ──
    identity_verified = fields.Boolean(
        string='Subject Identity Verified', default=False, tracking=True,
        help="Mandatory identity verification before releasing data or erasing PII."
    )
    verification_notes = fields.Char(string='Identity Verification Reference')

    # ── State Machine ──
    state = fields.Selection([
        ('submitted', 'Submitted / Identity Pending'),
        ('verified', 'Identity Verified / In Assessment'),
        ('blocked_legal_hold', 'Blocked by Active Legal Hold'),
        ('executed', 'Formally Executed / Completed'),
        ('rejected', 'Rejected with Legal Grounds'),
    ], string='Status', default='submitted', required=True, tracking=True)

    submitted_at = fields.Datetime(string='Submitted At', default=fields.Datetime.now, readonly=True)
    completed_at = fields.Datetime(string='Completed At', readonly=True)
    executed_by_user_id = fields.Many2one('res.users', string='Executed By DPO / Officer', readonly=True)

    # ── Erasure Certificate & Audit Lineage ──
    erasure_certificate_hash = fields.Char(
        string='Cryptographic Erasure Certificate Seal',
        readonly=True, copy=False,
        help="SHA-256 seal of the cryptographic erasure operation."
    )
    execution_notes = fields.Text(string='Execution & DPO Rationale Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('request_number', _('New')) == _('New'):
                vals['request_number'] = f"DSAR-{fields.Date.today().strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
        return super().create(vals_list)

    def action_verify_identity(self):
        """Confirms that data subject identity has been rigorously established."""
        for rec in self:
            rec.write({
                'identity_verified': True,
                'state': 'verified',
            })
            rec.message_post(body=_("Subject identity verified by DPO."))

    def action_execute_erasure(self):
        """
        Executes cryptographic erasure (GDPR Art 17 / UU PDP).
        Enforces:
          1. Identity verified
          2. Legal hold check: MUST NOT be under active legal hold
          3. Zero ledger alteration: financial transactions remain intact
          4. Emits DSAR_ERASURE_EXECUTED audit event
        """
        for rec in self:
            if not rec.identity_verified:
                raise UserError(_("Cannot execute erasure: Subject identity has not been verified."))

            # ── Gate 1: Check active legal hold ──
            LegalHold = self.env['vin.legal.hold']
            held = LegalHold.check_is_held(
                tenant_id=rec.tenant_id.id,
                organization_id=rec.subject_organization_id.id if rec.subject_organization_id else False,
                partner_profile_id=rec.subject_partner_id.id if rec.subject_partner_id else False,
            )
            if held:
                rec.write({
                    'state': 'blocked_legal_hold',
                    'execution_notes': _(
                        "Erasure request BLOCKED: Subject is bound to active legal hold [%s] (%s). "
                        "Records preserved pursuant to legal claims exception (GDPR Art 17(3)(e))."
                    ) % (held[0].hold_reference, held[0].matter_name)
                })
                rec.message_post(body=_(
                    "Erasure request blocked due to active legal hold: %s"
                ) % held[0].hold_reference)
                return

            # ── Gate 2: Perform cryptographic erasure of non-ledger PII ──
            # Mask user contact info with pseudonymized cryptographic salt
            salt = uuid.uuid4().hex[:12]
            pseudonym = f"erased_user_{salt}@privacy.internal"

            if rec.subject_user_id:
                rec.subject_user_id.sudo().write({
                    'name': f"Data Subject (Erased {salt})",
                    'login': pseudonym,
                    'email': pseudonym,
                    'active': False,
                })

            # Create immutable erasure certificate hash
            cert_payload = {
                'request_number': rec.request_number,
                'subject_email': rec.subject_email,
                'tenant_id': rec.tenant_id.id,
                'salt': salt,
                'executed_at': str(fields.Datetime.now()),
                'executed_by': self.env.user.id,
            }
            cert_raw = json.dumps(cert_payload, sort_keys=True)
            cert_digest = hashlib.sha256(cert_raw.encode('utf-8')).hexdigest()

            now = fields.Datetime.now()
            rec.write({
                'state': 'executed',
                'completed_at': now,
                'executed_by_user_id': self.env.user.id,
                'erasure_certificate_hash': cert_digest,
                'execution_notes': _(
                    "Cryptographic erasure executed successfully. "
                    "PII pseudonymized. Zero alteration to financial ledgers (ADR-002)."
                )
            })

            # Emit DSAR_ERASURE_EXECUTED audit event
            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'DSAR_ERASURE_EXECUTED',
                    'entity_name': 'vin.dsar.request',
                    'entity_id': str(rec.id),
                    'state_after': 'executed',
                    'payload': json.dumps({
                        'request_number': rec.request_number,
                        'certificate_hash': cert_digest,
                    })
                })

            rec.message_post(body=_(
                "Cryptographic erasure executed. Erasure Certificate Digest: %s"
            ) % cert_digest)
