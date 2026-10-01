# `vin_execution` Module — Workstream DAG, Milestones & Deliverables

## Overview
The `vin_execution` module implements the operational DAG (Directed Acyclic Graph) of projects, structured milestone sequential gating, task dependencies, immutable deliverable submissions, client acceptance sign-offs, and revision request caps.

## Models
*   `vin.workstream`: Directed Acyclic Graph (DAG) node with cycle-detection constraint (`_check_dag_acyclic`).
*   `vin.milestone`: Sequenced execution milestone with prerequisite gating and AC-05 acceptance hooks.
*   `vin.task`: Operational vs. Contractual task classification with prerequisite task resolution and audit notification (`TASK_DEPENDENCY_RESOLVED`).
*   `vin.deliverable`: Milestone deliverable specification and objective quality acceptance gates.
*   `vin.deliverable.submission`: Append-only, immutable deliverable release version linked to Content-Addressable Asset Vault SHA-256 digests.
*   `vin.deliverable.acceptance`: Formal client sign-off records triggering milestone acceptance and escrow release readiness.
*   `vin.deliverable.revision`: Structured critique feedback capped at maximum allowable revisions before requiring a formal Change Request (`CR_VN`).

## Controllers (REST API)
*   `POST /api/v1/deliverables/{id}/submissions`: Submits immutable deliverable release version.
*   `POST /api/v1/deliverables/{id}/acceptance`: Client formal acceptance sign-off.

## Invariants & Locked Decisions
*   **Acyclic DAG Validation:** Workstreams and prerequisite milestones enforce strict acyclic graph integrity.
*   **Submission Immutability (ADR-003):** Deliverable submissions are permanent legal evidence and cannot be updated or deleted.
*   **AC-05 (Milestone Acceptance Trigger):** When all deliverables of a milestone are accepted, the milestone transitions to `accepted` and emits `MILESTONE_ACCEPTED`.
*   **Structured Revision Cap:** Limits iterative reviews to 2 rounds; subsequent modifications mandate a Change Request (`CR_VN`).
