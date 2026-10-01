# `vin_audit` Module

## Overview
The `vin_audit` module provides append-only, tamper-evident cryptographic audit logging for all critical platform transitions across the VIN Project.

## Models
*   `vin.audit.event`: Canonical audit entity storing actor, action, subject, payload, timestamps, and previous SHA-256 event hash.

## Non-Negotiable Invariants
*   **Append-Only:** `write()` and `unlink()` are permanently locked and throw exceptions.
*   **Cryptographic Hash Chain:** Every event is chained to the preceding event in the tenant boundary using SHA-256.
*   **WORM Integration:** Ready for downstream synchronization with WORM legal object storage.
