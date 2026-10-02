# -*- coding: utf-8 -*-
"""
Compliance Governor Service (Q137–Q146, Q250 Compliance Domain).
Orchestrates retention lifecycles, legal hold checks, evidence packaging,
and privacy DSAR cryptographic erasure pipelines.
"""
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ComplianceGovernorService(models.AbstractModel):
    """
    Compliance Governor Service.
    Acts as the authoritative gateway for compliance decisions:
      - Intercepts disposal/purging requests to verify legal holds
      - Coordinates evidence packaging for litigation/arbitration
      - Executes DSAR cryptographic erasure without touching financial ledgers
    """
    _name = 'vin.compliance.governor'
    _description = 'VIN Compliance Governor Service'

    @api.model
    def can_purge_record(self, tenant_id, contract_id=None, project_id=None,
                         organization_id=None, partner_profile_id=None):
        """
        Determines whether records can be purged, archived, or erased.

        Returns:
            tuple: (allowed: bool, blocking_reason: str or None)
        """
        LegalHold = self.env['vin.legal.hold']
        holds = LegalHold.check_is_held(
            tenant_id=tenant_id,
            contract_id=contract_id,
            project_id=project_id,
            organization_id=organization_id,
            partner_profile_id=partner_profile_id,
        )
        if holds:
            blocking = _("Blocked by active legal hold [%s] (%s)") % (
                holds[0].hold_reference, holds[0].matter_name
            )
            return False, blocking

        return True, None

    @api.model
    def build_and_seal_evidence_package(self, tenant_id, title, purpose,
                                       contract_id=None, dispute_id=None, legal_hold_id=None):
        """
        Constructs and cryptographically seals an evidence package.

        Returns:
            vin.evidence.package record
        """
        pkg = self.env['vin.evidence.package'].create({
            'tenant_id': tenant_id,
            'title': title,
            'purpose': purpose,
            'contract_id': contract_id,
            'dispute_id': dispute_id,
            'legal_hold_id': legal_hold_id,
        })
        pkg.action_compile_and_seal()
        return pkg
