# Constitutional Schema Audit — Table Compliance Report

| Audit Date | Authority Document | Authority Version | Auditor | Status |
|---|---|---|---|---|
| 2026-07-16 | DOM-CORE-002 | 1.6 | Claude (automated) | **In Progress** |

---

## I. Summary

| Metric | Count |
|---|---|
| Total tables in `classroom_economy` | 75 |
| Authorized by DOM-CORE-002 | 46 |
| Explicitly prohibited (user instruction) | 9 |
| Dropped this session (Cat 1) | 4 |
| Remaining unauthorized | 16 |

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
| `user_invite_tokens` | ✅ Present | Marked EXTINCT in doc; still in DB |
| `user_recovery_tokens` | ✅ Present | Marked EXTINCT in doc; still in DB |
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
| `user_reports` | ✅ Present | |

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
| `teachers` | INV-IDEN-001: no separate identity tables | Yes — heavy runtime usage |
| `system_admins` | INV-IDEN-001 | Yes — sysadmin routes |
| `system_admin_credentials` | INV-IDEN-001 | Yes — sysadmin auth |
| `teacher_credentials` | INV-IDEN-001 | Yes — teacher auth |
| `teacher_invite_codes` | Superseded by user_invite_tokens | Minimal |
| `user_invite_tokens` | DOM-CORE-002 §1 EXTINCT | Minimal |
| `user_recovery_tokens` | DOM-CORE-002 §1 EXTINCT | Minimal |
| `class_memberships` | Deprecated; classes is canonical | Yes — bridge code |
| `insurance_policy_blocks` | No domain authority | Unknown |

**Note:** These require code migration before table drops. Not in current scope.

---

## IV. Dropped This Session — Category 1: Legacy Absorbed (4)

Dropped by migration `5a1b2c3d4e5f`.

| Table | Absorbed By | Had Active Code? |
|---|---|---|
| `obligation_assessment` | `assessment_events` (DOM-OBL-001) | No — orphaned stub |
| `student_insurance` | `entitlement_events` (DOM-OBL-001) | No — orphaned stub |
| `ticket_correlation_packs` (plural) | `ticket_correlation_pack` (singular, DOM-SUP-001) | No — empty duplicate |
| `audit_log` | `audit_events` + `chain_heads` (DOM-OPS-001) | No — orphaned stub |

---

## V. Remaining Unauthorized Tables (16)

These tables exist in the database but have no explicit permission in DOM-CORE-002 v1.6. Grouped by recommended action.

### Category A: Unique — Serve defined v2 operations, need DOM-CORE-002 amendment (7)

| # | Table | Owning Domain | Duty | Recommendation |
|---|---|---|---|---|
| 1 | `saved_adjustments` | DOM-CLASS-001 | Per-class saved payroll adjustment templates | Amend §2 |
| 2 | `error_events` | DOM-OPS-001 | Structured application error log | Amend §7 |
| 3 | `analytics_events` | DOM-ITR-001 | Raw analytics event stream | Amend §8 |
| 4 | `analytics_snapshots` | DOM-ITR-001 | Point-in-time analytics rollups | Amend §8 |
| 5 | `analytics_alerts` | DOM-ITR-001 | Analytics threshold alerts | Amend §8 |
| 6 | `actor_request_trace` | DOM-OPS-001 | Per-request actor context trace | Amend §7 |
| 7 | `teacher_onboarding` | DOM-IDEN-001 | Teacher first-run onboarding state | Amend §1 |

### Category B: Active legacy — Has runtime code dependencies, needs code migration before drop (5)

| # | Table | Active Code | Blocked By |
|---|---|---|---|
| 1 | `error_logs` | `ErrorLog` model, 15+ refs in `system_admin.py` | Must migrate to `error_events` first |
| 2 | `payroll_cache` | DOM-CORE-002 §2 explicitly prohibits persisted compute caches | Must remove cache reads/writes |
| 3 | `insurance_claims` | Legacy insurance system | Must remove insurance feature code |
| 4 | `insurance_enrollments` | Legacy insurance system | Must remove insurance feature code |
| 5 | `insurance_policies` | Legacy insurance system | Must remove insurance feature code |

### Category C: Unknown / needs investigation (4)

| # | Table | Notes |
|---|---|---|
| 1 | `economy_snapshot` | Possibly analytics; needs code search |
| 2 | `integrity_status` | Possibly observability; needs code search |
| 3 | `rent_items` | Possibly DOM-CLASS-001 child; needs code search |
| 4 | `rent_payments` | Possibly DOM-CLASS-001 child; needs code search |
| 5 | `rent_policy_versions` | Possibly DOM-ECON-003; needs code search |
| 6 | `rent_waivers` | Possibly DOM-CLASS-001 child; needs code search |

---

## VI. Changes Applied This Session

### DOM-CORE-002 v1.5 → v1.6

| Section | Change |
|---|---|
| §7 (Operations) | `audit_log` → `audit_events` + `chain_heads` |
| §9 (Support) | `ticket_correlation_packs` → `ticket_correlation_pack` (singular) |

### models_canonical.py

| Change | Detail |
|---|---|
| `AuditLog` → `AuditEvent` | Class renamed, `__tablename__` → `audit_events` |
| New: `ChainHead` | `__tablename__` = `chain_heads`, PK = `chain_scope` |
| `TicketCorrelationPack` | `__tablename__` → `ticket_correlation_pack` (singular), PK → `issue_id`, removed `TimestampMixin` |

### Migrations

| Revision | Description |
|---|---|
| `4bf6de0868a4` | Canonicalize recovery tables: seat_id, class_id, drop legacy columns |
| `5a1b2c3d4e5f` | Drop 4 legacy absorbed tables |

### test_smoke.py

- Imports: `AuditLog` → `AuditEvent, ChainHead`
- Model count assertion: 44 → 45

---

## VII. Recommended Next Steps

1. **Amend DOM-CORE-002 v1.7** for Category A tables (7 unique tables needing authorization)
2. **Code-migrate `error_logs`** → `error_events` (Category B, highest priority — 15+ active refs)
3. **Remove `payroll_cache`** reads/writes (explicitly prohibited by §2)
4. **Investigate Category C** tables and classify
5. **Plan legacy identity table drops** (prohibited tables — largest code migration effort)
