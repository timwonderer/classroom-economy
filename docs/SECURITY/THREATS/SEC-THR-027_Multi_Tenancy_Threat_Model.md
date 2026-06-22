# ARC-SEC-027: Multi-Tenancy Threat Model

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|ARC-SEC-027| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose
Document threat vectors, attack scenarios, and required mitigations strictly concerning multi-tenancy boundaries and `join_code` scoping.

## II. Scope
Security audits, penetration testing scenarios, and design reviews of isolated context handlers.

## III. Authority Level
Authoritative (ARC Tier). Subservient to INV-CORE-000 constraints.

## IV. Dependencies
- INV-CORE-000: Core Invariants
- ARC-SEC-015: Multi-Tenancy Audit

## V. Attack Vectors
1. **Insecure Direct Object Reference (IDOR)**
   - **Scenario:** A student modifies the request ID parameter of a transfer to target a student in another class.
   - **Mitigation:** Query scopes must intrinsically filter by `join_code`.

2. **Cross-Tenant Data Leak via Globals**
   - **Scenario:** A route dumps `StoreItem` entries without filtering by `join_code`.
   - **Mitigation:** `join_code` is enforced as an invariant parameter on all domain-level queries. No global fallback allowed.

3. **Improper Role Escalation**
   - **Scenario:** Using a teacher token to perform a global sysadmin action.
   - **Mitigation:** Strict route decorators (`@admin_required`, `@sysadmin_required`) enforce context validation prior to controller logic execution.

## VI. Verification
Multi-tenancy verification requires exhaustive testing using parallel HTTP sessions representing disparate `join_code` contexts to guarantee total isolation.
