# -*- coding: utf-8 -*-
"""
VIN Project Monorepo Scaffolding Script
Creates the locked 18 modules with standard subdirectories, manifests, access rules, and READMEs.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ADDONS_DIR = BASE_DIR / "addons"
SERVICES_DIR = BASE_DIR / "services"
INFRA_DIR = BASE_DIR / "infrastructure"

MODULE_METADATA = {
    "vin_identity": {
        "name": "VIN Identity — External IdP & Verification Mapping",
        "category": "Authentication",
        "summary": "External IdP, SSO/SCIM/JIT, and sensitive identity verification boundary",
        "depends": "['vin_core', 'vin_audit']",
        "description": "Owns external identity mapping, SSO/SCIM integration contracts, and sensitive KYC/KYB identity verification states."
    },
    "vin_partner": {
        "name": "VIN Partner — Creative Partner Profile & Portfolio",
        "category": "Partner",
        "summary": "Creative Partner Profile, agency/individual accounts, and portfolio metadata",
        "depends": "['vin_core', 'vin_identity', 'vin_audit']",
        "description": "Owns Creative Partner Profile, account types, verification workflows, expertise tags, and portfolio metadata."
    },
    "vin_matching": {
        "name": "VIN Matching — Discovery & Recommendation Engine",
        "category": "Project",
        "summary": "Creative Project Brief versioning, Hard Eligibility, and Contextual Ranking",
        "depends": "['vin_core', 'vin_partner', 'vin_policy', 'vin_audit']",
        "description": "Owns Creative Project Brief versions (BRIEF_VN), deterministic hard eligibility gates, and match snapshots."
    },
    "vin_contract": {
        "name": "VIN Contract — Immutable Contracts, Proposals & Approval Matrix",
        "category": "Legal",
        "summary": "Contract_VN, Proposal_VN, multi-tier approvals, and versioned change requests",
        "depends": "['vin_core', 'vin_policy', 'vin_audit']",
        "description": "Owns immutable versioned legal contracts (CONTRACT_VN), structured proposals, and approval matrix invalidation."
    },
    "vin_execution": {
        "name": "VIN Execution — Workstream DAG, Milestones & Deliverables",
        "category": "Project",
        "summary": "Workstream DAG execution, milestones, tasks, deliverables, and submissions",
        "depends": "['vin_core', 'vin_contract', 'vin_audit']",
        "description": "Owns Workstream DAG, milestones, operational vs contractual tasks, deliverables, and immutable submissions."
    },
    "vin_escrow": {
        "name": "VIN Escrow — Virtual Escrow & Double-Entry Ledger",
        "category": "Accounting",
        "summary": "Virtual escrow accounts, milestone allocations, and balanced double-entry ledger",
        "depends": "['vin_core', 'vin_contract', 'vin_audit']",
        "description": "Owns virtual escrow accounts, milestone allocations, locks, and balanced double-entry virtual ledger rows."
    },
    "vin_payment": {
        "name": "VIN Payment — Provider Gateways, Webhooks & Payouts",
        "category": "Accounting",
        "summary": "Payment provider abstraction, idempotent webhooks, and payout state machines",
        "depends": "['vin_core', 'vin_escrow', 'vin_audit']",
        "description": "Owns payment provider abstraction, idempotent webhook processing, payout state machines, and reconciliation."
    },
    "vin_tax_invoice": {
        "name": "VIN Tax & Invoice — Multi-Jurisdiction Compliance & Invoicing",
        "category": "Accounting",
        "summary": "Tax resolver, VAT/PPN, WHT/PPh, partner invoices, and tax certificates",
        "depends": "['vin_core', 'vin_escrow', 'vin_audit']",
        "description": "Owns tax profiles, invoice orchestration, tax resolver integrations, and immutable tax certificate payloads."
    },
    "vin_ip": {
        "name": "VIN IP — Asset-Level Rights & License Assignments",
        "category": "Legal",
        "summary": "Asset-level IP ownership, pass-through licenses, and portfolio display gates",
        "depends": "['vin_core', 'vin_execution', 'vin_escrow', 'vin_audit']",
        "description": "Owns asset-level intellectual property assignments, perpetual licenses, and portfolio display policy gates."
    },
    "vin_dispute": {
        "name": "VIN Dispute — Tiered Acceptance Disputes & Arbitration",
        "category": "Legal",
        "summary": "Acceptance disputes, revision classification objections, and arbitration lock",
        "depends": "['vin_core', 'vin_execution', 'vin_escrow', 'vin_audit']",
        "description": "Owns acceptance dispute state machines, revision classification objections, and evidence package linkages."
    },
    "vin_reputation": {
        "name": "VIN Reputation — Public Ratings & Internal Trust Score",
        "category": "Reputation",
        "summary": "Two-way dual-blind reviews, public metrics, and internal trust event scoring",
        "depends": "['vin_core', 'vin_partner', 'vin_audit']",
        "description": "Owns public star ratings, completion/on-time metrics, and internal trust score pipeline (hidden from public)."
    },
    "vin_subscription": {
        "name": "VIN Subscription — Tier Plans, Usage Billing & Commission Rules",
        "category": "Sales",
        "summary": "Client/Partner subscription plans, usage add-ons, and commission rule profiles",
        "depends": "['vin_core', 'vin_partner', 'vin_escrow', 'vin_audit']",
        "description": "Owns organization subscription tiers, usage-based billing, take-rate discounts, and commission rule profiles."
    },
    "vin_integration": {
        "name": "VIN Integration — Resilience Gateway, Webhooks & Replay",
        "category": "Technical",
        "summary": "Integration resilience, circuit breakers, dead-letter queues, and event replay",
        "depends": "['vin_core', 'vin_audit']",
        "description": "Owns third-party integration resilience, circuit breakers, dead-letter queue, and safe event replay mechanisms."
    },
    "vin_compliance": {
        "name": "VIN Compliance — Data Retention, Legal Hold & GDPR/DSAR",
        "category": "Compliance",
        "summary": "Data retention lifecycles, legal hold locks, and cryptographic erasure",
        "depends": "['vin_core', 'vin_audit']",
        "description": "Owns data classification, retention rules, legal holds, and DSAR cryptographic erasure without mutating ledgers."
    }
}

SUBDIRS = [
    "models",
    "services",
    "repositories",
    "controllers",
    "security",
    "data",
    "views",
    "wizard",
    "cron",
    "tests",
    "migrations",
    "static/description"
]

SERVICES = [
    "event_mesh",
    "asset_vault",
    "matching_engine",
    "ai_gateway",
    "dispute_engine",
    "payment_gateway"
]

INFRA_DIRS = [
    "terraform",
    "kubernetes",
    "gitops"
]

def scaffold():
    print("Scaffolding VIN Project modules and services...")

    # Scaffold Addons
    for mod, meta in MODULE_METADATA.items():
        mod_dir = ADDONS_DIR / mod
        for sub in SUBDIRS:
            (mod_dir / sub).mkdir(parents=True, exist_ok=True)

        # __init__.py
        init_py = mod_dir / "__init__.py"
        if not init_py.exists():
            init_py.write_text(
                "# -*- coding: utf-8 -*-\n"
                "from . import models\n"
                "from . import services\n"
                "from . import repositories\n"
                "from . import controllers\n",
                encoding="utf-8"
            )

        # __manifest__.py
        manifest_py = mod_dir / "__manifest__.py"
        if not manifest_py.exists():
            manifest_content = f"""# -*- coding: utf-8 -*-
{{
    'name': '{meta["name"]}',
    'version': '17.0.1.0.0',
    'category': '{meta["category"]}',
    'summary': '{meta["summary"]}',
    'description': \"\"\"{meta["description"]}\"\"\",
    'author': 'VIN Project Team',
    'depends': {meta["depends"]},
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'Proprietary',
}}
"""
            manifest_py.write_text(manifest_content, encoding="utf-8")

        # models/__init__.py
        for pkg in ["models", "services", "repositories", "controllers", "tests", "wizard"]:
            p_init = mod_dir / pkg / "__init__.py"
            if not p_init.exists():
                p_init.write_text("# -*- coding: utf-8 -*-\n", encoding="utf-8")

        # security/ir.model.access.csv
        access_csv = mod_dir / "security" / "ir.model.access.csv"
        if not access_csv.exists():
            access_csv.write_text("id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n", encoding="utf-8")

        # security/ir_rule.xml
        ir_rule = mod_dir / "security" / "ir_rule.xml"
        if not ir_rule.exists():
            ir_rule.write_text(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                "<odoo>\n"
                "    <data noupdate=\"1\">\n"
                "    </data>\n"
                "</odoo>\n",
                encoding="utf-8"
            )

        # README.md
        readme = mod_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# `{mod}` Module\n\n"
                f"## Overview\n{meta['summary']}.\n\n"
                f"## Responsibilities\n{meta['description']}\n",
                encoding="utf-8"
            )

    # Scaffold Services
    for svc in SERVICES:
        s_dir = SERVICES_DIR / svc
        s_dir.mkdir(parents=True, exist_ok=True)
        s_readme = s_dir / "README.md"
        if not s_readme.exists():
            s_readme.write_text(
                f"# {svc.replace('_', ' ').title()} Service Boundary\n\n"
                f"Specialized decoupled microservice handling domain: `{svc}`.\n",
                encoding="utf-8"
            )

    # Scaffold Infrastructure
    for infra in INFRA_DIRS:
        i_dir = INFRA_DIR / infra
        i_dir.mkdir(parents=True, exist_ok=True)
        i_readme = i_dir / "README.md"
        if not i_readme.exists():
            i_readme.write_text(
                f"# Infrastructure: {infra.title()}\n\n"
                f"Configuration and deployment scripts for `{infra}`.\n",
                encoding="utf-8"
            )

    print("Scaffolding complete!")

if __name__ == "__main__":
    scaffold()
