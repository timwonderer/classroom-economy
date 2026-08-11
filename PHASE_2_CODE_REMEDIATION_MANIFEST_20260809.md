# Phase 2 Code Remediation Manifest
**Date:** 2026-08-09  
**Purpose:** Inventory of non-compliant code and documentation requiring remediation in Phase 2  
**Status:** All non-compliant spec files removed; code identified for refactoring

---

## REMOVED ARTIFACTS

### Non-Compliant Specification Files (DELETED)
✅ **REMOVED:** `docs/FEATURE-EXECUTION/FEAT-IDEN-001_STUDENT_SEAT_CLAIM.md` (v1.0, 2026-04-23)
- **Reason:** 7 constitutional violations identified
- **Replaced by:** `FEAT-IDEN-001_UNAUTHENTICATED_STUDENT_SEAT_CLAIM_REMEDIATED.md` (v2.0, 2026-08-09)
- **Action:** File deleted 2026-08-09 10:00 UTC

---

## NON-COMPLIANT CODE REQUIRING PHASE 2 REMEDIATION

### 1. `app/routes/student.py`

#### `claim_account()` (lines 523-624)
**Issues:**
- ❌ Performs inline domain operations (ClassEconomy lookup, Seat queries)
- ❌ No audit trace emission
- ❌ No idempotency key handling
- ❌ Missing ClassMembership initialization
- ❌ Defers User creation to later step (atomicity violation)

**Required Changes (Phase 2):**
- [ ] Line 524: Change `@feat_shell("FEAT-IDEN-001")` — keep correct
- [ ] Lines 549-574: Extract class/seat resolution to FEAT (not route)
- [ ] Lines 576-611: Remove inline name matching logic
- [ ] Add audit trace emission
- [ ] Add idempotency_key parameter
- [ ] Ensure single transaction boundary
- [ ] Add ClassMembership initialization call

**Replace with:** Call to FEAT-IDEN-001 orchestrator (TBD - helper function or service)

---

#### `create_username()` (lines 627-657)
**Issues:**
- ❌ Tagged with wrong FEAT: `@feat_shell("FEAT-IDEN-002")` at line 628
- ❌ Generates username (should be student choice via form)
- ⚠️ Part of multi-step setup flow

**Required Changes (Phase 2):**
- [ ] Line 628: Verify FEAT tag is correct (FEAT-IDEN-002)
- [ ] Review username generation logic (may be correct as-is)
- [ ] Ensure idempotency_key is passed

**Status:** Likely OK as preparation step for FEAT-IDEN-002

---

#### `setup_pin_passphrase()` (lines 660-713)
**Issues:**
- ❌ Tagged with wrong FEAT: `@feat_shell("FEAT-IDEN-001")` at line 661 (should be FEAT-IDEN-002)
- ❌ Calls `create_student_user_for_seat()` inline (FEAT operation)
- ❌ No audit trace emission
- ❌ No idempotency handling
- ❌ Defers credential activation (atomicity concern)

**Required Changes (Phase 2):**
- [ ] Line 661: Change `@feat_shell("FEAT-IDEN-001")` to `@feat_shell("FEAT-IDEN-002")`
- [ ] Lines 693-699: Move User/credential creation to FEAT-IDEN-002
- [ ] Add audit trace emission
- [ ] Add idempotency_key parameter
- [ ] Ensure User pre-provisioning state validation
- [ ] Initialize session nonce, expiry, started_at

**Replace with:** Call to FEAT-IDEN-002 orchestrator

---

#### `add_class()` (lines 718+)
**Issues:**
- ❌ Currently tagged: `@feat_shell("FEAT-OBL-001")` (wrong domain)
- ❌ Should be identity operation (FEAT-IDEN-005)
- ❌ Needs specification written first (FEAT-IDEN-005 does not exist yet)

**Required Changes (Phase 2):**
- [ ] Create FEAT-IDEN-005 specification for authenticated class binding
- [ ] Change FEAT tag from FEAT-OBL-001 to FEAT-IDEN-005
- [ ] Move route logic to call FEAT-IDEN-005
- [ ] Add audit trace emission
- [ ] Add authorization checks (user can only bind own accounts)

**Status:** Blocked on FEAT-IDEN-005 spec creation

---

### 2. `app/routes/recovery.py`

#### `generate_reset_code()` (lines 34-77)
**Issues:**
- ❌ Tagged with wrong FEAT: `@feat_shell("FEAT-IDEN-002")` at line 34 (should be FEAT-IDEN-003)
- ❌ Performs inline User updates (FEAT operation)
- ❌ No teacher authorization validation
- ❌ No audit trace emission
- ❌ No rate limiting enforcement
- ❌ No idempotency handling

**Required Changes (Phase 2):**
- [ ] Line 34: Change `@feat_shell("FEAT-IDEN-002")` to `@feat_shell("FEAT-IDEN-003")`
- [ ] Lines 43-58: Move reset code generation to FEAT-IDEN-003
- [ ] Add teacher authorization check (admin seat in same class)
- [ ] Add audit trace emission
- [ ] Add rate limiting (max 5 per hour per teacher)
- [ ] Add idempotency_key parameter

**Replace with:** Call to FEAT-IDEN-003 orchestrator

---

#### `account_lookup()` (lines 89-157)
**Issues:**
- ❌ Tagged with wrong FEAT: `@feat_shell("FEAT-IDEN-002")` at line 91 (should be FEAT-IDEN-004)
- ❌ Performs inline User mutations (lines 131-137)
- ❌ No generic error messages (security risk)
- ❌ No audit trace emission
- ❌ No rate limiting/lockout on failed attempts
- ❌ No idempotency handling

**Required Changes (Phase 2):**
- [ ] Line 91: Change `@feat_shell("FEAT-IDEN-002")` to `@feat_shell("FEAT-IDEN-004")`
- [ ] Lines 108-137: Move reset code validation and credential clear to FEAT-IDEN-004
- [ ] Replace specific error messages with generic "Invalid or expired recovery code"
- [ ] Add audit trace emission
- [ ] Add rate limiting (max 5 attempts per 15 min per IP)
- [ ] Add lockout after 3 failures (5 min wait)
- [ ] Add idempotency_key parameter

**Replace with:** Call to FEAT-IDEN-004 orchestrator

---

### 3. `app/services/classroom_setup.py`

#### `create_student_user_for_seat()` (lines 215-241)
**Issues:**
- ⚠️ Not a FEAT (service function)
- ✅ Implements correct logic (creates user, binds seat, sets context)
- ❌ Called directly from routes (should be wrapped in FEAT)
- ❌ Not idempotent (called directly)
- ❌ No audit trace emission (caller responsible)

**Required Changes (Phase 2):**
- [ ] Keep function (service utility)
- [ ] REMOVE direct calls from routes
- [ ] Routes should call FEAT-IDEN-002 instead
- [ ] Add audit trace handling to caller (route)
- [ ] Document that this is an internal service, not a public FEAT

**Status:** Function OK; usage pattern needs fixing

---

### 4. Database Migrations

#### Outstanding Migration Concerns
- ⚠️ No migrations for FEAT-IDEN changes (schema should already exist)
- ✅ `seats` table has all required fields (user_id, claimed_at, claim hashes, dedupe_code)
- ✅ `users` table has required fields (reset_code fields, pin_hash, passphrase_hash)
- ✅ `classes` table has required fields (class_id, join_code)

**Required Actions (Phase 2):**
- [ ] Verify schema matches FEAT-IDEN specifications
- [ ] No migrations needed if schema is current
- [ ] If schema changes needed, create migration per SOP-DB-009

---

### 5. Tests

#### Test Files Requiring Updates
**Critical:** Tests must be updated alongside code changes

**Files to Update:**
- `tests/test_student_recovery.py` — Recovery flow tests
- `tests/dom/identity/test_student_recovery.py` — Identity domain tests
- `tests/test_student_routes.py` (if exists) — Student route tests
- Any other tests calling `@feat_shell("FEAT-IDEN-*")` routes

**Required Changes (Phase 2):**
- [ ] Update FEAT tag assertions (wrong tags currently checked)
- [ ] Add idempotency tests for all FEATs
- [ ] Add atomicity tests (rollback on failure)
- [ ] Add audit trace verification
- [ ] Add authorization tests (especially FEAT-IDEN-003)
- [ ] Add rate limiting tests
- [ ] Add generic error message tests (FEAT-IDEN-004)
- [ ] Test that no user search occurs (FEAT-IDEN-001)

---

## DOCUMENTATION REQUIRING UPDATES

### 1. Route Documentation
- ❌ `app/routes/__init__.py` or routing docs may reference old FEATs
- **Action:** Update any route documentation to use corrected FEAT names

### 2. API Documentation
- If API docs exist, update to show correct FEAT tags and required parameters

### 3. Code Comments
- **Action:** Remove or update inline comments referencing old FEAT-IDEN-001 v1.0 behavior

---

## SUMMARY OF PHASE 2 CODE CHANGES

### Routes to Modify (6 total)
1. `app/routes/student.py:claim_account()` — Extract logic to FEAT-IDEN-001
2. `app/routes/student.py:create_username()` — Verify tag
3. `app/routes/student.py:setup_pin_passphrase()` — Move to FEAT-IDEN-002, change tag
4. `app/routes/recovery.py:generate_reset_code()` — Move to FEAT-IDEN-003, change tag
5. `app/routes/recovery.py:account_lookup()` — Move to FEAT-IDEN-004, change tag
6. `app/routes/student.py:add_class()` — Blocked on FEAT-IDEN-005 spec

### FEATs to Create (4 total)
1. ✅ FEAT-IDEN-001 v2.0 — Spec complete
2. ✅ FEAT-IDEN-002 v1.0 — Spec complete
3. ✅ FEAT-IDEN-003 v1.0 — Spec complete
4. ✅ FEAT-IDEN-004 v1.0 — Spec complete
5. 📝 FEAT-IDEN-005 v1.0 — Spec needed

### Tests to Update (TBD - count)
- Update existing tests
- Add new tests for idempotency, atomicity, audit, authorization
- Add rate limiting tests

---

## PHASE 2 CRITICAL CHECKLIST

### Before Starting Code Changes
- [ ] Review all FEAT-IDEN specifications (v2.0 and new specs)
- [ ] Review this manifest with team
- [ ] Assign developers to each route
- [ ] Create FEAT-IDEN-005 specification

### During Code Changes
- [ ] Update FEAT tags (6 routes)
- [ ] Extract logic to FEATs (5 routes)
- [ ] Add audit trace emission
- [ ] Add idempotency handling
- [ ] Add rate limiting/authorization
- [ ] Update tests
- [ ] Update docs/comments

### After Code Changes
- [ ] Run full test suite
- [ ] Security review (especially FEAT-IDEN-004 generic messages)
- [ ] Compliance verification
- [ ] Code review against FEAT specs

---

## FILES NOT MODIFIED (IN SCOPE)

### Models (`app/models.py`)
- ✅ User, Seat, ClassEconomy models are correct
- ✅ No model changes needed
- ⚠️ Verify field types match specs (usernames hashed, credentials hashed, etc.)

### Forms (`app/forms.py`)
- ⚠️ May need form validation updates
- StudentClaimAccountForm — Check password/PIN validation rules
- StudentPinPassphraseForm — Verify validation matches FEAT-IDEN-002 spec

### Utilities
- ✅ hash_utils.py — Correct hash functions
- ✅ temporal resolver — Used for timestamps
- ❌ Any custom ID generation — Verify no legacy student_id usage

---

## REMOVED SPECIFICATIONS

**Deleted Files:**
- ❌ `docs/FEATURE-EXECUTION/FEAT-IDEN-001_STUDENT_SEAT_CLAIM.md` (v1.0, non-compliant)
  - Deleted: 2026-08-09
  - Reason: Constitutional violations (7 identified, fixed in v2.0)
  - Replaced by: `FEAT-IDEN-001_UNAUTHENTICATED_STUDENT_SEAT_CLAIM_REMEDIATED.md` (v2.0)

---

## NEXT STEPS (Phase 2 Readiness)

1. ✅ All non-compliant specs removed
2. ✅ All non-compliant code locations identified
3. ✅ Remediation manifest created
4. 📝 Assign developers to code changes
5. 📝 Create FEAT-IDEN-005 specification
6. 📝 Execute code remediation per this manifest

---

**This manifest is the single source of truth for Phase 2 code remediation. All changes must be tracked against this list.**

**Manifest Last Updated:** 2026-08-09  
**Manifest Status:** Ready for Phase 2 execution
