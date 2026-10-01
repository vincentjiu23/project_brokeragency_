# VIN PROJECT — Creative Commerce Operating System (`agencybroker`)

> **Platform Version:** v3.3–v3.8 Engineering Baseline  
> **Repository:** `https://github.com/vincentjiu23/project_brokeragency_`  
> **Deployment Target:** Progressive Hybrid Architecture (Odoo 17/18 LTS + PostgreSQL 16 + Specialized Cloud-Native Microservices on Managed Kubernetes)  
> **Architecture Status:** Locked Q1–Q250 Decision Register & Master Engineering Specification

---

## 1. Executive Summary & Operating Model

**VIN Project** is a curated creative-services brokerage and transaction infrastructure platform connecting verified Clients with verified Creative Partners (Agencies and Individual Creators). It is neither an open unvetted job board nor a traditional slow agency intermediary.

*   **Operating Principle:** Client controls planning and acceptance; Platform controls system, regulatory, financial, security, and evidence state; Creative Partner controls execution.
*   **Operating Model:** Full Creative Commerce Operating System spanning **Discovery → Matching → Contracting → Execution DAG → Automated Virtual Escrow → Tax Compliance → IP Transfer → Dispute Arbitration → Reputation Engine → Immutable Archival Vault**.

### The Canonical Relational Spine
```
Master Project (vin.master.project)
  └── Workstream DAG (vin.workstream)
        ├── Contract Lineage (vin.contract / CONTRACT_VN)
        └── Milestone (vin.milestone)
              ├── Task (vin.task)
              ├── Deliverable (vin.deliverable)
              │     └── Submission Lineage (vin.deliverable.submission)
              │           ├── Acceptance / Revision / Dispute
              │           └── Asset-Level IP Assignment (vin.ip.assignment)
              └── Virtual Escrow Allocation (vin.escrow.allocation)
                    └── Payment Event (vin.payment.event) → Double-Entry Virtual Ledger
```

---

## 2. Locked Architecture Decisions (Non-Negotiable)

Based on the locked decision register (Q1–Q250), all development strictly enforces:

1.  **Progressive Hybrid Architecture:** Odoo + PostgreSQL serve as the transactional ERP core and ledger foundation. Specialized independent boundaries handle:
    *   **Search / Vector Engine** (pgvector / Elasticsearch for semantic + structured matching)
    *   **Asset Vault** (Encrypted object store with SHA-256 content addressing, envelope encryption & WORM archive)
    *   **Event Mesh** (Canonical event envelope, idempotent consumption, dead-letter queuing)
    *   **Dispute Engine** (Tiered internal verification + external legal arbitration lock)
    *   **AI Gateway** (Decision support with full prompt/model decision lineage; high-risk actions require mandatory human approval)
    *   **Payment Provider Gateway** (Abstracted multi-provider payment & cross-border payout)
2.  **No Financial Floating-Point Arithmetic:** All money representations use `Decimal` / Odoo `Monetary` with explicit `currency_id`. Floating point arithmetic is prohibited.
3.  **Strict Double-Entry Virtual Escrow Ledger:** Escrow balances are never stored as mutable numbers. Balances are derived from balanced double-entry ledger rows (`Dr` Escrow Cash / `Cr` Escrow Liability, etc.).
4.  **Immutability of Historical Records:** Historical contracts (`CONTRACT_VN`), deliverable submissions, double-entry ledger rows, payment webhooks, audit events (`AUDIT_EVENT`), and legal evidence are append-only and cannot be updated or deleted.
5.  **Multi-Tenancy & Server-Side Tenant Isolation:** Top-level isolation is enforced via `tenant_id` (`vin.tenant`) and PostgreSQL Row-Level Security (`app.current_tenant_id`). Cross-organization interaction requires an explicit contractual bridge bound to a valid `CONTRACT_VN`.
6.  **Separation of Duties (SoD / Four-Eyes Principle):** Users who propose changes to financial ledgers, legal terms, or security configurations are strictly prohibited from approving them.
7.  **No Direct Reliance on UI for Authorization:** All authorization is evaluated server-side across:  
    `Identity → Tenant → Organization → Membership/Role → Project/Workstream Scope → Contractual Authority → Policy Version → Step-Up MFA`.

---

## 3. Monorepo Structure

```
agencybroker/
├── addons/                         # Odoo Custom Addon Modules
│   ├── vin_core/                   # Tenant, Org, Legal Entity, Membership, Master Project
│   ├── vin_identity/               # External IdP mapping, SSO/SCIM, verification state
│   ├── vin_partner/                # Creative Partner Profile, KYC/KYB, portfolio metadata
│   ├── vin_matching/               # Project Brief, Hard Eligibility, Ranking, Shortlists
│   ├── vin_contract/               # Contract_VN, Proposal_VN, Approval Matrix, Change Requests
│   ├── vin_execution/              # Workstream DAG, Milestones, Tasks, Deliverables
│   ├── vin_escrow/                 # Virtual Escrow accounts, allocations, locks, ledger
│   ├── vin_payment/                # Payment provider abstraction, webhooks, payout state machine
│   ├── vin_tax_invoice/            # Tax profiles (PPN/PPh/VAT/WHT), invoices, certificates
│   ├── vin_ip/                     # Asset-level IP assignments, licenses, portfolio display gates
│   ├── vin_dispute/                # Acceptance disputes, objection windows, arbitration cases
│   ├── vin_reputation/             # Public star ratings, SLAs, internal trust score (hidden)
│   ├── vin_subscription/           # Client/Partner tiers, recurring/usage billing, commission rules
│   ├── vin_security/               # RLS policies, step-up MFA, cross-tenant access logs, SoD
│   ├── vin_audit/                  # Tamper-evident hash chain, audit events, WORM linkage
│   ├── vin_integration/           # Resilience gateway, provider adapters, DLQ, replay
│   ├── vin_policy/                 # Policy versioning, effective-date resolution, hard limits
│   └── vin_compliance/             # Data retention, legal hold, GDPR/DSAR, cryptographic erasure
├── services/                       # Specialized Cloud-Native Services
│   ├── event_mesh/                 # Event bus abstraction (Local Odoo + Kafka/RabbitMQ)
│   ├── asset_vault/                # Encrypted object storage adapter & SHA-256 hasher
│   ├── matching_engine/            # Hybrid vector + structured candidate ranker
│   ├── ai_gateway/                 # LLM Gateway with audit lineage & hallucination guards
│   ├── dispute_engine/             # Multi-tier dispute evaluation & evidence packaging
│   └── payment_gateway/            # Unified provider adapter interface (Stripe, Xendit, etc.)
├── contracts/                      # Formal Schemas & Specifications
│   ├── openapi/                    # OpenAPI 3.x REST endpoint contracts
│   ├── events/                     # Domain event schemas & topics
│   └── schemas/                    # JSON schema definitions (Event Envelope, Brief, etc.)
├── infrastructure/                 # IaC & Deployment
│   ├── docker/                     # Local development Docker Compose & Dockerfiles
│   ├── terraform/                  # Cloud infrastructure (PostgreSQL, K8s, KMS, Object Storage)
│   ├── kubernetes/                 # Helm charts and manifests for staging/production
│   └── gitops/                     # Progressive delivery & ArgoCD/Flux configs
├── tests/                          # Automated Test Suites
│   ├── unit/                       # Fast isolated unit tests
│   ├── integration/                # Cross-module and API tests
│   ├── security/                   # Tenant isolation, RLS, SoD negative tests
│   └── financial/                  # Automated ledger reconciliation & zero-variance tests
├── docs/                           # Architectural Decision Records (ADRs) & Specs
│   ├── requirement_traceability_matrix.md
│   ├── architecture_decision_records.md
│   └── data_dictionary.md
└── scripts/                        # Utility & CI automation scripts
```

---

## 4. Odoo Custom Addons Module Directory Standard

Every custom module follows this explicit architectural separation:
```
module/
├── __init__.py
├── __manifest__.py
├── models/                         # ORM Models (Transactional Persistence)
├── services/                       # Domain Commands & Orchestration Logic
├── repositories/                   # Query Objects & Read Projections
├── controllers/                    # Transport Adapters (REST/JSON-RPC only)
├── security/                       # Model Access (CSV) and Record Rules (XML)
│   ├── ir.model.access.csv
│   └── ir_rule.xml
├── data/                           # Seed Data, Sequence definitions, System Parameters
├── views/                          # OWL & Odoo XML Views
├── wizard/                         # Transient Models (Wizards & User Prompts)
├── cron/                           # Scheduled Background Actions
├── tests/                          # PyUnit Tests (Happy, Hostile, & Tenant Isolation)
├── migrations/                     # Expand-and-Contract Migration Scripts
├── static/                         # Assets, Web/OWL Components
└── README.md                       # Module Documentation & Boundary Spec
```

---

## 5. Domain Responsibilities & Module Overview

| Module | Primary Responsibility | Critical Invariants |
| :--- | :--- | :--- |
| `vin_core` | Tenant, Organization, Legal Entity, Membership, Master Project | Strict multi-tenancy foundation. No financial logic. |
| `vin_identity` | External IdP mapping, SSO/SCIM/JIT, Identity verification | Sensitive identity data isolated from public APIs. |
| `vin_partner` | Creative Partner Profile, KYC/KYB workflow, portfolio metadata | Public profile is a filtered projection; never raw ORM. |
| `vin_matching` | Brief versioning, Hard Eligibility, Contextual Ranking, Shortlist | Hard eligibility cannot be bypassed by paid subscription. |
| `vin_contract` | Contract_VN, Proposal_VN, Multi-tier Approval, Change Requests | Signed contracts are immutable. Version chain: v1.0 → CR001 → v1.1. |
| `vin_execution` | Workstream DAG, Milestones, Tasks, Deliverables | Contractual changes route strictly to Change Request. |
| `vin_escrow` | Virtual escrow accounts, allocations, double-entry ledger | Never store escrow balance as mutable authoritative number. |
| `vin_payment` | Payment provider abstraction, payout state machine, webhooks | Idempotent webhooks. Terminal payout states cannot regress. |
| `vin_tax_invoice`| Multi-jurisdiction tax profiles (PPN/PPh/VAT/WHT), invoicing | Tax rules configurable by jurisdiction; never hard-coded. |
| `vin_ip` | Asset-level IP assignments, passed-through licenses, portfolio rights | IP transfer strictly gated by verified milestone payment. |
| `vin_dispute` | Acceptance dispute, classification dispute, arbitration lock | Disputes freeze only affected escrow/IP/SLA timers. |
| `vin_reputation`| Public metrics (Star/SLA) and internal trust score | Internal trust events are never exposed to public APIs. |
| `vin_subscription`| Client/Partner plans, usage add-ons, commission rule profiles | Take-rate discounts and tier benefits dynamically calculated. |
| `vin_security` | PostgreSQL RLS, Step-Up MFA, Break-Glass, SoD / Four-Eyes | No generic `sudo()`. Cross-tenant access logged immutably. |
| `vin_audit` | Immutable audit events, SHA-256 hash chains, WORM linkage | Full actor/time/policy/hash lineage for every state change. |
| `vin_integration`| Resilience gateway, webhooks, circuit breakers, event replay | Third-party failure triggers `INTEGRATION_DEGRADED` safely. |
| `vin_policy` | Policy versioning, effective dates, hard platform limits | Historical transactions pinned to active policy version. |
| `vin_compliance` | Retention rules, Legal Hold, GDPR/DSAR cryptographic erasure | Legal hold blocks purge. Zero ledger alteration on erasure. |

---

## 6. Implementation Status & Progress Tracker

- [x] **Monorepo Architecture Initialization**
  - [x] Monorepo directories: `addons/`, `services/`, `contracts/`, `infrastructure/`, `tests/`, `docs/`, `scripts/`
  - [x] Master Configuration: `docker-compose.yml`, `Dockerfile`, `odoo.conf`, `pyproject.toml`, `requirements.txt`
  - [x] Master Project README and Architectural Specification
- [x] **Phase 0: Foundation Architecture**
  - [x] `docs/requirement_traceability_matrix.md`: Full Q1–Q250 & Data Dict Traceability
  - [x] `docs/architecture_decision_records.md`: Zero-contradiction architectural validation
  - [x] `contracts/schemas/event_envelope.json`: Canonical Event Envelope
  - [x] `contracts/openapi/openapi_v1.yaml`: OpenAPI 3.0 API Baseline
  - [x] Module: `vin_core` (Tenant, Organization, Legal Entity, Membership, Master Project)
  - [x] Module: `vin_audit` (Audit Events, SHA-256 Tamper-Evident Hash Chain)
  - [x] Module: `vin_policy` (Policy Versions, Effective Date Resolution, Platform Limits)
  - [x] Module: `vin_security` (RLS Context Helper, Four-Eyes SoD Engine, Cross-Tenant Logging)
- [x] **Phase 1: Discovery & Matching**
  - [x] Module: `vin_identity` & `vin_partner`
  - [x] Module: `vin_matching`
- [x] **Phase 2: Project Execution & Asset Vault**
  - [x] Module: `vin_execution`
  - [x] Service: `asset_vault`
- [x] **Phase 3: Contract Engine & e-Signature**
  - [x] Module: `vin_contract`
- [x] **Phase 4: Virtual Escrow Ledger & Payment Orchestration**
  - [x] Module: `vin_escrow` (Escrow Accounts, Milestone Allocations, Balanced Double-Entry Virtual Ledger)
  - [x] Module: `vin_payment` (Provider Gateway Abstraction, Webhook Idempotency, Payout Orchestration, Circuit Breaker)
  - [x] Service: `services/payment_gateway` (Resilience gateway & mock provider abstraction)
- [ ] **Phase 5: Tax, Invoicing & Subscription**
  - [ ] Module: `vin_tax_invoice`
  - [ ] Module: `vin_subscription`
- [ ] **Phase 6: Acceptance, Revision & Dispute Engine**
  - [ ] Module: `vin_dispute`
- [ ] **Phase 7: IP Rights, Portfolio & Reputation**
  - [ ] Module: `vin_ip`
  - [ ] Module: `vin_reputation`
- [ ] **Phase 8: Compliance, Legal Hold & Production Hardening**
  - [ ] Module: `vin_compliance`
  - [ ] Module: `vin_integration`

---

## 7. Developer AI Execution Protocol

All development batches follow the strict sequence:
$$\text{Authorize} \longrightarrow \text{Validate Preconditions} \longrightarrow \text{State Transition} \longrightarrow \text{Persist} \longrightarrow \text{Append Audit} \longrightarrow \text{Publish Event}$$

For inquiries and issues, consult the technical team and the Architectural Decision Records in `docs/`.