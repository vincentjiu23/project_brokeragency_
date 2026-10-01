# `vin_identity` Module

## Overview
The `vin_identity` module provides external IdP federation (Google, Okta, Azure AD, SAML, OIDC) and sensitive KYC/KYB identity verification pipelines.

## Models
*   `vin.identity.link`: Maps Odoo users to external IdP subjects.
*   `vin.identity.verification`: Manages KYC/KYB verification cases, document metadata, and review states.

## Security & Invariants
*   **Encapsulation of Evidence:** Raw documents are never stored directly in PostgreSQL; they reference encrypted Asset Vault SHA-256 hashes.
*   **Four-Eyes Enforcement:** Applicants cannot self-approve their verification cases.
