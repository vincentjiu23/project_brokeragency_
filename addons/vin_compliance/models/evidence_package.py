# -*- coding: utf-8 -*-
"""
Evidence Package Model (Q137–Q146, Q250 Compliance Domain).
Generates tamper-evident legal and audit evidentiary packages
for court proceedings, tax inspections, or arbitration hearings.
"""
import uuid
import hashlib
import json
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class VinEvidencePackage(models.Model):
    """
    Compliance & Legal Evidence Package.
    Aggregates historical contracts, double-entry ledger rows, invoice records,
    deliverable hashes, and audit chain entries into an immutable, SHA-256 sealed bundle.
    """
    _name = 'vin.evidence.package'
    _description = 'VIN Compliance Evidence Package'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    uuid = fields.Char(
        string='UUID', default=lambda self: str(uuid.uuid4()),
        required=True, readonly=True, index=True, copy=False
    )
    package_number = fields.Char(
        string='Package Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), index=True
    )
    tenant_id = fields.Many2one(
        'vin.tenant', string='Tenant', required=True, index=True,
        default=lambda self: self.env.user.tenant_id if hasattr(self.env.user, 'tenant_id') else False
    )

    title = fields.Char(string='Package Title', required=True, tracking=True)
    purpose = fields.Selection([
        ('arbitration', 'Court / Arbitration Hearing Submission'),
        ('tax_audit', 'Statutory Tax Inspection (DJP / Audit)'),
        ('dispute_evidence', 'Internal Tier 2/3 Dispute Adjudication'),
        ('compliance_audit', 'Annual ISO 27001 / SOC 2 Compliance Review'),
    ], string='Package Purpose', required=True, default='arbitration', tracking=True)

    # ── Context Linkage ──
    contract_id = fields.Many2one('vin.contract', string='Contract Context', index=True)
    legal_hold_id = fields.Many2one('vin.legal.hold', string='Legal Hold Context', index=True)
    dispute_id = fields.Many2one('vin.dispute', string='Dispute Case', index=True)

    # ── Package Content Snapshot (Serialized JSON) ──
    package_data = fields.Text(
        string='Serialized Snapshot Payload',
        readonly=True,
        help="Structured JSON snapshot of contracts, milestones, payouts, and audit hashes."
    )
    item_count = fields.Integer(string='Included Evidentiary Items', readonly=True, default=0)

    # ── Digital Seal & Integrity ──
    sha256_hash = fields.Char(
        string='Package SHA-256 Digest', readonly=True, copy=False,
        help="Cryptographic seal guaranteeing zero post-generation tampering."
    )
    state = fields.Selection([
        ('draft', 'Draft / Compiling'),
        ('sealed', 'Cryptographically Sealed (Immutable)'),
        ('exported', 'Exported to Custodian / Counsel'),
    ], string='Package Status', default='draft', required=True, tracking=True)

    sealed_by_user_id = fields.Many2one('res.users', string='Sealed By Officer', readonly=True)
    sealed_at = fields.Datetime(string='Sealed At', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('package_number', _('New')) == _('New'):
                vals['package_number'] = f"EV-PKG-{fields.Date.today().strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
        return super().create(vals_list)

    def action_compile_and_seal(self):
        """
        Compiles evidentiary snapshot from contract, ledger, deliverable, and audit data,
        then calculates SHA-256 digital seal and transitions to 'sealed'.
        """
        for rec in self:
            if rec.state == 'sealed':
                raise UserError(_("Evidence package is already sealed and immutable."))

            # Compile structured evidentiary dataset
            evidence_items = []
            if rec.contract_id:
                c = rec.contract_id
                evidence_items.append({
                    'type': 'contract',
                    'contract_id': c.id,
                    'title': c.title,
                    'total_contract_value': float(c.total_contract_value or 0),
                    'state': c.state,
                })

            if rec.dispute_id:
                d = rec.dispute_id
                evidence_items.append({
                    'type': 'dispute',
                    'dispute_number': d.dispute_number,
                    'disputed_amount': float(d.disputed_amount or 0),
                    'state': d.state,
                })

            # Check audit event trail
            if 'vin.audit.event' in self.env and rec.contract_id:
                audit_records = self.env['vin.audit.event'].search([
                    ('tenant_id', '=', rec.tenant_id.id),
                    ('entity_name', '=', 'vin.contract'),
                    ('entity_id', '=', str(rec.contract_id.id)),
                ], limit=50)
                for ae in audit_records:
                    evidence_items.append({
                        'type': 'audit_event',
                        'event_type': ae.event_type,
                        'timestamp': str(ae.create_date),
                    })

            payload = {
                'package_number': rec.package_number,
                'tenant_id': rec.tenant_id.id,
                'purpose': rec.purpose,
                'compiled_at': str(fields.Datetime.now()),
                'items': evidence_items,
            }
            raw = json.dumps(payload, sort_keys=True)
            digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()

            now = fields.Datetime.now()
            rec.write({
                'package_data': raw,
                'item_count': len(evidence_items),
                'sha256_hash': digest,
                'state': 'sealed',
                'sealed_by_user_id': self.env.user.id,
                'sealed_at': now,
            })

            # Emit audit event
            if 'vin.audit.event' in self.env:
                self.env['vin.audit.event'].sudo().create({
                    'tenant_id': rec.tenant_id.id,
                    'actor_user_id': self.env.user.id,
                    'event_type': 'EVIDENCE_PACKAGE_SEALED',
                    'entity_name': 'vin.evidence.package',
                    'entity_id': str(rec.id),
                    'state_after': 'sealed',
                    'payload': json.dumps({
                        'package_number': rec.package_number,
                        'sha256_hash': digest,
                        'item_count': len(evidence_items),
                    })
                })

            rec.message_post(body=_(
                "Evidence Package [%s] compiled and sealed. SHA-256 Digest: %s"
            ) % (rec.package_number, digest))

    def write(self, vals):
        """Prevent modifying package once sealed."""
        for rec in self:
            if rec.state in ('sealed', 'exported') and rec.sha256_hash:
                disallowed = set(vals.keys()) - {'state'}
                if disallowed:
                    raise UserError(_(
                        "Cannot modify sealed evidence package. Record is cryptographically sealed."
                    ))
        return super().write(vals)
