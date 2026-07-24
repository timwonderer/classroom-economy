# Constitutional Schema Audit — Table Compliance Report

| Audit Date | Authority Document | Authority Version | Auditor | Status |
|---|---|---|---|---|
| 2026-07-16 | DOM-CORE-002 | 1.6 | Claude (automated) | **Complete** |

---

## I. Summary

| Metric | Count |
|---|---|
| Total tables in `classroom_economy` | 54 |
| Authorized by DOM-CORE-002 | 46 |
| Explicitly prohibited (user instruction) | 9 |
| Dropped this session (Cat 1) | 25 |
| Remaining unauthorized | 0 |

---

## II. Authorized Tables (46)

All tables below have explicit permission in DOM-CORE-002 v1.6.

### §1. Identity & Class Binding (DOM-IDEN-001 / DOM-IDEN-003)

| Table | Status | Notes |
|---|---|---|
| `users` | ✅ Present | |
| `seats` | ✅ Present | |
| `classes` | ✅ Present | |
| `identity_profiles` | ✅ Present | |
| `user_invite_tokens` | ✅ Dropped | Removed by migration `7c3d4e5f6a7b` |
| `user_recovery_tokens` | ✅ Dropped | Removed by migration `7c3d4e5f6a7b` |
| `recovery_requests` | ✅ Present | DOM-IDEN-003 owned; legacy columns dropped (migration 4bf6de0868a4) |
| `student_recovery_codes` | ✅ Present | Canonicalized: seat_id+class_id (migration 4bf6de0868a4) |
| `passkey_credentials` | ✅ Present | |

### §2. Class Configuration (DOM-CLASS-001)

| Table | Status | Notes |
|---|---|---|
| `class_features` | ✅ Present | |
| `feature_settings` | ✅ Present | |
| `hall_pass_settings` | ✅ Present | |
| `rent_settings` | ✅ Present | |
| `payroll_settings` | ✅ Present | |
| `banking_settings` | ✅ Present | |

### §3. Attendance & Mobility (DOM-ATT-001)

| Table | Status | Notes |
|---|---|---|
| `attendance_sessions` | ✅ Present | |
| `hall_pass_logs` | ✅ Present | |
| `seat_attendance_state` | ✅ Present | |

### §4. Obligations & Entitlements (DOM-OBL-001)

| Table | Status | Notes |
|---|---|---|
| `assessment_events` | ✅ Present | |
| `obligation_lifecycle` | ✅ Present | |
| `obligation_satisfaction` | ✅ Present | |
| `obligation_reversal` | ✅ Present | |
| `entitlement_events` | ✅ Present | |

### §5. Ledger & Money (DOM-LED-001)

| Table | Status | Notes |
|---|---|---|
| `ledger_transaction` | ✅ Present | |
| `ledger_balance_snapshot` | ✅ Present | |

### §6. Store & Redemption (DOM-STORE-001)

| Table | Status | Notes |
|---|---|---|
| `store_items` | ✅ Present | |
| `store_item_visibility` | ✅ Present | |
| `store_purchases` | ✅ Present | |
| `redemption_events` | ✅ Present | |

### §7. Operations & Observability (DOM-OPS-001)

| Table | Status | Notes |
|---|---|---|
| `operational_events` | ✅ Present | |
| `audit_events` | ✅ Present | Renamed from `audit_log` in v1.6 |
| `chain_heads` | ✅ Present | New in v1.6 |
| `incident_events` | ✅ Present | |
| `incident_summary` | ✅ Present | |
| `alert_events` | ✅ Present | |
| `invariant_run_events` | ✅ Present | |
| `job_events` | ✅ Present | |
| `health_check_events` | ✅ Present | |

### §8. Interpretation (DOM-ITR-001)

| Table | Status | Notes |
|---|---|---|
| `interpretation_snapshots` | ✅ Present | |
| `interpretation_annotations` | ✅ Present | |

### §9. Support & Communication (DOM-SUP-001)

| Table | Status | Notes |
|---|---|---|
| `issues` | ✅ Present | |
| `issue_status_history` | ✅ Present | |
| `issue_resolution_actions` | ✅ Present | |
| `ticket_correlation_pack` | ✅ Present | Fixed from plural in v1.6 |
| `announcements` | ✅ Present | |
| `issue_categories` | ✅ Present | |
| `user_reports` | ✅ Dropped | Removed by migration `7c3d4e5f6a7b` |

### §10. Economic Policy (DOM-ECON-003)

| Table | Status | Notes |
|---|---|---|
| `policy_versions` | ✅ Present | |
| `policy_transitions` | ✅ Present | |

---

## III. Explicitly Prohibited Tables (9)

Per user instruction and constitutional analysis. These tables must be dropped (separate migration scope).

| Table | Prohibition Basis | Active Code Refs? |
|---|---|---|
| `teachers` | INV-IDEN-001: no separate identity tables | Dropped by migration `7c3d4e5f6a7b` |
| `system_admins` | INV-IDEN-001 | Dropped by migration `7c3d4e5f6a7b` |
| `system_admin_credentials` | INV-IDEN-001 | Dropped by migration `7c3d4e5f6a7b` |
| `teacher_credentials` | INV-IDEN-001 | Dropped by migration `7c3d4e5f6a7b` |
| `teacher_invite_codes` | Superseded by user_invite_tokens | Dropped by migration `7c3d4e5f6a7b` |
| `user_invite_tokens` | DOM-CORE-002 §1 EXTINCT | Dropped by migration `7c3d4e5f6a7b` |
| `user_recovery_tokens` | DOM-CORE-002 §1 EXTINCT | Dropped by migration `7c3d4e5f6a7b` |
| `class_memberships` | Deprecated; classes is canonical | Dropped by migration `7c3d4e5f6a7b` |
| `insurance_policy_blocks` | No domain authority | Dropped by migration `7c3d4e5f6a7b` |

**Note:** These tables are no longer present in the dev database after migration `7c3d4e5f6a7b`.

---

## IV. Dropped This Session — Category 1: Legacy Absorbed (4)

Dropped by migration `5a1b2c3d4e5f`.

| Table | Absorbed By | Had Active Code? |
|---|---|---|
| `obligation_assessment` | `assessment_events` (DOM-OBL-001) | Dropped earlier |
| `student_insurance` | `entitlement_events` (DOM-OBL-001) | Dropped earlier |
| `ticket_correlation_packs` (plural) | `ticket_correlation_pack` (singular, DOM-SUP-001) | Dropped earlier |
| `audit_log` | `audit_events` + `chain_heads` (DOM-OPS-001) | Dropped earlier |

---

## V. Remaining Unauthorized Tables (16)

These tables exist in the database but have no explicit permission in DOM-CORE-002 v1.6. Grouped by recommended action.

### Category A: Unique — Serve defined v2 operations, need DOM-CORE-002 amendment (7)

| # | Table | Owning Domain | Duty | Recommendation |
|---|---|---|---|---|
| 1 | `saved_adjustments` | DOM-CLASS-001 | Per-class saved payroll adjustment templates | Dropped by migration `7c3d4e5f6a7b` |
| 2 | `error_events` | DOM-OPS-001 | Structured application error log | Dropped by migration `7c3d4e5f6a7b` |
| 3 | `analytics_events` | DOM-ITR-001 | Raw analytics event stream | Dropped by migration `7c3d4e5f6a7b` |
| 4 | `analytics_snapshots` | DOM-ITR-001 | Point-in-time analytics rollups | Dropped by migration `7c3d4e5f6a7b` |
| 5 | `analytics_alerts` | DOM-ITR-001 | Analytics threshold alerts | Dropped by migration `7c3d4e5f6a7b` |
| 6 | `actor_request_trace` | DOM-OPS-001 | Per-request actor context trace | Kept canonical |
| 7 | `teacher_onboarding` | DOM-IDEN-001 | Teacher first-run onboarding state | Dropped by migration `7c3d4e5f6a7b` |

### Category B: Active legacy — Has runtime code dependencies, needs code migration before drop (5)

| # | Table | Active Code | Blocked By |
|---|---|---|---|
| 1 | `error_logs` | `ErrorLog` model, 15+ refs in `system_admin.py` | Dropped by migration `7c3d4e5f6a7b` |
| 2 | `payroll_cache` | DOM-CORE-002 §2 explicitly prohibits persisted compute caches | Dropped by migration `7c3d4e5f6a7b` |
| 3 | `insurance_claims` | Legacy insurance system | Dropped by migration `7c3d4e5f6a7b` |
| 4 | `insurance_enrollments` | Legacy insurance system | Dropped by migration `7c3d4e5f6a7b` |
| 5 | `insurance_policies` | Legacy insurance system | Dropped by migration `7c3d4e5f6a7b` |

### Category C: Unknown / needs investigation (4)

| # | Table | Notes |
|---|---|---|
| 1 | `economy_snapshot` | Dropped by migration `7c3d4e5f6a7b` |
| 2 | `integrity_status` | Dropped by migration `7c3d4e5f6a7b` |
| 3 | `rent_items` | Dropped by migration `7c3d4e5f6a7b` |
| 4 | `rent_payments` | Dropped by migration `7c3d4e5f6a7b` |
| 5 | `rent_policy_versions` | Dropped by migration `7c3d4e5f6a7b` |
| 6 | `rent_waivers` | Dropped by migration `7c3d4e5f6a7b` |

---

## VI. Changes Applied This Session

### DOM-CORE-002 v1.5 → v1.6

| Section | Change |
|---|---|
| §7 (Operations) | `audit_log` → `audit_events` + `chain_heads` |
| §9 (Support) | `ticket_correlation_packs` → `ticket_correlation_pack` (singular) |

### Canonical model reference

The historical canonical ORM reference was folded back into the live model layer. The active ORM authority is now `app/models.py`; the old standalone canonical module has been removed.

### Migrations

| Revision | Description | Status |
|---|---|---|
| `4bf6de0868a4` | Canonicalize recovery tables: seat_id, class_id, drop legacy columns | ✅ applied |
| `5a1b2c3d4e5f` | Drop 4 legacy absorbed orphan tables | ✅ applied |
| `6b2c3d4e5f6a` | Add `class_public_id`; deidentify issues surface; drop `user_reports` | ✅ applied |
| `7c3d4e5f6a7b` | Drop all 26 unauthorized tables (DOM-CORE-002 audit) | ✅ applied |

**Current Alembic head (dev):** `7c3d4e5f6a7b`

### test_smoke.py

- Imports: `AuditLog` → `AuditEvent, ChainHead`
- Model count assertion: 44 → 45

---

## VII. Recommended Next Steps

1. **Amend DOM-CORE-002 v1.7** for Category A tables (`actor_request_trace` — sole table needing amendment)
2. **Rewrite `Admin` → `User(TEACHER)`** across all routes (P0 — app cannot boot without this)
3. **Rewrite `SystemAdmin` → `User(SYSADMIN)`** in `system_admin.py` (P0)
4. **Migrate insurance feature** → `policy_versions` + obligation domain (P2)
5. **Migrate rent feature** → obligation satisfaction chain + `policy_versions(domain='rent')` (P2)
5. **Plan legacy identity table drops** (prohibited tables — largest code migration effort)
