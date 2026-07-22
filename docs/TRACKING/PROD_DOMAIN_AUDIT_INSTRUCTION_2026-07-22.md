# PROD Domain End-to-End Audit Instruction

| Reference | Version | Date | Authority | Reviewer |
|-----------|---------|------|-----------|----------|
| AUDIT-PROD-001 | 1.0 | 2026-07-22 | QA/Review | [TBD] |

---

## Purpose

This audit validates that the Productivity and Payroll (PROD) domain has been **completely and correctly** migrated to v2 canonical architecture. It is a **strict, zero-tolerance checklist** designed to catch incomplete wiring, legacy pattern leaks, and architectural violations.

**Outcome:** Either "AUDIT PASS" (all items verified) or "AUDIT FAIL" with detailed findings.

---

## Pre-Audit Setup

### 1. Branch and Environment
- [ ] Checked out branch: `dom-prod-001/schema-alignment`
- [ ] Database migrated to head: `flask db current` shows `f6a7b8c9d0e2` or later
- [ ] Test database initialized: `TEST_DATABASE_URL` set and accessible
- [ ] No uncommitted changes: `git status` shows clean working tree

### 2. Read Authoritative Documents
**Read these in order before starting audit:**
- [ ] `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md` (understand tables, rules, authority)
- [ ] `docs/FEATURE-EXECUTION/FEAT-PROD-001_RECORD_ATTENDANCE_SESSION.md` (understand write contract)
- [ ] `docs/FEATURE-EXECUTION/FEAT-PROD-002_RECORD_HALL_PASS_LOG.md` (understand write contract)
- [ ] `docs/FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md` (understand write contract)
- [ ] `docs/SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md` (understand temporal evaluation)
- [ ] `.claude/CLAUDE.md` - Architecture and multi-tenancy rules
- [ ] `.claude/rules/multi-tenancy.md` - Critical scoping rules

---

## Part A: Schema and Data Model Audit

### A1: Table Structure Validation
**Verify PROD owns exactly three tables with correct schema:**

```bash
psql $TEST_DATABASE_URL -c "
SELECT tablename FROM pg_tables 
WHERE schemaname='public' 
AND tablename IN ('attendance_sessions','hall_pass_logs','payroll_event')
ORDER BY tablename;"
```

- [ ] **Expected output:** attendance_sessions, hall_pass_logs, payroll_event (exactly 3 tables)
- [ ] **Fail if:** Missing table, extra PROD table found, or retired tables still present (tap_events, seat_attendance_state)

### A2: AttendanceSession Column Validation
**Verify canonical v2 shape, reject v1 patterns:**

```bash
psql $TEST_DATABASE_URL -c "
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name='attendance_sessions' 
ORDER BY ordinal_position;"
```

**Required columns (check each):**
- [ ] `id` (integer PK)
- [ ] `target_seat_id` (integer FK, NOT NULL) ← **NOT `seat_id`**
- [ ] `class_id` (varchar 36, FK, NOT NULL) ← **scoping key**
- [ ] `target_user_id` (integer FK, NOT NULL)
- [ ] `actor_seat_id` (integer FK, NOT NULL)
- [ ] `mechanism` (varchar 20, NOT NULL, default 'self')
- [ ] `status` (varchar 20, NOT NULL, default 'active') — values: active | inactive
- [ ] `reason_code` (varchar 32, NOT NULL) — values: start_work | hall_pass | done_for_day | daily_limit
- [ ] `hall_pass_id` (varchar 100, nullable, indexed) ← **entitlement instance ID, not log row ID**
- [ ] `timestamp` (datetime UTC, NOT NULL, indexed) ← **NOT `started_at` or `ended_at`**

**Fail if:**
- [ ] Any column with name `seat_id`, `started_at`, `ended_at`, `duration_seconds`, `is_deleted`
- [ ] Missing any required column listed above
- [ ] `hall_pass_id` not nullable

### A3: HallPassLog Column Validation
**Verify canonical v2 shape:**

```bash
psql $TEST_DATABASE_URL -c "
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name='hall_pass_logs' 
ORDER BY ordinal_position;"
```

**Required columns:**
- [ ] `id` (integer PK)
- [ ] `requested_by_seat_id` (integer FK, NOT NULL)
- [ ] `approved_by_seat_id` (integer FK, NOT NULL)
- [ ] `correlation_id` (varchar 100, indexed) ← **grant-level provenance**
- [ ] `hall_pass_id` (varchar 100, indexed) ← **consumed entitlement instance ID**
- [ ] `class_id` (varchar 36, FK, NOT NULL) ← **scoping key**
- [ ] `timestamp` (datetime UTC, NOT NULL)
- [ ] `destination` (varchar 255, nullable) ← **optional**

**Fail if:**
- [ ] `hall_pass_id` has unique constraint (it should not — multiple logs can share instance for retries)
- [ ] Missing `class_id` (critical for multi-tenancy)
- [ ] Old columns like `status`, `request_time`, `decision_time`, `period`, `started_at`, `ended_at`

### A4: PayrollEvent Column Validation
**Verify canonical v2 shape:**

```bash
psql $TEST_DATABASE_URL -c "
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name='payroll_event' 
ORDER BY ordinal_position;"
```

**Required columns:**
- [ ] `id` (integer PK)
- [ ] `class_id` (varchar 36, FK, NOT NULL) ← **scoping key**
- [ ] `target_seat_id` (integer FK, NOT NULL)
- [ ] `target_user_id` (integer FK, NOT NULL)
- [ ] `payroll_event_type` (varchar 32) — values: payroll | manual_credit | payroll_reversal
- [ ] `correlation_id` (varchar 100, indexed) ← **links to Ledger transaction**
- [ ] `policy_version_id` (integer FK, NOT NULL)
- [ ] `mechanism` (varchar 32) — values: TEACHER | SYSTEM
- [ ] `summary_json` (jsonb)
- [ ] `recorded_at` (datetime UTC, NOT NULL, indexed)

**Fail if:**
- [ ] `amount` column exists (Ledger owns amount, not PROD)
- [ ] Missing `class_id` scoping
- [ ] Missing `policy_version_id` (idempotency key for payroll runs)
- [ ] Missing `correlation_id` (critical link to Ledger)

---

## Part B: FEAT Layer Audit

### B1: FEAT-PROD-001 (record_attendance_session)
**Verify this is the ONLY writer to attendance_sessions:**

```bash
# Search for direct AttendanceSession writes outside FEATs
grep -r "AttendanceSession(" app/routes/ app/services/ --include="*.py" | grep -v "FEAT\|record_attendance_session\|test" | grep -v "\.#"
```

- [ ] **No matches** (all writes must go through FEAT-PROD-001)
- [ ] **Fail if:** Found any direct `AttendanceSession(` in routes or services

### B2: record_attendance_session Implementation
**Verify signature and behavior:**

```bash
grep -A 30 "def record_attendance_session" app/feats/prod.py | head -40
```

- [ ] Function exists and is exported from `app/feats/prod.py`
- [ ] Accepts required params: `ctx`, `actor_seat_id`, `target_seat_id`, `target_user_id`, `mechanism`
- [ ] Uses `canonical_temporal_resolver` for timestamp (not direct `datetime.now()`)
- [ ] Validates `class_id` and `seat_id` from context, fails closed otherwise
- [ ] Sets `status` to "active" or "inactive" (never deletes/edits)
- [ ] Sets `reason_code` for inactive rows
- [ ] Sets `hall_pass_id` when reason_code = hall_pass (from entitlement instance)
- [ ] Returns result object with committed row

### B3: FEAT-PROD-002 (record_hall_pass_log)
**Verify this is the ONLY writer to hall_pass_logs:**

```bash
grep -r "HallPassLog(" app/routes/ app/services/ --include="*.py" | grep -v "record_hall_pass_log\|test\|#"
```

- [ ] **No direct constructions** (all writes through FEAT-PROD-002)

### B4: record_hall_pass_log Implementation
**Verify signature:**

```bash
grep -A 20 "def record_hall_pass_log" app/feats/prod.py | head -30
```

- [ ] Function exists in `app/feats/prod.py`
- [ ] Accepts: `ctx`, `requested_by_seat_id`, `approved_by_seat_id`, `destination`, `reason`, `idempotency_key`
- [ ] Verifies entitlement is available (calls into entitlement service)
- [ ] Writes `HallPassLog` with:
  - `correlation_id` from consumed entitlement grant's correlation_id
  - `hall_pass_id` as the specific consumed entitlement instance ID
  - `class_id` for scoping
  - `timestamp` from canonical temporal resolver
- [ ] Calls `consume_entitlement()` to mark entitlement as consumed
- [ ] Returns result with committed log row

### B5: FEAT-PROD-003 (record_payroll_event)
**Verify this is the ONLY writer to payroll_event:**

```bash
grep -r "PayrollEvent(" app/routes/ app/services/ --include="*.py" | grep -v "record_payroll_event\|test" | grep -v "#"
```

- [ ] **No direct constructions**

### B6: record_payroll_event Implementation
**Verify signature:**

```bash
grep -A 25 "def record_payroll_event" app/feats/prod.py | head -35
```

- [ ] Function exists in `app/feats/prod.py`
- [ ] Accepts: `ctx`, `target_seat_id`, `payroll_event_type`, `correlation_id`, `policy_version_id`, `mechanism`, `summary_json`
- [ ] Validates policy version exists (idempotency guard)
- [ ] Writes `PayrollEvent` with:
  - `class_id` for scoping
  - `target_seat_id` and `target_user_id`
  - `correlation_id` linking to Ledger transaction
  - `recorded_at` from canonical temporal resolver
- [ ] Calls Ledger FEAT to post monetary transaction
- [ ] Returns result with committed event row and ledger transaction

---

## Part C: Route Wiring Audit

### C1: Student Dashboard Route
**File:** `app/routes/student.py` → `student.dashboard`

```bash
grep -A 50 "def dashboard" app/routes/student.py | head -60
```

- [ ] Uses `resolve_canonical_context()` for authority
- [ ] Resolves attendance state via `get_class_attendance_status()` (not `get_all_block_statuses`)
- [ ] Passes single `attendance_state` dict (not block-keyed map)
- [ ] Reads `hall_pass_balance` from entitlement service (not `student.hall_passes`)
- [ ] Passes `current_class_id` to template (not `blocks` or `periods`)
- [ ] Uses canonical `ClassEconomy` for class display (not `Seat.block`)

**Template check:**
```bash
grep -i "student_blocks\|period_states\|data-period\|data-block" templates/student_dashboard.html
```
- [ ] **No matches** (no block/period scoping in template)

### C2: Attendance Commands (/api/tap, /api/student-status)
**File:** `app/routes/api.py`

```bash
grep -A 20 "@api_bp.route('/tap'" app/routes/api.py | head -30
```

- [ ] `/api/tap` endpoint calls `record_attendance_session` (FEAT-PROD-001)
- [ ] Does NOT accept `period` parameter from client (uses canonical context)
- [ ] Validates `action` is one of: start_work | break | leave | return | done_for_day
- [ ] Sets `mechanism` appropriately (student/teacher/system)

```bash
grep -A 15 "@api_bp.route('/student-status'" app/routes/api.py | head -20
```

- [ ] Returns single `attendance_state` for active class
- [ ] Does NOT return block-keyed state map
- [ ] Uses canonical temporal resolver for elapsed time calculation

**Fail if:**
- [ ] `/api/tap` accepts `period` parameter
- [ ] Returns `periods` or `student_blocks` state
- [ ] Uses direct `utc_now()` instead of canonical temporal resolver

### C3: Hall-Pass Approval Route
**File:** `app/routes/api.py` → `handle_pending_hall_pass_request`

```bash
grep -A 30 "def handle_pending_hall_pass_request" app/routes/api.py | head -40
```

- [ ] Reads pending request from ephemeral queue (not database)
- [ ] Approve action calls `record_hall_pass_log()` (FEAT-PROD-002)
- [ ] Reject action only removes from queue (no PROD write)
- [ ] Passes `hall_pass_id` as consumed entitlement instance to FEAT
- [ ] Validates class ownership through canonical context

### C4: Payroll Run Route
**File:** `app/routes/admin.py` → `run_payroll`

```bash
grep -A 40 "def _run_payroll" app/routes/admin.py | head -50
```

- [ ] Calls `record_payroll_event()` (FEAT-PROD-003) for each student
- [ ] Uses `canonical_temporal_resolver` for run anchor time
- [ ] Generates unique `correlation_id` for each payroll run
- [ ] Passes `policy_version_id` for idempotency
- [ ] Does NOT use removed `FEAT-LED-004` or legacy adjustment paths

**Fail if:**
- [ ] Uses old `execute_admin_adjustments` or legacy Ledger paths
- [ ] Doesn't set `correlation_id` for each event

### C5: Payroll History Route
**File:** `app/routes/admin.py` → `admin_payroll_history`

```bash
grep -A 30 "def admin_payroll_history" app/routes/admin.py | head -40
```

- [ ] Reads from `PayrollEvent` (not Transaction filtered by type)
- [ ] Scoped by `class_id` (not block)
- [ ] Uses `canonical_temporal_resolver` for date filtering
- [ ] Joins Ledger amounts by `correlation_id + target_seat_id`
- [ ] Template receives dict rows (not legacy ledger rows)

### C6: Student Detail Route
**File:** `app/routes/admin.py` → `student_detail_public`

```bash
grep -A 30 "def student_detail_public" app/routes/admin.py | head -40
```

- [ ] Uses canonical context for authorization
- [ ] Reads attendance from `AttendanceSession` by `target_seat_id + class_id`
- [ ] Reads payroll from `PayrollEvent` (not Transaction filters)
- [ ] Hall-pass balance from entitlement service (not `student.hall_passes`)
- [ ] IdentityProfile for display names (not `student.first_name`)

**Check for debug output:**
```bash
grep -n "print(" app/routes/admin.py | grep "student_detail"
```
- [ ] **No matches** (no debug prints in production routes)

### C7: Hall-Pass Controls
**File:** `app/routes/admin.py` → `adjust_hall_pass_entitlements`

```bash
grep -A 30 "def adjust_hall_pass_entitlements" app/routes/admin.py | head -40
```

- [ ] Uses `@feat_shell("FEAT-ENT-001")` decorator
- [ ] Calls `grant_hall_passes()` or `remove_hall_passes()`
- [ ] Only supports "add" and "remove" actions
- [ ] Does NOT support "set balance" (removed, not compatible with v2)
- [ ] Returns derived balance from entitlement service (not stored value)

**Fail if:**
- [ ] Supports "set" action for hall-pass balance
- [ ] Returns stored balance instead of derived

### C8: Roster Bulk Operations
**File:** `app/routes/admin.py` → `admin.tap_in_students`, `admin.tap_out_students`

```bash
grep -A 20 "def tap_in_students\|def tap_out_students" app/routes/admin.py | head -30
```

- [ ] Accept only `seat_ids` (not `block` parameter)
- [ ] Call `record_attendance_session()` for each seat
- [ ] Set `mechanism="teacher"`
- [ ] Use canonical context class_id (not client-supplied)

```bash
grep -A 20 "def bulk_adjust_hall_pass_entitlements" app/routes/admin.py | head -30
```

- [ ] Calls `grant_hall_passes()` or `remove_hall_passes()`
- [ ] Only supports add/remove (not set)
- [ ] Scoped to class_id from canonical context

---

## Part D: Temporal Evaluation Audit

### D1: Canonical Temporal Resolver Usage
**Verify no route uses removed time utilities:**

```bash
grep -r "from app.utils.time\|utc_now()\|datetime.now()\|datetime.utcnow()" app/routes/ app/services/ --include="*.py" | grep -v "canonical_temporal_resolver" | head -20
```

- [ ] **Acceptable matches only:** 
  - Imports of timezone utilities (get_timezone)
  - Direct datetime for non-PROD features
  - Comments referencing old patterns

- [ ] **Fail if:** 
  - `utc_now()` or `datetime.now()` in PROD routes/services
  - Direct day boundary construction
  - Legacy temporal rebuild patterns

### D2: Temporal Resolver Calls
**Verify all PROD read/write uses resolver:**

```bash
grep -r "canonical_temporal_resolver" app/routes/admin.py app/routes/api.py app/routes/student.py app/feats/prod.py --include="*.py" -c
```

- [ ] **Minimum 10+ calls** (every major PROD operation)
- [ ] **Examples to verify:**
  - `record_attendance_session` uses resolver for timestamp
  - `enforce_daily_limits_job` uses resolver for boundaries
  - Hall-pass approval route uses resolver for day context
  - Payroll history uses resolver for date filtering
  - Public verification uses resolver for class-local time

---

## Part E: Multi-Tenancy Audit

### E1: Class Scoping Verification
**Every PROD query MUST include class_id filter:**

```bash
# Check AttendanceSession queries
grep -r "AttendanceSession.query" app/ --include="*.py" | grep -v "test\|#" | wc -l
```

**For each match, verify:**
- [ ] Includes `.filter(AttendanceSession.class_id == class_id)` or equivalent
- [ ] Scoped by `target_seat_id + class_id` combination (not just seat)

```bash
# Check HallPassLog queries
grep -r "HallPassLog.query" app/ --include="*.py" | grep -v "test\|#" | wc -l
```

**For each match:**
- [ ] Includes `.filter(HallPassLog.class_id == class_id)`

```bash
# Check PayrollEvent queries
grep -r "PayrollEvent.query" app/ --include="*.py" | grep -v "test\|#" | wc -l
```

**For each match:**
- [ ] Includes `.filter(PayrollEvent.class_id == class_id)`

### E2: Verify No Teacher-Only Scoping
**CRITICAL: Never scope by teacher_id alone for PROD reads:**

```bash
grep -r "filter_by(teacher_id" app/routes/ app/feats/ --include="*.py" | grep -E "AttendanceSession|HallPassLog|PayrollEvent"
```

- [ ] **No matches** (teacher_id is not sufficient for class isolation)

### E3: Block/Period Rejection
**Verify block/period is never used as scoping:**

```bash
grep -r "\.block\|period.*=\|data-block\|data-period" app/routes/ app/services/ --include="*.py" | grep -v "test\|#\|display\|section" | head -20
```

- [ ] No scoping by `Seat.block` or client-supplied period
- [ ] "section" is acceptable as display label only (not scoping)

---

## Part F: Template Audit

### F1: Student Dashboard Template
**File:** `templates/student_dashboard.html`

```bash
rg "student_blocks|period_states|data-period|data-block|student.block" templates/student_dashboard.html
```

- [ ] **No matches** (no block/period state in template)

```bash
rg "attendance_state_json|hall_pass_balance|current_class_id" templates/student_dashboard.html
```

- [ ] **Multiple matches** (uses canonical v2 state)

### F2: Student Payroll Template
**File:** `templates/student_payroll.html`

```bash
rg "student_blocks|period_states|unpaid_seconds_per_block" templates/student_payroll.html
```

- [ ] **No matches**

```bash
rg "class_label|payroll_state|unpaid_seconds|attendance_events" templates/student_payroll.html
```

- [ ] **Multiple matches** (canonical v2 contract)

### F3: Admin Payroll Template
**File:** `templates/admin_payroll.html`

```bash
rg "blocks|data-block|student.block|historyBlockFilter" templates/admin_payroll.html
```

- [ ] **No matches**

```bash
rg "payroll_class_options|class_id|data-class-id" templates/admin_payroll.html
```

- [ ] **Multiple matches** (class-scoped view)

### F4: Hall-Pass Template
**File:** `templates/admin_hall_pass.html`

```bash
rg "pending_requests.*approve|FEAT-PROD-002" templates/admin_hall_pass.html
```

- [ ] Found (pending request approval UI)

### F5: Student Detail Template
**File:** `templates/student_detail.html`

```bash
rg "student.first_name|student.display_first_name|student.tap_events|student.block" templates/student_detail.html
```

- [ ] **No matches** (no direct student model derefs)

```bash
rg "identity_profile|attendance_events|payroll_event_history|hall_pass_balance" templates/student_detail.html
```

- [ ] **Multiple matches** (canonical displays)

---

## Part G: Test Audit

### G1: Test Suite Status
**Run full test suite:**

```bash
pytest -q tests/dom/prod/ tests/dom/attendance/ --tb=line 2>&1 | tail -20
```

- [ ] **Target:** 34 passed, 0 failed (exact match)
- [ ] **Fail if:** Any failures, errors, or warnings
- [ ] **Fail if:** Fewer than 34 tests passing

### G2: Specific Test Coverage

**FEAT-PROD-001 tests:**
```bash
pytest -q tests/dom/prod/test_feat_prod.py -k "FEAT_PROD_001" -v 2>&1 | grep -E "PASSED|FAILED"
```

- [ ] Attendance session creation tests pass
- [ ] Immutability tests pass (no edit/delete)

**FEAT-PROD-002 tests:**
```bash
pytest -q tests/dom/prod/test_feat_prod.py -k "FEAT_PROD_002" -v 2>&1 | grep -E "PASSED|FAILED"
```

- [ ] Hall-pass log creation tests pass
- [ ] Entitlement identity tests pass (hall_pass_id ≠ correlation_id)

**FEAT-PROD-003 tests:**
```bash
pytest -q tests/dom/prod/test_feat_prod.py -k "FEAT_PROD_003" -v 2>&1 | grep -E "PASSED|FAILED"
```

- [ ] Payroll event recording tests pass

**Temporal resolver tests:**
```bash
pytest -q tests/dom/temporal/ -v 2>&1 | tail -10
```

- [ ] Tests pass
- [ ] Resolver correctly evaluates class-local time

### G3: Stale Test Cleanup Verification
**No deprecated test files should exist:**

```bash
ls tests/dom/attendance/test_*.py | wc -l
```

- [ ] **Expected 5 files:**
  - test_attendance.py
  - test_hall_pass_checkout.py
  - test_hall_pass_history_scoping.py
  - test_hall_pass_verify.py
  - test_hall_pass_checkout.py

- [ ] **Fail if:** Found any of:
  - test_shared_student_attendance.py
  - test_api_fixes.py
  - test_api_tenancy.py
  - test_api_attendance_history.py
  - test_attendance_seat_scope.py
  - test_tap_flow.py
  - test_timezone_fix.py

### G4: Test Imports Validation
**Verify tests only import canonical PROD components:**

```bash
grep -r "from app.attendance import\|from app.models import.*SeatAttendanceState\|from app.models import.*TapEvent" tests/dom/attendance/ --include="*.py"
```

- [ ] **Expected matches only:** 
  - `from app.attendance import calculate_period_attendance` (helper function, not test framework)
  - Comments referencing deprecated patterns

- [ ] **Fail if:** Tests importing deleted models/functions

---

## Part H: Documentation Audit

### H1: Domain Authority Docs
**Verify current and accurate:**

- [ ] `DOM-PROD-001` correctly describes tables (attendance_sessions, hall_pass_logs, payroll_event)
- [ ] `DOM-PROD-001` correctly specifies field names (timestamp, target_seat_id, class_id)
- [ ] `FEAT-PROD-001/002/003` correctly describe write contracts
- [ ] No references to deleted tables (tap_events, seat_attendance_state)

### H2: PROD Stocktake
**File:** `docs/TRACKING/PROD_PAYROLL_RECONSTRUCTION_STOCKTAKE_2026-07-20.md`

- [ ] Documents hall-pass entitlement identity contract clarification
- [ ] Documents daily-limit test rewrite proof
- [ ] Documents stale test cleanup (7 files deleted)
- [ ] Lists all validation evidence with artifact references
- [ ] Marks all major surfaces as REWIRED or REWIRED_READ/WRITE

### H3: Template Audit Docs
**Verify alignment with actual state:**

- [ ] `TEMPLATE_AUDIT_STUDENT.md` marks student dashboard as REWIRED_READ_WRITE
- [ ] `TEMPLATE_AUDIT_ADMIN_E-P.md` marks hall-pass as REWIRED
- [ ] `TEMPLATE_ROUTE_AUDIT_ADMIN_AND_SHARED.md` marks student detail as REWIRED_READ
- [ ] All marked surfaces actually use v2 patterns (verify by spot-checking route code)

---

## Part I: Legacy Pattern Detection

### I1: Search for Deleted Models
**These models must NOT be referenced anywhere:**

```bash
grep -r "SeatAttendanceState\|TapEvent\|StudentBlock" app/ --include="*.py" | grep -v "test\|#" | grep -v ".pyc"
```

- [ ] **No matches** (all references should be in comments/docs only)

### I2: Search for Deleted Functions
```bash
grep -r "get_all_block_statuses\|batch_auto_tapout\|soft_delete" app/ --include="*.py" | grep -v "test\|#"
```

- [ ] **No matches** in production code

### I3: Search for Deleted Fields
```bash
grep -r "\.seat_id\|\.started_at\|\.ended_at\|\.duration_seconds\|\.is_deleted" app/ --include="*.py" | grep -E "AttendanceSession|TapEvent" | grep -v "test\|#"
```

- [ ] **No matches** (only `target_seat_id`, `timestamp`, never `is_deleted`)

### I4: Search for Block/Period Scoping
```bash
grep -r "filter.*block\|\.block\|period.*scope" app/routes/ app/services/ --include="*.py" | grep -v "test\|display\|section\|#"
```

- [ ] **No matches** for actual scoping (section is display-only)

---

## Part J: Entitlement Integration Audit

### J1: Hall-Pass Balance Derivation
**Verify no stored "balance" field, only derived:**

```bash
grep -r "def get_hall_pass_balance" app/services/entitlement_service.py -A 10 | head -15
```

- [ ] Derives balance from: granted events - consumed (approved hall_pass_logs)
- [ ] Does NOT return stored value (no hall_pass_balance column)

### J2: Grant/Remove Operations
```bash
grep -r "def grant_hall_passes\|def remove_hall_passes" app/services/entitlement_service.py -A 5 | head -20
```

- [ ] `grant_hall_passes()` writes GRANT event to EntitlementEvent
- [ ] `remove_hall_passes()` writes REVOCATION event (doesn't delete)
- [ ] Both return derived new balance

### J3: Correlation ID Contract
**Verify correlation_id is shared, hall_pass_id is instance:**

```bash
pytest -q tests/dom/prod/test_feat_prod.py::test_FEAT_PROD_002__uses_entitlement_identity_not_correlation_as_hall_pass_id -v
```

- [ ] **PASSED** (proves the contract)

---

## Part K: Verification Summary

### K1: Count Success Criteria
**All of the following must be 100% true:**

- [ ] PROD owns exactly 3 tables (attendance_sessions, hall_pass_logs, payroll_event)
- [ ] All tables have correct v2 schema (timestamp, target_seat_id, class_id)
- [ ] No deleted models/functions referenced in production code
- [ ] All PROD writes go through FEAT-PROD-001/002/003
- [ ] All PROD routes use canonical_context and canonical_temporal_resolver
- [ ] All multi-tenancy queries include class_id filter
- [ ] No block/period used as scoping (display-only)
- [ ] All templates updated to v2 contracts
- [ ] All stale tests deleted (exactly 7 deletions)
- [ ] Full test suite passes (34 passed, 0 failed)
- [ ] Documentation current and accurate
- [ ] No debug print statements in production routes
- [ ] No legacy pattern leaks found

### K2: Risk Zones (Extra Scrutiny)
If ANY of these shows unexpected result, AUDIT FAILS:

1. **Temporal evaluation:**
   ```bash
   grep -c "canonical_temporal_resolver" app/feats/prod.py app/routes/admin.py app/routes/api.py
   ```
   - [ ] Minimum 15 calls across these files

2. **Multi-tenancy scoping:**
   ```bash
   grep -c "class_id ==" app/routes/admin.py | grep -E "AttendanceSession|HallPassLog|PayrollEvent"
   ```
   - [ ] Every PROD query filtered by class_id

3. **Immutability:**
   ```bash
   grep -r "\.update()\|\.delete()\|soft.delete\|is_deleted" app/ --include="*.py" | grep -E "AttendanceSession|HallPassLog|payroll"
   ```
   - [ ] **No matches** (append-only only)

---

## Audit Sign-Off

### Pass Criteria
Audit PASSES if and only if:
- [ ] All sections A through K are checked and verified
- [ ] No failures encountered
- [ ] No legacy patterns detected
- [ ] Tests passing
- [ ] Documentation current

### Fail Criteria
Audit FAILS if any of:
- [ ] Schema mismatch (wrong field names, missing class_id)
- [ ] Legacy models/functions found in production code
- [ ] PROD writes not through FEATs
- [ ] Block/period used for scoping
- [ ] Multi-tenancy queries missing class_id
- [ ] Tests failing or stale tests present
- [ ] Debug output in routes
- [ ] Templates still using block/period state

---

## Audit Report Template

```markdown
# PROD Domain Audit Report

**Auditor:** [Name]
**Date:** [Date]
**Branch:** dom-prod-001/schema-alignment
**Result:** [PASS / FAIL]

## Summary
[1-2 sentence summary of findings]

## Sections Verified
- [ ] Part A: Schema and Data Model (X/X checks passed)
- [ ] Part B: FEAT Layer (X/X checks passed)
- [ ] Part C: Route Wiring (X/X checks passed)
- [ ] Part D: Temporal Evaluation (X/X checks passed)
- [ ] Part E: Multi-Tenancy (X/X checks passed)
- [ ] Part F: Templates (X/X checks passed)
- [ ] Part G: Tests (X/X checks passed)
- [ ] Part H: Documentation (X/X checks passed)
- [ ] Part I: Legacy Pattern Detection (X/X checks passed)
- [ ] Part J: Entitlement Integration (X/X checks passed)
- [ ] Part K: Verification Summary (X/X checks passed)

## Issues Found
[Numbered list of any issues, or "None"]

## Risk Assessment
- High Risk: [If any found]
- Medium Risk: [If any found]
- Low Risk: [If any found]

## Recommendations
[Any suggested improvements or follow-up tasks]

## Sign-Off
- Auditor: ___________________
- Date: ___________________
- Status: [APPROVED / REJECTED with reason]
```

---

## Notes for Auditor

1. **Read documentation first** - It's the source of truth. Code should match docs, not vice versa.

2. **Be strict on multi-tenancy** - This is where the biggest security issues hide. Every query must have class_id.

3. **Test the contract** - Run tests locally. Don't just grep. See actual behavior.

4. **Follow the data** - For each major PROD surface, trace a request from route → FEAT → database. Ensure no shortcuts.

5. **Check for comments** - Some deprecated patterns may be referenced in comments explaining why they were removed. That's OK. But not in live code.

6. **Temporal evaluation is critical** - Every PROD operation must use canonical_temporal_resolver. This is non-negotiable.

7. **Documentation must be current** - Stocktake doc should reference this audit when complete. Ensure it's being maintained.

---

**Last Updated:** 2026-07-22  
**Author:** Claude Code  
**Version:** 1.0
