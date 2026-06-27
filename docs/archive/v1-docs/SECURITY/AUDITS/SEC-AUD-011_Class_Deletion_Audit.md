# Class Deletion Audit

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SEC-AUD-011| 1.1 | 2026-03-08 | 1.0 |Normative|

**Date:** 2026-02-21
**Author:** Claude (automated audit)
**Severity:** Mixed — one confirmed data bug (P1), several inconsistency and UX risks (P2/P3)
**Status:** Open — remediation pending

---

## Executive Summary

The application has **four distinct paths** that can delete or partially delete a class period (TeacherBlock). They were built at different times, by different concerns, and they behave differently in every dimension that matters: what gets deleted, what survives, what the user is warned about, and whether referential integrity is enforced.

The most serious individual finding is a confirmed **BalanceCache orphaning bug**: the `balance_cache` table stores balances scoped by `join_code` but is never cleaned up by any deletion path, including the most thorough one (`_hard_delete_join_code_scope`). Orphaned cache rows can cause stale balance reads if a join code is ever reused or if the cache is queried without verifying the class still exists.

Beyond that single bug, the structural concern is that these four paths are not aligned. A teacher deleting their own class triggers a robust, two-step confirmation and cleans up 17+ tables. A system admin deleting the same class through a different UI path leaves all financial data intact and shows only a one-line browser `confirm()` dialog — with no mention that the behavior is intentionally different from the teacher-initiated path. Neither path warns users or offers an export.

---

## The Four Deletion Paths

### Path 1: Teacher-initiated join-code deletion

| | |
|---|---|
| **Route** | `POST /admin/join-code/delete` (alias: `DELETE /admin/join-code`) |
| **File** | `app/routes/admin.py:3056–3082` |
| **Auth** | `@admin_required` — teacher must own the join code |
| **Core logic** | `_hard_delete_join_code_scope(join_code, teacher_id)` (`admin.py:327–488`) |

This is the primary, most destructive path. The route verifies ownership by querying `TeacherBlock` for the authenticated teacher, then delegates to `_hard_delete_join_code_scope`, which runs 17 deletion statements in sequence before committing.

**Confirmation UI** (`templates/admin_students.html:1458–1507`):
- Two-step: browser `confirm()` dialog with an itemized data-loss warning, followed by a typed confirmation prompt requiring the teacher to type `DELETE BLOCK <NAME>` exactly.
- This is the only path with a substantive user warning.

**What gets deleted:**

| Table | Notes |
|---|---|
| `RedemptionAuditLog` | For `StudentItem` records in this join_code |
| `StudentItem` | scoped by `join_code` |
| `TapEvent` | scoped by `join_code` |
| `HallPassLog` | scoped by `join_code` |
| `RentPayment` | scoped by `join_code` |
| `StudentBlock` | scoped by `join_code` |
| `AnalyticsSnapshot` | scoped by `join_code` |
| `AnalyticsEvent` | scoped by `join_code` |
| `Announcement` | filtered by `teacher_id + join_code` |
| `IssueResolutionAction` | for Issues in this join_code |
| `Issue` | scoped by `join_code` |
| `InsuranceClaim` | tied to StudentInsurance or Transaction in this join_code |
| `StudentInsurance` | scoped by `join_code` |
| `Transaction` | via `_delete_transactions_for_join_code(join_code_deletion=True)` |
| `StoreItemBlock` | entries for this class's block names |
| `StoreItem` | only if the item's only visibility was to this block |
| `TeacherBlock` | filtered by `teacher_id + join_code` |
| `Student` | orphans only (no remaining `TeacherBlock` rows in any join_code) |
| `StudentTeacher` | for the same orphaned students |

**What is NOT deleted:**

| Table | Notes |
|---|---|
| `BalanceCache` | Has `join_code` column — **BUG: never deleted here** |
| `PayrollSettings` | Scoped by `teacher_id + block` name, not join_code — survives |
| `RentSettings` | Scoped by `teacher_id + block` name — survives |
| `BankingSettings` | Scoped by `teacher_id` — survives (expected) |
| `InsurancePolicyBlock` | Scoped by `block` name, not join_code — survives |
| `InsurancePolicy` | Scoped by `teacher_id` — survives (expected) |

---

### Path 2: Legacy block-name deletion (wrapper for Path 1)

| | |
|---|---|
| **Route** | `POST /admin/students/delete-block` |
| **File** | `app/routes/admin.py:3007–3053` |
| **Auth** | `@admin_required` |
| **Core logic** | Resolves block name → join_code(s), then calls `_hard_delete_join_code_scope` |

This route was built as a backwards-compatible wrapper for callers that know a block name but not a join code. It looks up `TeacherBlock` rows matching the authenticated teacher and block name, then:

- If 0 join codes found: returns success (idempotent)
- If 2+ join codes found: returns an error — caller must specify join code explicitly
- If exactly 1 join code: calls `_hard_delete_join_code_scope`, then deletes any remaining unclaimed seats in the same block

Because it ultimately calls Path 1's core function, **the deletion scope is identical to Path 1**. The same `BalanceCache` orphan bug applies.

**Confirmation UI** (`templates/admin_students.html:1458–1507`):
- Identical to Path 1 — same two-step browser confirm + typed confirmation. `deleteEntireBlock()` in the template calls this route.

---

### Path 3: System admin period deletion (soft delete)

| | |
|---|---|
| **Route** | `POST /sysadmin/delete-period/<admin_id>/<period>` |
| **File** | `app/routes/system_admin.py:1184–1273` |
| **Auth** | `@system_admin_required` |
| **Authorization gate** | Teacher must have a pending `DeletionRequest` for this period, OR have been inactive for 6+ months |

This path is intentionally a soft delete — it removes the class from the roster without touching any financial or activity history. However, it uses the **legacy `Student.block` field** to find enrolled students rather than `TeacherBlock.join_code`. This means it cannot clean up join_code-scoped records even if it wanted to.

**What gets deleted:**

| Table | Notes |
|---|---|
| `TeacherBlock` | Rows where `teacher_id == admin.id AND block == period` |
| `StudentTeacher` | Only if the student has no other periods with this teacher |

**What is NOT deleted (intentionally, but without documentation):**

All join_code-scoped financial data: `Transaction`, `TapEvent`, `HallPassLog`, `RentPayment`, `StudentBlock`, `StudentInsurance`, `InsuranceClaim`, `StudentItem`, `AnalyticsEvent`, `AnalyticsSnapshot`, `Issue`, `BalanceCache`, `Announcement` — everything.

**Confirmation UI** (`templates/system_admin_manage_teachers.html:450–471`):
- Single `confirm()` dialog: `"Delete period PERIOD for username? This will remove N student link(s)."`
- No mention of what is preserved versus deleted.
- No warning that this is a different, lighter deletion than the teacher-facing path.
- No typed confirmation requirement.

**Key inconsistency with Path 1:** If a teacher requests their class be deleted (triggering this path via a sysadmin), they get a soft delete with no data removal. If they delete their own class from the teacher UI (Path 1), they get a hard delete of all data. The user-facing outcome is opaque — the teacher has no way to know which behavior applies.

---

### Path 4: System admin teacher account deletion

| | |
|---|---|
| **Route** | `POST /sysadmin/manage-teachers/delete/<admin_id>` |
| **File** | `app/routes/system_admin.py:1276–1367` |
| **Auth** | `@system_admin_required` |
| **Authorization gate** | Same as Path 3 (pending `DeletionRequest` or 6+ months inactive) |

Deletes the entire teacher account. This removes all teacher-owned configuration and roster records but preserves all student records and financial history. `_hard_delete_join_code_scope` is **not called**.

**What gets deleted:**

| Table | Notes |
|---|---|
| `StudentTeacher` | All links to this teacher |
| `DeletionRequest` | Explicitly deleted before `Admin` row to avoid FK flush issue |
| `TeacherBlock` | All rows for this teacher |
| `BankingSettings` | Filtered by `teacher_id` |
| `FeatureSettings` | Filtered by `teacher_id` |
| `HallPassSettings` | Filtered by `teacher_id` |
| `PayrollFine` | Filtered by `teacher_id` |
| `PayrollReward` | Filtered by `teacher_id` |
| `PayrollSettings` | Filtered by `teacher_id` |
| `RentSettings` | Filtered by `teacher_id` |
| `StudentItem` | Items owned by this teacher's store items |
| `StoreItem` | Filtered by `teacher_id` |
| `TeacherOnboarding` | Filtered by `teacher_id` |
| `Admin` | The teacher record itself (triggers DB CASCADE) |
| `AdminCredential` | Via `ondelete='CASCADE'` on `Admin` FK |
| `Announcement` | Via `ondelete='CASCADE'` on `teacher_id` FK |
| `AnalyticsSnapshot` | Via `ondelete='CASCADE'` on `teacher_id` FK |
| `AnalyticsEvent` | Via `ondelete='CASCADE'` on `teacher_id` FK |

**What is NOT deleted:**

| Table | Notes |
|---|---|
| `Student` | All student records preserved |
| `Transaction` | All transaction history preserved |
| `TapEvent` | All tap history preserved |
| `HallPassLog` | All hall pass records preserved |
| `RentPayment` | All rent payment history preserved |
| `StudentBlock` | All student-period state preserved |
| `StudentInsurance` | All insurance enrollments preserved |
| `InsuranceClaim` | All insurance claims preserved |
| `BalanceCache` | Preserved (same orphan risk as Path 1 if join code is gone) |
| `Issue` | All issue records preserved |

**Confirmation UI:** Same single `confirm()` dialog as Path 3 — `"Delete teacher account username? This will remove all student links."` No data-loss detail, no typed confirmation.

---

### Path 5: Database-level cascade on Admin deletion (implicit)

If an `Admin` row is ever deleted by any means other than Path 4's explicit route — for example, a direct database operation, a future admin tool, or a migration that removes rows — the DB-level `ondelete='CASCADE'` on `TeacherBlock.teacher_id` will delete all associated `TeacherBlock` rows automatically. However, none of the application-level cleanup in `_hard_delete_join_code_scope` will run. All join_code-scoped data (`Transaction`, `TapEvent`, `StudentBlock`, `BalanceCache`, etc.) will be left behind with no associated class period.

This is not a current active risk, but the lack of a DB-level FK from `join_code` columns back to `teacher_blocks.join_code` means the database cannot enforce cleanup and there is no hook to trigger application-level logic.

---

## Findings Summary

### Finding 1 — BalanceCache is never cleaned up (P1 Bug)

**Severity:** P1
**Affected paths:** All four paths

`BalanceCache` (`app/models.py:761–781`) has a `join_code` column (line 770) and a unique constraint on `(join_code, student_id)`. It is the primary balance read source for the ledger+settlement model. It is **not included** in `_hard_delete_join_code_scope` and is not deleted by any other path.

After a class is deleted via Path 1 or 2, orphaned `balance_cache` rows remain. These rows:
- Accumulate indefinitely with no cleanup mechanism
- Could return stale balance data if a join code is ever reused (join codes are currently short alphanumeric strings, not guaranteed globally unique)
- Violate the multi-tenancy principle that all data scoped by `join_code` must be removed when that class is deleted

**Detection query:**
```sql
SELECT COUNT(*) FROM balance_cache bc
WHERE NOT EXISTS (
    SELECT 1 FROM teacher_blocks tb
    WHERE tb.join_code = bc.join_code
);
```

**Fix:** Add `BalanceCache.query.filter_by(join_code=join_code).delete(synchronize_session=False)` to `_hard_delete_join_code_scope` in `admin.py`, before the `TeacherBlock` deletion at line 458.

---

### Finding 2 — Path 3 (sysadmin period deletion) uses the legacy `Student.block` field (P2)

**Severity:** P2
**Affected path:** Path 3 only

The sysadmin period deletion at `system_admin.py:1220–1226` finds students using `Student.block == period`. This is the deprecated legacy field that was replaced by `TeacherBlock.join_code` after the P0 multi-tenancy incident. Using it means:

- Students whose `Student.block` value drifted from their `TeacherBlock.join_code` assignment (e.g. due to a rename) will not be found
- The function cannot clean up join_code-scoped data even if policy changes require it, because the join code is never resolved in this path
- Inconsistency with every other part of the codebase that uses `join_code` as the source of truth

**Fix:** Resolve `period` → `join_code` via `TeacherBlock` before operating on students, matching the pattern used by Paths 1 and 2.

---

### Finding 3 — Inconsistent deletion semantics between teacher and sysadmin paths (P2)

**Severity:** P2
**Affected paths:** All four

A teacher deleting their own class via the teacher UI (Paths 1/2) triggers a full hard delete: all transactions, balances, attendance, insurance, and store data are permanently removed. A system admin deleting the same class via the sysadmin UI (Path 3) leaves all of that data intact.

The user (teacher) has no way to know which behavior will apply when they request deletion. The sysadmin UI does not communicate to the system admin that Path 3 is intentionally a soft delete and Path 1 is a hard delete. There is no documentation visible in either UI explaining this distinction.

This creates risk in both directions:
- A teacher who wants their data deleted and requests it through a DeletionRequest will receive a soft delete that leaves all records intact
- A system admin who intends to lightly offboard a period (preserving history) could accidentally trigger a hard delete if they expose the teacher-facing route

**Recommendation:** Decide on an explicit policy: should sysadmin-initiated period deletion be a soft delete (preserve data) or a hard delete (remove data), and document this clearly in both UIs and in this audit.

---

### Finding 4 — Sysadmin confirmation dialogs do not describe data impact (P2)

**Severity:** P2
**Affected paths:** Paths 3 and 4

The sysadmin confirmation for period deletion says:
> `"Delete period PERIOD for username? This will remove N student link(s)."`

The sysadmin confirmation for teacher account deletion says:
> `"Delete teacher account username? This will remove all student links."`

Neither message:
- Mentions what data is preserved (financial history, balances, transactions)
- Mentions what data is removed (TeacherBlock rows, settings)
- Warns that the action cannot be undone
- Requires typed confirmation

Compare to the teacher-facing confirmation (Path 1/2), which explicitly lists transactions, balances, attendance records, hall pass logs, and purchases, and requires typing `DELETE BLOCK <NAME>`.

**Recommendation:** Update sysadmin confirmation messages to accurately describe what will and will not be deleted, and to note the action is irreversible.

---

### Finding 5 — Settings tables orphaned on join-code deletion (P3)

**Severity:** P3 (low impact — settings without an active class are inert)
**Affected path:** Path 1 (and Path 2)

`PayrollSettings` and `RentSettings` are scoped by `teacher_id + block` (period name), not by `join_code`. When a join code is deleted via `_hard_delete_join_code_scope`, these settings rows survive. This is partially intentional — a teacher might want their payroll configuration to persist if they recreate a period — but it means the database accumulates configuration rows for classes that no longer exist.

These rows are only removed when the teacher account itself is deleted (Path 4). They are inert (no students, no active class) but represent uncontrolled accumulation.

**Recommendation:** On join-code deletion, optionally delete `PayrollSettings` and `RentSettings` rows for the matching block name if no other TeacherBlock with that block name remains for the teacher.

---

### Finding 6 — No export or backup offered on any deletion path (P3)

**Severity:** P3
**Affected paths:** All four

None of the four deletion paths offer teachers or sysadmins an opportunity to export class data before deletion. Given that class deletion is permanent and removes transaction history, attendance records, and student balances, the absence of a data export step is a meaningful gap — especially for educators who may want to archive records for gradebook purposes.

---

### Finding 7 — No database-level FK constraint on `join_code` references (P3)

**Severity:** P3
**Type:** Structural / integrity risk

`join_code` is stored as a plain `String` column on many tables (e.g. `Transaction.join_code`, `TapEvent.join_code`, `BalanceCache.join_code`). There is no foreign key from these columns back to `teacher_blocks.join_code`. The database cannot enforce referential integrity on class membership.

This means:
- If a deletion fails mid-transaction and is only partially applied, the database cannot detect orphaned records
- There is no DB-level hook to trigger cleanup when a join code is removed
- Orphaned records from Finding 1 (and any future similar bugs) are invisible to the database

**Recommendation:** Make `teacher_blocks.join_code` a unique (or primary key candidate) column and add foreign key constraints from high-value tables (`Transaction.join_code`, `BalanceCache.join_code`, `StudentBlock.join_code`, etc.) to `teacher_blocks.join_code`. This will require a coordinated migration and data validation pass.

---

## Comparison Matrix

| | Path 1 (Teacher / join-code) | Path 2 (Teacher / block name) | Path 3 (Sysadmin / period) | Path 4 (Sysadmin / teacher) |
|---|---|---|---|---|
| **Trigger** | Teacher deletes own class | Teacher deletes block by name | Sysadmin deletes teacher's period | Sysadmin deletes teacher account |
| **Auth gate** | Owns join code | Owns block name | Pending request or 6mo inactive | Pending request or 6mo inactive |
| **Core function** | `_hard_delete_join_code_scope` | same | custom (soft delete) | custom (settings cleanup) |
| **Transactions deleted** | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Balances deleted** | ✅ Yes (StudentBlock) | ✅ Yes | ❌ No | ❌ No |
| **BalanceCache deleted** | ❌ **Bug** | ❌ **Bug** | ❌ No | ❌ No |
| **Settings deleted** | ❌ No (by join_code scope) | ❌ No | ❌ No | ✅ Yes (by teacher_id) |
| **TapEvents deleted** | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Students deleted** | ✅ Orphans only | ✅ Orphans only | ❌ No | ❌ No |
| **Confirmation style** | Two-step: confirm + type phrase | Two-step: confirm + type phrase | Single `confirm()` | Single `confirm()` |
| **Data-loss warning** | ✅ Itemized warning | ✅ Itemized warning | ❌ Mentions "student links" only | ❌ Mentions "student links" only |
| **Uses `join_code` scope** | ✅ Yes | ✅ Yes | ❌ Uses `Student.block` (legacy) | N/A |

---

## Prioritized Recommendations

### P1 — Fix BalanceCache orphaning (Finding 1)

Add a deletion statement for `BalanceCache` to `_hard_delete_join_code_scope` in `app/routes/admin.py` between the `RentPayment` deletion (line 380) and the `StudentBlock` deletion (line 381):

```python
BalanceCache.query.filter_by(join_code=join_code).delete(synchronize_session=False)
```

This requires importing `BalanceCache` at the top of the function or confirming it is already in scope.

### P2 — Migrate Path 3 off the legacy `Student.block` field (Finding 2)

In `system_admin.py:1220–1226`, replace the lookup on `Student.block` with a join through `TeacherBlock` using `join_code`:

```python
students_in_period = db.session.query(Student).join(
    TeacherBlock,
    (Student.id == TeacherBlock.student_id) &
    (TeacherBlock.join_code == join_code)  # resolved from period name
).filter(
    TeacherBlock.teacher_id == admin.id
).all()
```

This requires first resolving `period` → `join_code` via a `TeacherBlock` lookup.

### P2 — Define and document deletion semantics for each path (Finding 3)

Create a written policy (this document can serve as the basis) stating:
- Teacher-initiated deletion = hard delete, all data removed
- Sysadmin period deletion = soft delete, history preserved
- Sysadmin teacher deletion = settings/roster removed, history preserved

Communicate this distinction in both UIs: add a brief note to the sysadmin deletion confirmation explaining what is preserved and what is removed.

### P2 — Improve sysadmin confirmation dialogs (Finding 4)

Update `system_admin_manage_teachers.html` to show accurate impact descriptions:

**Period deletion:**
> "Delete period PERIOD for username? This will remove N student roster links and the class period configuration. All transaction history, balances, and student records are preserved. This action cannot be undone."

**Teacher account deletion:**
> "Delete teacher account username? This will remove all class periods, payroll/rent settings, and student roster links. Student accounts and transaction history are preserved. This action cannot be undone."

Consider adding typed confirmation (matching the teacher-facing pattern) for both sysadmin paths.

### P3 — Clean up orphaned settings on join-code deletion (Finding 5)

After `TeacherBlock` deletion in `_hard_delete_join_code_scope`, check whether any `PayrollSettings` or `RentSettings` rows for the matching block name(s) are now orphaned (no remaining TeacherBlock with that block name for this teacher) and delete them.

### P3 — Add pre-deletion data export option (Finding 6)

Before executing any deletion, offer a CSV export of the class's transaction history, student balances, and attendance records. This is especially important for the teacher-facing paths where all data is permanently removed.

### P3 — Add FK constraints on `join_code` columns (Finding 7)

As a longer-term structural improvement, add `join_code` as a proper foreign key reference on the highest-risk tables (`BalanceCache`, `Transaction`, `StudentBlock`). This would require a schema migration and careful handling of existing null/legacy values.

---

## Files Referenced

| File | Lines | Purpose |
|---|---|---|
| `app/routes/admin.py` | 327–488 | `_hard_delete_join_code_scope` — core deletion logic |
| `app/routes/admin.py` | 3007–3053 | `POST /admin/students/delete-block` |
| `app/routes/admin.py` | 3056–3082 | `POST /admin/join-code/delete` |
| `app/routes/system_admin.py` | 1184–1273 | `POST /sysadmin/delete-period/<admin_id>/<period>` |
| `app/routes/system_admin.py` | 1276–1367 | `POST /sysadmin/manage-teachers/delete/<admin_id>` |
| `app/models.py` | 161–224 | `TeacherBlock` model, `ondelete='CASCADE'` on `teacher_id` |
| `app/models.py` | 761–781 | `BalanceCache` model — join_code column, never deleted |
| `app/models.py` | 1084–1113 | `RentSettings` — scoped by `teacher_id + block` |
| `app/models.py` | 1718–1742 | `PayrollSettings` — scoped by `teacher_id + block` |
| `templates/admin_students.html` | 1458–1507 | `deleteEntireBlock()` — two-step confirmation UI |
| `templates/system_admin_manage_teachers.html` | 450–471 | Single `confirm()` sysadmin deletion UI |

---

**Last Updated:** 2026-02-21
