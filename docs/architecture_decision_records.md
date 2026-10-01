# Architectural Decision Records (ADRs) — Locked Engineering Decisions

## ADR-001: Progressive Hybrid Architecture
*   **Status:** Locked (Q147)
*   **Context:** The platform requires rock-solid transactional and double-entry accounting integrity while also scaling high-throughput search, asset storage, and event streaming.
*   **Decision:** Retain Odoo + PostgreSQL as the core transactional ERP foundation. Decouple specialized domains into dedicated services (Event Mesh, Asset Vault, Vector Search, AI Gateway, Payment Provider Gateway) through explicit contract interfaces.
*   **Consequences:** Prevents microservice sprawl while keeping business logic and ledger auditability centralized.

## ADR-002: Double-Entry Virtual Escrow Ledger & Floating-Point Ban
*   **Status:** Locked (Q106, Q145)
*   **Context:** Escrow balances cannot be vulnerable to race conditions, silent modifications, or rounding discrepancies.
*   **Decision:** Escrow balances are strictly derived from balanced double-entry virtual ledger entries (`Dr`/`Cr`). All monetary values use Decimal/Odoo Monetary with explicit `currency_id`. Floating point arithmetic is banned across all modules.

## ADR-003: Immutability of Legal and Financial Lineage
*   **Status:** Locked (Q41–Q60, Q145)
*   **Context:** Contracts, proposals, deliverable submissions, and audit events must withstand evidentiary scrutiny.
*   **Decision:** `CONTRACT_VN`, `PROPOSAL_VN`, deliverable submissions, ledger rows, and audit events are strictly append-only. Updates create new version rows (`version_no + parent_version_id`) linked with SHA-256 cryptographic hashes. Physical or logical deletion of these entities is disallowed.

## ADR-004: Server-Side Multi-Tenancy & Row-Level Security (RLS)
*   **Status:** Locked (Q1–Q10, Q121)
*   **Context:** Clients and Partners from different organizations must never access or leak each other's confidential data.
*   **Decision:** Every business entity carries `tenant_id`. PostgreSQL Row-Level Security uses `app.current_tenant_id` session variables. Cross-tenant access is prohibited unless an explicit contractual bridge bound to a valid `CONTRACT_VN` exists, and any cross-tenant query is immutably logged.

## ADR-005: Segregation of Duties (Four-Eyes Principle)
*   **Status:** Locked (Q116, Q144)
*   **Context:** Sensitive operations (financial adjustments, contract overrides, policy changes) pose critical risk.
*   **Decision:** Requesters of sensitive operations can never approve their own requests. Automated enforcement validates that `created_by != approved_by`.
