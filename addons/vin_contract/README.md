# `vin_contract` Module — Immutable Contracts, Proposals & Change Requests

## Overview
The `vin_contract` module governs the complete contractual lifecycle within the VIN Project, implementing immutable versioned contracts (`CONTRACT_VN`), structured bilateral proposals (`PROPOSAL_VN`), Segregation of Duties approval matrices, and version-spawning Change Requests (`CR_VN`).

## Models
*   `vin.contract`: Canonical legal contract entity (`CONTRACT_VN`) supporting SHA-256 seal hashes, multi-tier approvals, electronic signing, and strict post-activation immutability.
*   `vin.contract.proposal`: Structured bilateral proposals and counter-proposals with JSON delta snapshots.
*   `vin.contract.approval`: Multi-tier approval matrix enforcing Segregation of Duties (Four-Eyes Principle).
*   `vin.contract.change.request`: Formal Change Requests (`CR_VN`) that spawn subsequent immutable contract versions (`version_no + 1`).

## Controllers (REST API)
*   `POST /api/v1/contracts/{id}/proposals`: Submits structured contract proposal.
*   `POST /api/v1/change-requests`: Submits versioned Change Request.

## Invariants & Locked Decisions
*   **Contract Immutability (ADR-003 / Q41-Q60):** Active and completed contracts are strictly append-only. Direct modification of commercial or deadline fields is blocked.
*   **Four-Eyes Principle (ADR-005):** Contract authors/creators cannot approve any approval tier of their own contracts.
*   **Approval Invalidation on Material Delta (AC-03):** Submitting a proposal with material budget or timeline deltas automatically invalidates affected prior approvals and reverts contract to review state.
*   **Additive Version Spawning:** Executing an approved Change Request preserves the historical contract version as `amended` and spawns a new active contract version.
