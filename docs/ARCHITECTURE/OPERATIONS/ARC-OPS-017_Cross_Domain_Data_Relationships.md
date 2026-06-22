# ARC-OPS-017: Cross-Domain Data Relationships

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-017 | 1.0 | 2026-04-18 | N/A | Constitutional |

## I. Purpose

Define the semantics of the cross-domain identifiers and foreign references that connect V2 domains.

## II. Scope

This document covers reference meaning only. It does not assign shared ownership of tables or fields.

## III. Authority Level

Constitutional.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_Authority_Model.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `ARC-OPS-016_Schema_Ownership_Index.md`

## V. Core Cross-Domain References

### `join_code`

- Meaning:
  - Public class boundary token.
- Used across:
  - Identity
  - Ledger
  - Attendance
  - Store
  - Obligations
  - Class Configuration
- Rule:
  - `join_code` has no meaning outside a class-scoped universe.

### `class_id`

- Meaning:
  - Internal class authority key anchored by `class_economies`.
- Used across:
  - Identity
  - Class Configuration
  - policy/config rows that need stable class linkage
- Rule:
  - `class_id` is an anchor reference, not a substitute for domain ownership.

### `student_id`

- Meaning:
  - Identity-domain student principal reference.
- Used across:
  - Ledger
  - Attendance
  - Store
  - Obligations
- Rule:
  - `student_id` always inherits scoped meaning from the surrounding class context.

### `teacher_id`

- Meaning:
  - Identity-domain teacher/admin principal reference.
- Used across:
  - Ledger
  - Attendance
  - Store
  - Obligations
  - Class Configuration
- Rule:
  - `teacher_id` alone is not sufficient to define class scope in V2.

### `policy_id`

- Meaning:
  - Obligations-domain reference to an insurance policy definition.
- Used across:
  - Obligations
  - Ledger reimbursement linkage
- Rule:
  - `policy_id` links a ledger event back to obligation context; it does not make Ledger the owner of policy schema.

### `store_item_id`

- Meaning:
  - Store-domain reference to a catalog item.
- Used across:
  - Store
  - redemption/audit flows
- Rule:
  - Money movement relating to a store item still belongs to Ledger, not Store.

### `original_transaction_id` / `reversal_transaction_id`

- Meaning:
  - Ledger-internal event relationship links.
- Used across:
  - Ledger
  - FEAT workflows that need traceability to source events
- Rule:
  - Relationship linkage does not transfer ownership away from Ledger.

### `transaction_id` on `insurance_claims`

- Meaning:
  - Obligations-domain pointer to the incident transaction being claimed against.
- Used across:
  - Obligations
  - Ledger reimbursement traceability
- Rule:
  - This is a traceability reference only; claim state stays in Obligations and money state stays in Ledger.

## VI. Interpretation Rules

- Cross-domain references are allowed; shared mutation authority is not.
- A reference field documents relationship semantics, not ownership transfer.
- When a workflow spans domains, FEAT orchestrates; domains retain their own table authority.

## VII. Amendment

Revisions require version increment, effective-date update, and continued consistency with the authority model and domain foundation.
