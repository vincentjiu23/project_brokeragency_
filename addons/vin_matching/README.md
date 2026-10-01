# `vin_matching` Module — Discovery & Recommendation Engine

## Overview
The `vin_matching` module implements deterministic candidate matching, project brief versioning, hard eligibility verification, match snapshot preservation, and blind RFQ opportunity dispatching for the VIN Project.

## Models
*   `vin.project.brief`: Versioned Project Brief / RFQ entity (`BRIEF_VN`) supporting canonical SHA-256 hash sealing, budget constraints, target partner account tiers, and blind anonymity mode.
*   `vin.match.snapshot`: Immutable historical audit snapshot of a matching run for a given brief version.
*   `vin.match.candidate`: Individual evaluated candidate line item recording overall score, expertise fit, reputation, and hard eligibility pass/fail status.
*   `vin.opportunity.record`: Dispatched opportunity with response SLA deadline tracking, blind project preview, and bilateral disclosure upon acceptance.

## Services
*   `MatchingEngineService`: Evaluates deterministic hard eligibility gates (verification status, availability, account type compatibility) and calculates multi-factor ranking scores.
*   `OpportunityDispatchService`: Dispatches opportunities to top-ranked candidates, starts response SLA timers, and generates sanitized blind RFQ previews.

## Controllers (REST API)
*   `GET /api/v1/projects/{brief_uuid}/matches`: Retrieves frozen candidate match snapshot and scores for a project brief.
*   `POST /api/v1/opportunities/{opportunity_uuid}/respond`: Allows partners to accept or decline engagement opportunities.

## Critical Invariants & Rules
*   **Hard Eligibility Rule (AC-01 & Locked Decision Q26-Q40):** Unverified, suspended, or incompatible candidates are strictly excluded from match snapshots.
*   **No Pay-to-Win:** Paid subscription tiers **cannot** bypass or override hard eligibility gates.
*   **Snapshot Immutability (ADR-003):** `vin.match.snapshot` records are append-only; update (`write`) and delete (`unlink`) are strictly blocked.
*   **Blind Introduction (AC-02):** In blind mode, client identity remains undisclosed until the partner explicitly accepts the engagement opportunity.
*   **Audit Lineage:** Automatically emits immutable audit events: `BRIEF_CREATED`, `MATCH_SNAPSHOT_CREATED`, `CONTACT_INITIATED`.
