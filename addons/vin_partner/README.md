# `vin_partner` Module

## Overview
The `vin_partner` module manages Creative Partner Profiles, agency vs. individual account tiers, verification states, expertise tags, and portfolio showcase items.

## Models
*   `creative.partner.profile`: Extends and profiles creative partners, tracking account type, verification status, internal trust score, and public rating.
*   `vin.expertise.tag`: Normalized taxonomy of creative skills, industries, and service specializations.
*   `vin.portfolio.item`: Verified portfolio showcase items with strict IP disclosure permissions (`PORTFOLIO_DISPLAY_ALLOWED`).

## Services
*   `PartnerProfileProjectionService`: Generates sanitized public projections of partner profiles, strictly stripping sensitive fields such as internal trust scores, banking credentials, and non-cleared contact details.

## Security & Invariants
*   **Tenant Isolation**: Strict multi-tenant row-level security per tenant isolation rules.
*   **IP / NDA Clearance (Q124)**: Portfolio items cannot transition to published state without explicit `display_allowed` verification.
*   **Sensitive Field Protection**: Internal trust scoring and financial details are inaccessible via public projection views.
