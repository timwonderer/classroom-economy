# ARC-OPS-016: Schema Ownership Index

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-016 | 1.0 | 2026-04-18 | N/A | Constitutional |

## I. Purpose

Provide a thin runtime table-to-domain ownership index for V2.

## II. Scope

This document lists owning domain documents for authority-critical runtime tables. It does not define fields, constraints, or lifecycle rules.

## III. Authority Level

Constitutional as an index only. It may point to authority; it does not replace domain authority.

## IV. Dependencies

- `INV-CORE-001_Authority_Model.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`

## V. Table Ownership Index

| Table | Owning Domain |
|---|---|
| `transaction` | `DOM-LED-001` |
| `balance_cache` | `DOM-LED-001` |
| `payroll_cache` | `DOM-LED-001` |
| `attendance_sessions` | `DOM-ATT-001` |
| `hall_pass_logs` | `DOM-ATT-001` |
| `seat_attendance_state` | `DOM-ATT-001` |
| `students` | `DOM-IDEN-001` |
| `student_teachers` | `DOM-IDEN-001` |
| `seats` | `DOM-IDEN-001` |
| `teacher_blocks` | `DOM-IDEN-001` |
| `class_memberships` | `DOM-IDEN-001` |
| `store_items` | `DOM-STORE-001` |
| `store_item_blocks` | `DOM-STORE-001` |
| `student_items` | `DOM-STORE-001` |
| `redemption_audit_logs` | `DOM-STORE-001` |
| `rent_payments` | `DOM-OBL-001` |
| `insurance_policies` | `DOM-OBL-001` |
| `insurance_policy_blocks` | `DOM-OBL-001` |
| `student_insurance` | `DOM-OBL-001` |
| `insurance_claims` | `DOM-OBL-001` |
| `class_economies` | `DOM-CLASS-001` |
| `class_features` | `DOM-CLASS-001` |
| `feature_settings` | `DOM-CLASS-001` |
| `hall_pass_settings` | `DOM-CLASS-001` |
| `rent_settings` | `DOM-CLASS-001` |
| `payroll_settings` | `DOM-CLASS-001` |
| `banking_settings` | `DOM-CLASS-001` |

## VI. Rules

- If a table appears here, the listed domain is the only authority that may define its schema contract.
- Other documents may reference the table, but may not redefine its fields or constraints.
- If ownership is unclear or missing, the documentation model is incomplete and must be amended before introducing competing definitions.

## VII. Amendment

Revisions require version increment, effective-date update, and continued consistency with the domain foundation and authority model.
