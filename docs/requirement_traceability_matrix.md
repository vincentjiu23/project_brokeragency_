# VIN Project — Requirement Traceability Matrix (RTM)

| Req ID / Decision | Domain | Odoo Module | Primary Model(s) | API Contract | Event Contract | Test Class | Verification Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Q1–Q10 / Q147** | Multi-Tenancy & Identity | `vin_core` | `vin.tenant`, `vin.organization`, `vin.legal.entity`, `vin.membership` | `/api/v1/tenants`, `/api/v1/organizations` | `TENANT_INITIALIZED`, `ORG_ONBOARDED` | `TestTenantIsolation` | Verified |
| **Q11–Q25 / Q150** | Creative Partner | `vin_partner` | `creative_partner_profile`, `partner_verification_case`, `portfolio_item` | `/api/v1/partners/{id}`, `/api/v1/partners/{id}/verify` | `PARTNER_VERIFIED`, `PORTFOLIO_APPROVED` | `TestPartnerQualification` | Verified |
| **Q26–Q40 / Q155** | Discovery & Matching | `vin_matching` | `project_brief_vn`, `match_snapshot`, `opportunity_record` | `/api/v1/projects/{id}/matches`, `/api/v1/opportunities/{id}/respond` | `BRIEF_CREATED`, `CONTACT_INITIATED`, `MATCH_SNAPSHOT_CREATED` | `TestMatchingEligibility` | Verified |
| **Q41–Q60 / Q160** | Contract & Proposal | `vin_contract` | `contract_vn`, `proposal_vn`, `approval_record`, `change_request` | `/api/v1/contracts/{id}/proposals`, `/api/v1/change-requests` | `PROPOSAL_SUBMITTED`, `APPROVAL_INVALIDATED`, `CONTRACT_ACTIVATED` | `TestContractImmutability` | Verified |
| **Q61–Q75 / Q165** | Execution DAG | `vin_execution` | `workstream_dag`, `milestone`, `task`, `deliverable` | `/api/v1/workstreams/{id}/tasks`, `/api/v1/milestones/{id}` | `MILESTONE_STARTED`, `TASK_DEPENDENCY_RESOLVED` | `TestWorkstreamDAG` | Verified |
| **Q76–Q90 / Q170** | Deliverable & Review | `vin_execution` | `deliverable_submission`, `acceptance_record`, `revision_record` | `/api/v1/deliverables/{id}/submissions`, `/api/v1/deliverables/{id}/acceptance` | `DELIVERABLE_SUBMITTED`, `MILESTONE_ACCEPTED` | `TestDeliverableReview` | Verified |
| **Q91–Q98 / Q175** | Dispute & Arbitration | `vin_dispute` | `dispute`, `dispute_evidence_item`, `arbitration_case` | `/api/v1/disputes/{id}`, `/api/v1/disputes/{id}/escalate` | `DISPUTE_OPENED`, `DISPUTE_ESCALATED`, `DISPUTE_RESOLVED` | `TestDisputeFreeze` | Verified |
| **Q99–Q105 / Q180**| Subscription & Fee | `vin_subscription`| `subscription`, `commission_rule_profile`, `fee_rule` | `/api/v1/subscriptions`, `/api/v1/fees/evaluate` | `SUBSCRIPTION_UPGRADED`, `FEE_CALCULATED` | `TestCommissionProfile` | Verified |
| **Q106–Q109 / Q185**| Escrow & Payment | `vin_escrow`, `vin_payment` | `escrow_account`, `escrow_allocation`, `ledger_entry`, `payment_event`, `settlement` | `/api/v1/payments/webhooks/{provider}`, `/api/v1/settlements/{id}/execute` | `PAYMENT_WEBHOOK_RECEIVED`, `ESCROW_ALLOCATED`, `PAYOUT_SUCCESS` | `TestEscrowVirtualLedger` | Verified |
| **Q110–Q116 / Q190**| Communication & Governance | `vin_security`, `vin_core` | `vin.cross.tenant.access.log`, `governance_override_record` | `/api/v1/governance/overrides` | `OVERRIDE_REQUESTED`, `OVERRIDE_EXECUTED` | `TestFourEyesGovernance` | Verified |
| **Q117–Q128 / Q200**| AI Governance & Vault | `vin_core`, `vin_audit` | `asset_object`, `ai_decision_log`, `vin.audit.event` | `/api/v1/assets/authorize-upload`, `/api/v1/ai/decisions` | `ASSET_UPLOADED`, `AI_RECOMMENDATION_LOGGED` | `TestAIDecisionLineage` | Verified |
| **Q129–Q136 / Q210**| Tax & Invoicing | `vin_tax_invoice` | `tax_profile`, `invoice`, `tax_certificate` | `/api/v1/invoices/{id}`, `/api/v1/tax/resolve` | `INVOICE_GENERATED`, `TAX_RESOLVED` | `TestTaxResolver` | Verified |
| **Q137–Q146 / Q250**| IP Rights & Compliance | `vin_ip`, `vin_compliance` | `ip_assignment`, `evidence_package`, `retention_rule`, `legal_hold` | `/api/v1/ip/assignments`, `/api/v1/compliance/legal-holds` | `IP_ASSIGNED`, `LEGAL_HOLD_APPLIED` | `TestIPTransferAndLegalHold` | Verified |

## Architecture Acceptance Criteria (AC-01 to AC-12)
*   **AC-01 (Eligible Brief Matched):** Only hard-eligible candidates; snapshot stored in `match_snapshot`.
*   **AC-02 (Partner Contacted):** Actionable notification emitted and response SLA timer started.
*   **AC-03 (Material Proposal Delta):** Material change triggers automatic invalidation of affected approvals.
*   **AC-04 (Escrow Funded):** Virtual ledger funded with locked FX rate timestamp.
*   **AC-05 (Deliverable Accepted):** Automatic trigger of milestone escrow release and IP transition.
*   **AC-06 (Duplicate Webhook):** Idempotency key deduplication prevents duplicate payout or state regression.
*   **AC-07 (Provider Outage):** Transition to `INTEGRATION_DEGRADED` while core Odoo state remains protected.
*   **AC-08 (Closure Gates Pass):** 5-gate check triggers `PROJECT_COMPLETED` with 14-working-day review window.
*   **AC-09 (Window Expires):** Project auto-closes into `PROJECT_CLOSED` and triggers cold archival.
*   **AC-10 (Post-Close Amendment):** Historical `V_FINAL` unmutated; additive `POST_CLOSURE_AMENDMENT_VN`.
*   **AC-11 (Cross-Tenant Access):** Strict block without active contractual bridge; immutable logging in `vin.cross.tenant.access.log`.
*   **AC-12 (High-Risk AI):** Autonomous financial/legal actions blocked; mandatory human review required.
