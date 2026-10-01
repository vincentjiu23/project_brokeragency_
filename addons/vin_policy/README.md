# `vin_policy` Module

## Overview
The `vin_policy` module implements the policy versioning engine and non-retroactive historical policy pinning as mandated by Section 30 of the VIN Master Business Specification.

## Models
*   `vin.policy.version`: Versioned rules definition storing JSON policy variables, validity timestamps, and immutable enforcement status.

## Non-Negotiable Invariants
*   **Non-Retroactive Historical Pinning:** In-flight contracts and financial events are pinned to the policy version active at creation. Active policy rules cannot be mutated in place.
*   **Deterministic Activation:** Activating version $N+1$ automatically marks version $N$ as superseded with `effective_to` timestamp.
