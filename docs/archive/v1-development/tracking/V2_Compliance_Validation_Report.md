# V2 Compliance Validation Report — `codex/v2.0`

**Date:** 2026-05-09
**Branch:** `codex/v2.0`
**Reference:** `docs/TRACKING/V2_Full_compliance_migration_plan.md`

---

## Executive Summary

Of 16 migration plan status claims validated, **13 are PASS**, **2 are PARTIAL**, and **1 is a critical FAIL**. There are **3 P0-severity issues** (runtime crashes), **5 P1-severity INV-ARC-007 violations**, and **3 P2-severity cleanup items**.

---

## Wave 3C Status Validation

| Claim | Status | Notes |
|---|---|---|
| 3C.2–3C.6: Auth helpers (`get_current_seat`, `get_current_class_id`, `get_current_user`, `require_seat_context`) | ✅ PASS | All four exist in `app/auth.py:311–414` |
| 3C.8: Hall pass class-authoritative, fail-closed | ⚠️ PARTIAL | Backend scoping correct; GET write violation remains (see P1-2) |
| 3C.9/3C.9-B: Store scope class-authoritative | ✅ PASS | `app/services/store_service.py` uses `seat.class_id` throughout |
| 3C.10-B: Rent cycle functions, coverage windows, idempotency key, rent exemption | ⚠️ PARTIAL | Functions and model fields exist — **`FEAT-OBL-002` not registered in `FEAT_REGISTRY`** (see P0-1) |
| 3C.10-T/C: Temporal helpers, calendar-based insurance | ✅ PASS | All three helpers in `app/utils/time.py:209,235,257`; no raw `datetime.now()` in codebase |
| 3C.11: Insurance admin queries class-scoped | ✅ PASS | `InsurancePolicy.class_id.in_(...)` used across 6 query sites |
| 3C.12-A/B: Payroll scope bridge | ✅ PASS | `app/payroll.py` resolves `class_id` before querying `PayrollSettings` |
| 3C.12-C: Hall pass/students templates purged | ✅ PASS | Backend passes `None` for `requested_join_code`; no switching scripts in templates |
| 3C.12-D: Payroll/store/banking/support templates purged | ✅ PASS | All confirmed via backend route inspection |
| 3C.12-E: Hall pass setup/insurance/rent/banking templates purged | ✅ PASS | Backend confirmed; no `settings_block` switching on page load |
| 3C.12-F: Feature toggle authority, `@admin_bp.before_request`, `admin_feature_disabled.html` | ✅ PASS | `ADMIN_FEATURE_ENDPOINTS` maps 7 endpoints; student gets hard 404; template exists |
| 3C.12-G: Banking/payroll/analytics by `class_id` | ✅ PASS | All four paths resolve and query by `class_id` |
| 3C.12-H: Economy rebalance/cleanup by `class_id` | ✅ PASS | `FeatureSettings.class_id.in_(...)` and class ID subqueries confirmed |
| 3C.12-I: `process_expired_collective_goals` removed from `GET /admin/store` | ✅ PASS | No calls in `admin.py`; guardrail test in `test_v2_authority_guardrails.py` asserts this |
| 3C.12-J: Store mutations wrapped in `FEATContext`; `flush()` in store utility | ✅ PASS | All three POSTs use `FEATContext`; `flush()` confirmed at `app/utils/store.py:134` |
| Wave 5 FEAT atomicity enforcement | ✅ PASS | `init_feat_enforcement()` active; `before_flush`/`before_commit` hooks raise `FEATContextError` |

---

## P0 — Runtime Crash / Data Correctness

### P0-1 · `FEAT-OBL-002` unregistered in `FEAT_REGISTRY`
**Files:** `app/feats/rent_cycle_feat.py:20`, `app/feats/base.py:103–108`

`execute_scheduled_rent_charge` is decorated with `@feat_shell("FEAT-OBL-002")`, but `FEAT-OBL-002` does not appear in `FEAT_REGISTRY` in `base.py` (only `FEAT-OBL-001` is registered). `FEATContext.__init__` raises:

```
FEATContextError: FATAL: FEAT code FEAT-OBL-002 is not in the canonical registry.
```

Rent cycle execution is completely broken in any non-test environment. Tests in `tests/test_scheduled_tasks_rent_cycle.py` monkeypatch `execute_scheduled_rent_charge`, which masks this failure.

**Wave plan claim:** Wave 3C.10-B marked complete.
**Invariant violated:** FEAT-CORE-000

---

### P0-2 · `GET /admin/economy-health` mutates `FeatureSettings` outside FEAT
**Files:** `app/routes/admin.py:8277–8283`, `app/utils/economy_rebalance.py:148`

`activate_due_rebalances(admin_id)` is called inside the GET handler, mutating `FeatureSettings.economy_pending_rebalance_json` rows in a loop, then calling `db.session.commit()` outside any `FEATContext`. With FEAT enforcement active and dirty state present, this raises `FEATContextError` and crashes with a 500.

**Invariants violated:** INV-ARC-007, FEAT-CORE-000

---

### P0-3 · `GET /admin/banking` creates `BankingSettings` and commits outside FEAT
**File:** `app/routes/admin.py:10714–10721`

When no settings exist for the resolved block, the handler creates a default `BankingSettings` object and calls `db.session.commit()` directly. Same crash risk as P0-2.

**Invariants violated:** INV-ARC-007, FEAT-CORE-000

---

## P1 — Architecture Violation (INV-ARC-007: GET → DB write)

These are confirmed GET routes that commit to the database outside any `FEATContext`. With FEAT enforcement active they will crash if there is dirty state; without dirty state they still violate INV-ARC-007 structurally.

| # | Route | File:Line | What it writes |
|---|---|---|---|
| P1-1 | `GET /admin/recovery-status` | `admin.py:3577` | Sets `recovery_request.status = 'expired'` and commits |
| P1-2 | `GET /admin/hall-pass` | `admin.py:8095` | Lazy-generates `teacher.hall_pass_verify_token` and commits — **claimed fixed in 3C.8** |
| P1-3 | `GET /admin/issues/<ref>` | `admin.py:12592` | Calls `update_issue_status()`, sets `teacher_reviewed_at`, commits |
| P1-4 | `GET /student/setup-complete` | `student.py:4045` | Sets `student.has_completed_setup = True` and commits |
| P1-5 | `GET /student/dashboard` (exception handler) | `student.py:~1160` | Flushes a `ClassEconomy` creation in the `AccessScopeDenied` handler outside FEAT — latent crash for students with missing class scope |

---

## P2 — Cleanup / Non-Blocking

### P2-1 · Redundant bare `db.session.commit()` in `run_rent_cycle_for_class`
**File:** `app/scheduled_tasks.py:258`

An outer `db.session.commit()` fires after each `execute_scheduled_rent_charge` call. Since `feat_shell` already commits and exits before returning, this fires on a clean session (no dirty state) and does not crash — but it is architecturally incorrect. Once P0-1 is resolved, this outer commit should be removed.

### P2-2 · Residual INV-ARC-014 label-based filter: `Student.block == block_q`
**File:** `app/routes/admin.py:10786`

```python
query = query.filter(Student.block == block_q)
```

`block_q` is taken directly from `request.args.get('block')` and used as a raw DB filter. The query is teacher-scoped first so cross-tenant leakage is not a concern, but this contradicts INV-ARC-014's prohibition on label-based routing as a control key.

### P2-3 · Analytics engine uses `teacher_id` for student list queries
**File:** `app/utils/analytics_engine.py:91–122`

The analytics computation backend still uses `teacher_id` for student roster queries. Wave 3C.12-G is marked complete for analytics *settings* lookup (payroll settings by `class_id`), but the student list queries in this range remain teacher-scoped — a DOM-CLASS-001 partial violation.

---

## Summary by Invariant

| Invariant | Status | Violations |
|---|---|---|
| **FEAT-CORE-000** (all mutation via registered FEAT) | ❌ FAILING | P0-1, P0-2, P0-3, P1-1 through P1-5 |
| **INV-ARC-007** (no GET writes) | ❌ FAILING | P0-2, P0-3, P1-1, P1-2, P1-3, P1-4, P1-5 |
| **INV-ARC-014** (no label-based routing) | ⚠️ PARTIAL | P2-2 (low severity) |
| **INV-ARC-015** (class-local time) | ✅ COMPLIANT | No raw `datetime.now()` found anywhere in `app/` |
| **DOM-CORE-002** (canonical schema) | ✅ COMPLIANT (so far) | Waves 1–2 complete; Waves 3–12 schema changes not yet executed |
| **DOM-CLASS-001** (class-scoped settings) | ⚠️ PARTIAL | P2-3 (analytics student roster still teacher-scoped) |

---

## Recommended Immediate Actions (before Wave 4)

1. **Register `FEAT-OBL-002`** in `FEAT_REGISTRY` in `app/feats/base.py` — rent cycle execution is broken in all non-test environments (P0-1)
2. **Wrap `activate_due_rebalances`** in a FEAT or convert economy-health GET to a POST-triggered action (P0-2)
3. **Wrap the `BankingSettings` lazy creation** in `admin.py:10714` in a FEAT or pre-create on class setup (P0-3)
4. **Remove the hall pass token lazy-write** from `GET /admin/hall-pass` — generate on POST or at class setup time (P1-2; retroactively closes the 3C.8 partial)
5. **Convert remaining GET-write routes** (recovery-status, issues, setup-complete, dashboard exception handler) to FEAT-wrapped POST or initialization paths (P1-1, P1-3, P1-4, P1-5)
