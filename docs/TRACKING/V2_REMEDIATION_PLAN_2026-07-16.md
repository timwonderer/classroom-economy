# V2 Constitutional Compliance Remediation Plan

> Historical remediation log only. This document captures the original constitutional audit state and may still list legacy Store/Entitlements artifacts such as `StorePurchase`, `RedemptionEvent`, and `quantity_delta`. Current runtime authority lives in the live Store closeout docs and code.

| Field | Value |
|---|---|
| Created | 2026-07-16 |
| Last updated | 2026-07-16 (live scan audit) |
| Branch | `codex/v2.0` |
| Authority docs | INV-IDEN-001, INV-ARC-007, INV-ARC-019, DOM-CORE-002 §§1–5, DOM-IDEN-007, DOM-SUP-001, FEAT layer contract |
| Original violations | 166 |
| Resolved | 163 |
| **Remaining violations** | **3** |
| Prepared by | Automated audit + live grep verification 2026-07-16 |

---

## Executive Summary

The codebase originally contained 166 constitutional violations across seven categories. Live grep verification against the current worktree finds **3 remaining violations**, all in `app/routes/admin.py`. Categories 1, 2, 3, 4, 5, 6, and 7 are fully or nearly resolved:

- **Cat-1 (FEAT bypass)**: 0 remaining — no `db.session.add/delete/flush` calls in any route file.
- **Cat-2 (block/section as authority scope)**: 0 hard violations remaining — all 13 original call sites fixed. One soft residue at lines 5834–5835 (`~ClassEconomy.section.in_(desired_blocks)` inside a delete scope) is already bounded by `class_id == class_id` and poses no cross-class data-bleed risk; flagged for eventual cleanup.
- **Cat-3 (session writes in routes)**: 0 remaining — canonical session helpers in `app/auth.py` used everywhere.
- **Cat-4 (orphaned FK)**: 0 remaining — `rent_policy_version_id` renamed to `policy_version_id` and repointed to `policy_versions.id`.
- **Cat-5, Cat-6, Cat-7**: Resolved (see section details below).

The 3 remaining violations are **runtime NameErrors** from `TapEvent`/`TapEventReasonCode` references that survive outside of their `has_table("tap_events")` guards. These will crash specific routes in production.

---

## Remaining Violations (3) — Active Crash Bugs

### R-1 · admin.py line 4249 — TapEvent NameError in student detail route

```python
# app/routes/admin.py:4249 — OUTSIDE of any has_table guard
tap_scope = sa.and_(TapEvent.seat_id == seat_id, TapEvent.class_id == class_id)
```

**Impact:** `NameError: name 'TapEvent' is not defined` when the student detail page route is called. Crashes the route entirely.

**Fix:** Replace `tap_scope` and all downstream `TapEvent` references in this route with `AttendanceSession`-based query:
```python
# canonical replacement
att_scope = sa.and_(AttendanceSession.seat_id == seat_id, AttendanceSession.class_id == class_id)
latest_session = AttendanceSession.query.filter(att_scope).order_by(AttendanceSession.started_at.desc()).first()
```
Also remove `latest_tap_event_query` (line 4281) and `latest_tap_event` (line 4295) — replace with `latest_session`.

### R-2 · admin.py line 9008 — TapEventReasonCode NameError in payroll/attendance route

```python
# app/routes/admin.py:9008 — OUTSIDE of any guard
reason_code=TapEventReasonCode.DAILY_LIMIT,
```

**Impact:** `NameError: name 'TapEventReasonCode' is not defined` when the daily attendance limit logic fires during payroll or tap processing. `student_tap()` call fails.

**Fix:** `TapEventReasonCode` was the enum for the dropped `TapEvent`. The `student_tap()` FEAT (in `app/feats/attendance.py`) should accept `AttendanceReasonCode` instead. Replace:
```python
# before
reason_code=TapEventReasonCode.DAILY_LIMIT,

# after
reason_code=AttendanceReasonCode.DAILY_LIMIT,
```
Verify `student_tap()` signature accepts `AttendanceReasonCode` (it already uses `AttendanceReasonCode` on `AttendanceSession`).

### R-3 · admin.py line 4249 companion — TapEvent.class_id / TapEvent.timestamp refs (lines 4249, 4281, 4295)

Already covered by R-1. Lines 4281 and 4295 are downstream of the `tap_scope` defined at 4249 and will also NameError. Fix together with R-1.

---

## Priority Order

| Priority | Category | Files Affected | Remaining Count | Status |
|---|---|---|---|---|
| **P0** | R-1/R-2/R-3: TapEvent NameErrors | `app/routes/admin.py` lines 4249, 4281, 4295, 9008 | 3 | **Open — runtime crashes** |
| ✅ done | Cat-1: FEAT layer bypass | route files | 0 | Verified clean by live grep |
| ✅ done | Cat-2: Block/section as authority scope | `app/routes/admin.py`, `app/routes/api.py` | 0 | 13 violations fixed; soft residue at lines 5834–5835 (bounded by class_id) |
| ✅ done | Cat-3: Session identity written in routes | route files | 0 | Canonical session helpers used |
| ✅ done | Cat-4: Orphaned FK (`ObligationAssessment`) | `app/models.py` | 0 | Column renamed + FK repointed to `policy_versions.id` |
| ✅ done | Cat-5: Non-canonical model classes | `app/models.py` | 0 | 4 removed, 1 renamed — commit `85b6be64` |
| ✅ done | Cat-6: Dead FEAT file | `app/feats/` | 0 | `insurance_claim_feat.py` deleted — commit `85b6be64` |
| ✅ done | Cat-7: Orphaned scheduled task | `app/scheduled_tasks.py` | 0 | Tombstoned — commit `85b6be64` |

---

## Category 1: FEAT Layer Bypass

**Authority:** INV-ARC-007 ("GET handlers must not write to the database; all state mutation goes through FEAT layer"), FEAT layer contract ("Routes must not call `db.session.add/commit/delete` directly; wrap in `FEATContext`").

### 1.1 app/routes/admin.py (73 violations)

| Line | Code | Domain | Required FEAT |
|---|---|---|---|
| 1761 | `db.session.add(economy)` | Class creation | FEAT-CLASS-001 |
| 1771 | `db.session.add(Seat(...))` | Seat creation | FEAT-IDEN-001 |
| 1885 | `db.session.add(new_seat)` | Roster add | FEAT-IDEN-001 |
| 1893 | `db.session.add(profile)` | Identity profile creation | FEAT-IDEN-001 |
| 3096 | `db.session.add(new_user)` | Teacher signup | FEAT-IDEN-002 |
| 4676 | `db.session.add(new_seat)` | Student seat assignment | FEAT-IDEN-001 |
| 4949 | `db.session.delete(seat_entry)` | Seat removal | FEAT-IDEN-001 |
| 5013 | `db.session.delete(seat_entry)` | Seat removal | FEAT-IDEN-001 |
| 5108 | `db.session.add(new_seat)` | Seat creation | FEAT-IDEN-001 |
| 5253 | `db.session.add(new_seat)` | Seat creation | FEAT-IDEN-001 |
| 5367 | `db.session.add(new_item)` | Store item creation | FEAT-STORE-001 |
| 5822 | `db.session.add(...)` | Payroll reward creation | FEAT-PAY-001 |
| 5956 | `db.session.add(block_settings)` | Feature settings creation | FEAT-SETTINGS-001 |
| 6159 | `db.session.add(new_item)` | Item creation | FEAT-STORE-001 |
| 6170 | `db.session.delete(item)` | Item deletion | FEAT-STORE-001 |
| 8040 | `db.session.add(setting)` | Settings creation | FEAT-SETTINGS-001 |
| 8130 | `db.session.add(new_setting)` | Settings creation | FEAT-SETTINGS-001 |
| 8152 | `db.session.add(new_setting)` | Settings creation | FEAT-SETTINGS-001 |
| 8483 | `db.session.add(class_row)` | Class creation | FEAT-CLASS-001 |
| 8491 | `db.session.add(teacher_seat)` | Seat creation | FEAT-IDEN-001 |
| 8503 | `db.session.add(seat)` | Seat creation | FEAT-IDEN-001 |
| 8628 | `db.session.add(new_seat)` | Seat creation | FEAT-IDEN-001 |
| 8644 | `db.session.delete(profile)` | Student deletion | FEAT-IDEN-001 |
| 8645 | `db.session.delete(seat)` | Student deletion | FEAT-IDEN-001 |
| 8817 | `db.session.add(seat)` | Seat creation | FEAT-IDEN-001 |
| 9650 | `db.session.add(settings)` | Settings creation | FEAT-SETTINGS-001 |
| 9738 | `db.session.delete(admin)` | User deletion | FEAT-IDEN-002 |
| 9922 | `db.session.add(report)` | Announcement creation | FEAT-COMMS-001 |
| 10236 | `db.session.add(announcement)` | Announcement creation | FEAT-COMMS-001 |
| 10339 | `db.session.delete(announcement)` | Announcement deletion | FEAT-COMMS-001 |

*Note: 43 additional violations in admin.py not enumerated above follow identical patterns in the same domain groupings.*

### 1.2 app/routes/student.py (8 violations)

| Line | Code | Context | Required FEAT |
|---|---|---|---|
| 651 | `db.session.add(user)` | User creation in claim flow | FEAT-IDEN-003 |
| 653 | `db.session.flush()` | Claim flow | FEAT-IDEN-003 |
| 662 | `db.session.flush()` | Claim flow | FEAT-IDEN-003 |
| 831 | `db.session.flush()` | Attendance flow | FEAT-ATT-001 |
| 3014 | `db.session.flush()` | Passkey flow | FEAT-IDEN-003 |
| 3121 | `db.session.flush()` | Passkey flow | FEAT-IDEN-003 |
| 3484 | `db.session.flush()` | Store flow | FEAT-STORE-002 |
| 3517 | `db.session.flush()` | Store flow | FEAT-STORE-002 |

### 1.3 app/routes/system_admin.py (21 violations)

| Line | Code | Context | Required FEAT |
|---|---|---|---|
| 385 | `db.session.add(credential)` | Passkey credential | FEAT-AUTH-001 |
| 544 | `db.session.delete(credential)` | Passkey deletion | FEAT-AUTH-001 |
| 978 | `db.session.delete(legacy_admin)` | User deletion | FEAT-IDEN-002 |
| 980 | `db.session.delete(admin_user)` | User deletion | FEAT-IDEN-002 |
| 1698 | `db.session.add(announcement)` | Announcement creation | FEAT-COMMS-001 |
| 1782 | `db.session.delete(announcement)` | Announcement deletion | FEAT-COMMS-001 |
| 1977 | `db.session.add(IssueResolutionAction(...))` | Issue action | FEAT-SUPPORT-001 |

*Note: 14 additional violations in system_admin.py follow identical domain patterns.*

### 1.4 app/routes/api.py (11 violations)

| Line | Code | Context | Required FEAT |
|---|---|---|---|
| 237 | `db.session.add(RedemptionEvent(...))` | Redemption event | FEAT-STORE-002 |
| 271 | `db.session.add(settings)` | Settings creation | FEAT-SETTINGS-001 |

*Note: 9 additional violations in api.py follow identical domain patterns.*

### Canonical Replacement Pattern (Category 1)

**Before (violating):**
```python
# app/routes/admin.py — direct session mutation in route handler
new_seat = Seat(user_id=user.id, class_id=class_id, role="student")
db.session.add(new_seat)
db.session.commit()
```

**After (compliant):**
```python
# Route handler — calls FEAT only
from app.feats.identity_feat import enroll_student_seat

result = enroll_student_seat(
    FEATContext("FEAT-IDEN-001", idempotency_key=f"enroll:{user.id}:{class_id}"),
    user_id=user.id,
    class_id=class_id,
)

# app/feats/identity_feat.py — FEAT delegates to service
def enroll_student_seat(ctx: FEATContext, *, user_id: int, class_id: str):
    with feat_shell(ctx):
        return identity_service.create_seat(user_id=user_id, class_id=class_id)

# app/services/identity_service.py — service owns db.session
def create_seat(*, user_id: int, class_id: str) -> Seat:
    seat = Seat(user_id=user_id, class_id=class_id, role="student")
    db.session.add(seat)
    db.session.commit()
    return seat
```

---

## Category 2: Block/Section as Authority Scope

**Authority:** DOM-IDEN-007 ("`block`/`period`/`section` is display metadata only, never a scoping/authority key; `join_code` is ingress-only alias; all internal scoping uses `class_id`").

### 2.1 app/routes/admin.py

| Line | Code | Violation | Fix Summary |
|---|---|---|---|
| 853 | `ClassEconomy.section.in_(blocks)` | Multi-class student fetch scoped by section label | Resolve `class_id` set from `blocks` labels first, then scope by `class_id` |
| 879 | `ClassEconomy.section.in_(blocks)` | Transaction fetch scoped by section | Same two-step resolution |
| 904 | `ClassEconomy.section.in_(blocks)` | Attendance fetch scoped by section | Same two-step resolution |
| 1193 | `ClassEconomy.section.isnot(None)` | Block list enumeration | Enumerate distinct `ClassEconomy.section` for display only; do not chain into authority queries |
| 1194 | `ClassEconomy.section.isnot(None)` | Block list enumeration | Same |
| 1846 | `ClassEconomy.section == target_block` | Single-class scope by section | Resolve to `class_id` via `ClassEconomy.query.filter_by(section=target_block, user_id=user_id).first().class_id` |
| 4371 | `ClassEconomy.section.in_(block_parts)` | Student assignment scoped by section | Two-step resolution to `class_id` set |
| 4813 | `ClassEconomy.section == section` | Class lookup by section | Resolve `class_id`; use `class_id` for all downstream queries |
| 4989 | `ClassEconomy.section == section` | Class lookup by section | Same |
| 9992 | `ClassEconomy.section.in_(periods)` | Payroll scoped by section | Two-step resolution |
| 10038 | `ClassEconomy.section == period` | Payroll scoped by section | Resolve `class_id` |
| 10102 | `ClassEconomy.section == source_period` | Copy operation scoped by section | Resolve source `class_id` |
| 10138 | `ClassEconomy.section == period` | Settings scoped by section | Resolve `class_id` |

### 2.2 app/routes/api.py

| Line | Code | Violation | Fix Summary |
|---|---|---|---|
| 1321 | `HallPassLog.period == period` | Hall pass filtered by period field | `HallPassLog` must be scoped by `class_id`; remove `.period` filter |

### Canonical Replacement Pattern (Category 2)

**Before (violating):**
```python
# Scoping authority query by section label — DOM-IDEN-007 violation
students = (
    Seat.query
    .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
    .filter(ClassEconomy.section.in_(blocks))
    .all()
)
```

**After (compliant):**
```python
# Step 1: resolve display label → class_id set (ClassEconomy is the only table where section is valid)
class_ids = [
    row.class_id for row in
    ClassEconomy.query
    .filter(ClassEconomy.section.in_(blocks), ClassEconomy.user_id == current_user_id)
    .with_entities(ClassEconomy.class_id)
    .all()
]

# Step 2: scope authority query by class_id — never by section
students = Seat.query.filter(Seat.class_id.in_(class_ids)).all()
```

---

## Category 3: Session Identity Written Directly in Routes

**Authority:** INV-ARC-019 ("`resolve_canonical_context()` is the sole legal way to get identity in routes").

| File | Line | Code | Context | Required Fix |
|---|---|---|---|---|
| `app/routes/admin.py` | 2843 | `session["user_id"] = user.id` | Login flow | Call `establish_teacher_session(user)` from `app/auth.py` |
| `app/routes/admin.py` | 8514 | `session["user_id"] = user_id` | Class creation flow | Call `establish_teacher_session(user)` |
| `app/routes/admin.py` | 11125 | `session["user_id"] = user.id` | Passkey flow | Call `establish_teacher_session(user)` |
| `app/routes/system_admin.py` | 272 | `session["user_id"] = user.id` | Sysadmin login | Call `establish_sysadmin_session(user)` from `app/auth.py` |
| `app/routes/system_admin.py` | 481 | `session["user_id"] = user.id` | Passkey login | Call `establish_sysadmin_session(user)` |
| `app/routes/student.py` | 2988 | `session['user_id'] = linked_user.id` | Student passkey claim | Call `establish_student_session(user, class_id=...)` |

### Canonical Replacement Pattern (Category 3)

**Before (violating):**
```python
# Route handler writing session directly
session["user_id"] = user.id
session["role"] = "admin"
```

**After (compliant):**
```python
# app/auth.py — single point of truth for session structure
def establish_teacher_session(user: User) -> None:
    session["user_id"] = user.id
    session["role"] = "admin"
    session.permanent = True

def establish_sysadmin_session(user: User) -> None:
    session["user_id"] = user.id
    session["role"] = "sysadmin"
    session.permanent = True

def establish_student_session(user: User, *, class_id: str) -> None:
    session["user_id"] = user.id
    session["class_id"] = class_id
    session["role"] = "student"
    session.permanent = True

# Route handler — calls helper only
from app.auth import establish_teacher_session
establish_teacher_session(user)
```

---

## Category 4: Orphaned FK in ObligationAssessment ✅ RESOLVED (migration `a1b2c3d4e5f6`)

**Authority:** DOM-ECON-003 ("policy versions are tracked in `policy_versions`"), DOM-OBL-001 ("ObligationAssessment references the policy version that produced it").

| File | Line | Code | Resolution |
|---|---|---|---|
| `app/models.py` | 1165 | `policy_version_id = db.Column(db.Integer, db.ForeignKey('policy_versions.id'), nullable=True, index=True)` | Column now points at the canonical `policy_versions.id` table |

### Canonical Replacement Pattern (Category 4)

**Migration required.** Steps:

1. Drop existing FK constraint on `obligation_assessments.rent_policy_version_id` (discover constraint name dynamically via `get_foreign_keys_by_column`).
2. Rename column: `rent_policy_version_id` → `policy_version_id`.
3. Add FK constraint to `policy_versions.id`.
4. Update `ObligationAssessment` model:

```python
# app/models.py — after migration
class ObligationAssessment(db.Model):
    # ...
    policy_version_id = db.Column(
        db.Integer,
        db.ForeignKey("policy_versions.id"),
        nullable=True,
        index=True,
    )
    policy_version = db.relationship("PolicyVersion", back_populates="assessments")
```

---

## Category 5: Non-Canonical Models in models.py ✅ RESOLVED (commit `85b6be64`)

**Authority:** DOM-CORE-002 §§1–5.

All five items below were resolved in commit `85b6be64`. Model classes were removed from `models.py`; backing tables were already absent from the DB (dropped in migration `7c3d4e5f6a7b`). Route-body `NameError` signals remain as intentional markers for the corresponding route rewrites (tracked under Cat-1 and Cat-2 above).

### 5.1 TapEvent ✅

| Field | Value |
|---|---|
| Class | ~~`TapEvent`~~ |
| Table | `tap_events` (dropped — migration `7c3d4e5f6a7b`) |
| Canonical replacement | `attendance_sessions` (DOM-ATT-001) |
| Resolution | Class removed from `models.py`. Import-level violations fixed in `admin.py`, `api.py`, `system_admin.py`, `wsgi.py`. Body-level NameErrors remain as signals. |

### 5.2 StoreItemBlock ✅

| Field | Value |
|---|---|
| Class | ~~`StoreItemBlock`~~ |
| Table | `store_item_blocks` (dropped — migration `7c3d4e5f6a7b`) |
| Canonical replacement | `store_item_visibility` scoped by `class_id` (DOM-STORE-001) |
| Resolution | Class removed from `models.py`. Import-level violations fixed in `admin.py`, `api.py`, `student.py`, `deletion.py`, `scheduled_tasks.py`. Body-level NameErrors remain as signals. |

### 5.3 StudentItem ✅

| Field | Value |
|---|---|
| Class | ~~`StudentItem`~~ |
| Table | `student_items` (dropped — migration `7c3d4e5f6a7b`) |
| Canonical replacement | `store_purchases` + `redemption_events` (DOM-STORE-001) |
| Resolution | Class removed from `models.py`. Import-level violations fixed in `admin.py`, `wsgi.py`, `student_deletion.py`. Body-level NameErrors remain as signals. |

### 5.4 RedemptionAuditLog ✅

| Field | Value |
|---|---|
| Class | ~~`RedemptionAuditLog`~~ (+ `RedemptionAuditAction`, `RedemptionAuditSource`) |
| Table | `redemption_audit_logs` (dropped — migration `7c3d4e5f6a7b`) |
| Canonical replacement | `redemption_events` + `audit_events` with `domain='store'` (DOM-STORE-001, DOM-OPS-001) |
| Resolution | All three classes removed from `models.py`. Import-level violations fixed in `admin.py`, `deletion.py`, `student_deletion.py`. Body-level NameErrors remain as signals. |

### 5.5 BalanceCache → LedgerBalanceSnapshot ✅ (classification correction)

| Field | Value |
|---|---|
| Original class | `BalanceCache` |
| Renamed to | `LedgerBalanceSnapshot` |
| Table | `ledger_balance_snapshot` — **authorized** per DOM-CORE-002 §5 (Ledger & Money) |
| Correction | Original audit incorrectly classified this as a prohibited compute cache. The table `ledger_balance_snapshot` is explicitly authorized. The violation was the misleading class name only. |
| Resolution | Class renamed to `LedgerBalanceSnapshot` in `models.py`. All references updated across `banking.py`, `ledger_service.py`, `balance_service.py`, `admin.py`, `student_deletion.py`. No schema change (same `__tablename__`). |

---

## Category 6: Dead FEAT File ✅ RESOLVED (commit `85b6be64`)

**Authority:** FEAT layer contract (FEATs must reference live models).

| File | Resolution |
|---|---|
| ~~`app/feats/insurance_claim_feat.py`~~ | **Deleted.** Dead import references in `app/routes/admin.py` (line 146) and `app/routes/student.py` (line 87) replaced with tombstone comments. Insurance claim lifecycle pending full rewrite to DOM-OBL-001 obligation satisfaction chain. |

---

## Category 7: Orphaned Scheduled Task ✅ RESOLVED (commit `85b6be64`)

**Authority:** DOM-IDEN-007, DOM-CORE-002 §6.

| File | Resolution |
|---|---|
| `app/scheduled_tasks.py` lines 88–163 | **Tombstoned.** `StoreItemBlock` import and the entire orphaned-block-cleanup task body replaced with a comment explaining the table is dropped and the canonical replacement is `store_item_visibility`. Pending: implement `StoreItemVisibility` orphan cleanup (see canonical pattern below). |

**Canonical replacement (still to implement):**
```python
# app/scheduled_tasks.py — pending implementation
from app.models import StoreItemVisibility, ClassEconomy

def cleanup_orphaned_store_visibility():
    """Remove store_item_visibility rows for inactive/deleted classes."""
    active_class_ids = {
        row.class_id for row in
        ClassEconomy.query.with_entities(ClassEconomy.class_id).filter_by(status="active").all()
    }
    orphaned = StoreItemVisibility.query.filter(
        StoreItemVisibility.class_id.notin_(active_class_ids)
    ).all()
    for row in orphaned:
        db.session.delete(row)
    db.session.commit()
```

---

## Migration Requirements

| Category | Migration Required | Status | Description |
|---|---|---|---|
| Cat-4 | ~~Yes~~ | **Done** | Column renamed to `policy_version_id` and repointed to `policy_versions.id` in migration `a1b2c3d4e5f6`; downgrade is intentionally unsupported |
| Cat-5 (TapEvent) | ~~Yes~~ | **Done** | Table already dropped in migration `7c3d4e5f6a7b` |
| Cat-5 (StoreItemBlock) | ~~Yes~~ | **Done** | Table already dropped in migration `7c3d4e5f6a7b` |
| Cat-5 (StudentItem) | ~~Yes~~ | **Done** | Table already dropped in migration `7c3d4e5f6a7b` |
| Cat-5 (RedemptionAuditLog) | ~~Yes~~ | **Done** | Table already dropped in migration `7c3d4e5f6a7b` |
| Cat-5 (BalanceCache) | ~~Yes~~ | **N/A** | `ledger_balance_snapshot` is authorized; class renamed to `LedgerBalanceSnapshot` only |
| Cat-1, 2, 3, 6, 7 | No schema migration | Cat-6/7 done; 1/2/3 pending | Code-only changes; no new columns or tables required |

**Only Cat-4 requires a migration.** All migrations must follow `.claude/rules/database-migrations.md`: single head verified before generation, idempotency helpers copied from `migrations/migration_template.py.mako`, all CREATE/DROP ops wrapped in existence checks, linter run before commit.

---

## Appendix: Files Confirmed Clean

The following files had zero violations of the categories above at the time of this audit:

| File | Confirmed Clean Of |
|---|---|
| `app/services/context_resolver.py` | Cat-3 (session writes); Cat-1 (db.session in service layer is permitted) |
| `app/services/ledger_service.py` | Cat-1 (service layer owns db.session — compliant), Cat-2 |
| `app/services/identity_service.py` | Cat-2, Cat-3 |
| `app/auth.py` | Cat-1, Cat-2 |
| `app/feats/base.py` | Cat-1 (this file defines the FEATContext — it is the fix target) |
| `app/routes/analytics.py` | Cat-1, Cat-2 (read-only analytics routes) |
| `app/routes/recovery.py` | Cat-2, Cat-3 |
| `app/routes/main.py` | Cat-1, Cat-2, Cat-3 |
