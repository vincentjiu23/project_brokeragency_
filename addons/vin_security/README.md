# `vin_security` Module

## Overview
The `vin_security` module enforces the platform security baseline, including PostgreSQL Row-Level Security (RLS), Segregation of Duties (SoD) / Four-Eyes principle, and immutable cross-tenant auditing.

## Models
*   `vin.cross.tenant.access.log`: Append-only audit trail logging all cross-tenant access and verified contractual bridges.
*   `vin.governance.override`: Controlled human override workflow enforcing Four-Eyes approvals, official legal evidence attachment, time-bounds, and rollback instructions.

## Non-Negotiable Invariants
*   **Four-Eyes Enforcement:** The requester of a sensitive ledger, legal, or security change is strictly forbidden from approving it.
*   **Immutable Cross-Tenant Audit:** Any query traversing tenant boundaries requires an explicit `CONTRACT_VN` bridge reference and is logged immutably.
