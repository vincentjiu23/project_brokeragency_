# `vin_core` Module

## Overview
The `vin_core` module establishes the core multi-tenant and organization boundaries for the VIN Project platform.

## Models
*   `vin.tenant`: Top-level tenant isolation root.
*   `vin.organization`: Commercial entity root owning projects and memberships.
*   `vin.legal.entity`: Multi-jurisdiction legal registrations, NPWP/VAT, and company numbers.
*   `vin.membership`: RBAC scoping binding Odoo users to organizations with specific functional roles.
*   `vin.master.project`: Project aggregation root implementing the non-negotiable 5-gate closure workflow.

## Security & Isolation
Tenant isolation is enforced server-side through `ir.rule` matching user memberships. Cross-tenant access is prohibited unless bridged by an explicit `CONTRACT_VN`.
