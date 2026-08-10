# FEAT-IDEN Remediation Roadmap
**Status: Complete specification framework**  
**Date: 2026-08-09**

---

## Overview

The Identity Domain requires a coordinated set of FEATs to cover all student lifecycle operations. This roadmap maps each FEAT to governing DOM-IDEN authority and implementation status.

---

## FEAT-IDEN Specification Matrix

| FEAT ID | Purpose | DOM Authority | Status | Implementation |
|---------|---------|---------------|--------|-----------------|
| FEAT-IDEN-001 | Unauthenticated Seat Claim (New User) | DOM-IDEN-005 §VII | ✅ REMEDIATED v2.0 | `/student/claim-account` |
| FEAT-IDEN-002 | Student Credential Setup | DOM-IDEN-002 §VIII.IV Step 8 | ✅ NEW CREATED v1.0 | `/student/setup-pin-passphrase` |
| FEAT-IDEN-003 | Teacher-Initiated Reset Code Generation | DOM-IDEN-002 §IX Step 1 | ✅ NEW CREATED v1.0 | `/admin/generate-reset-code` |
| FEAT-IDEN-004 | Student Recovery Code Validation & Credential Clear | DOM-IDEN-002 §IX Step 2 | 📝 TODO | `/recovery/account-lookup` |
| FEAT-IDEN-005 | Authenticated Class Binding (Existing User) | DOM-IDEN-005 §VII | 📝 TODO | `/student/add-class` |
| FEAT-IDEN-006+ | (Future: Additional identity operations) | TBD | - | - |

---

## Current Implementation Status

### Routes Needing FEAT Refactoring

| Route | Current FEAT Tag | Correct FEAT | Status |
|-------|-----------------|-------------|--------|
| `/student/claim-account` | `@feat_shell("FEAT-IDEN-001")` | FEAT-IDEN-001 | ✅ Correct (after remediation) |
| `/student/create-username` | `@feat_shell("FEAT-IDEN-002")` | FEAT-IDEN-002 | ✅ Correct (newly assigned) |
| `/student/setup-pin-passphrase` | `@feat_shell("FEAT-IDEN-001")` | FEAT-IDEN-002 | ⚠️ WRONG TAG - should be FEAT-IDEN-002 |
| `/admin/generate-reset-code` | `@feat_shell("FEAT-IDEN-002")` | FEAT-IDEN-003 | ❌ WRONG - should be FEAT-IDEN-003 |
| `/recovery/account-lookup` | `@feat_shell("FEAT-IDEN-002")` | FEAT-IDEN-004 | ❌ WRONG - should be FEAT-IDEN-004 |
| `/student/add-class` | `@feat_shell("FEAT-OBL-001")` | FEAT-IDEN-005 | ❌ WRONG - needs its own FEAT |

---

## Workflow Flowchart

```
NEW STUDENT (First Time in Any Class)
│
├─ Path A: Unauthenticated Claim
│  │
│  ├─ FEAT-IDEN-001: Unauthenticated Seat Claim
│  │  └─ Input: join_code, first_name, last_name
│  │  └─ Output: user_id (uncredentialed), seat_id
│  │
│  ├─ FEAT-IDEN-002: Credential Setup
│  │  └─ Input: username, pin, passphrase
│  │  └─ Output: authenticated session, ready for login
│  │
│  └─ Result: Student can now log in
│
└─ [End of new student flow]

EXISTING STUDENT (Returning / Lost Credentials)
│
├─ Path B: Account Recovery
│  │
│  ├─ Teacher Action: FEAT-IDEN-003: Generate Reset Code
│  │  └─ Teacher initiates recovery for claimed student
│  │  └─ System generates 8-char reset code, 10-min TTL
│  │
│  ├─ Student Action: FEAT-IDEN-004: Validate Code & Clear Credentials
│  │  └─ Student submits reset code
│  │  └─ System validates code, clears old credentials
│  │
│  ├─ FEAT-IDEN-002: Credential Setup (reused)
│  │  └─ Student sets new username, PIN, passphrase
│  │
│  └─ Result: Student can log in with new credentials
│
└─ [End of recovery flow]

EXISTING STUDENT (Adding New Class)
│
├─ Path C: Authenticated Class Binding
│  │
│  ├─ Student logs in (existing credentials, FEAT-IDEN-LOGIN)
│  │
│  ├─ Student selects "Add Class" option
│  │
│  ├─ FEAT-IDEN-005: Authenticated Class Binding (TODO)
│  │  └─ Input: join_code, authenticated user_id
│  │  └─ May or may not need name credentials (TBD)
│  │  └─ Output: new seat in new class, bound to existing user
│  │
│  └─ Result: Student now participates in two classes
│
└─ [End of class-add flow]
```

---

## FEAT-IDEN-001: Unauthenticated Student Seat Claim

**Status: ✅ REMEDIATED (v2.0, 2026-08-09)**

**Key Changes from v1.0:**
- ✅ Removed DOB and DOB-based identity_hash
- ✅ Removed existing user search
- ✅ Always creates NEW user (never reuses)
- ✅ Added last_active_class_id initialization
- ✅ Clarified unauthenticated-only scope
- ✅ Fixed audit outcome (only NEW_USER_CLAIMED)

**File:** `docs/FEATURE-EXECUTION/FEAT-IDEN-001_UNAUTHENTICATED_STUDENT_SEAT_CLAIM_REMEDIATED.md`

**Implementation Todos:**
- [ ] Update app/routes/student.py:claim_account() to match FEAT-IDEN-001 v2.0
- [ ] Remove User search logic (lines 576-611 searching by name hashes)
- [ ] Add ClassMembership initialization call
- [ ] Add audit trace emission (ACT-IDEN-001)
- [ ] Ensure single atomic transaction
- [ ] Update tests to verify no user search occurs

---

## FEAT-IDEN-002: Student Credential Setup

**Status: ✅ NEW CREATED (v1.0, 2026-08-09)**

**Key Features:**
- ✓ Activates credentials on pre-provisioned user (from FEAT-IDEN-001)
- ✓ Validates username, PIN, passphrase
- ✓ Hashes credentials with salt+pepper
- ✓ Establishes authenticated session
- ✓ Emits audit trace (ACT-IDEN-002)

**File:** `docs/FEATURE-EXECUTION/FEAT-IDEN-002_STUDENT_CREDENTIAL_SETUP.md`

**Implementation Todos:**
- [ ] Update app/routes/student.py:setup_pin_passphrase() to match FEAT-IDEN-002
- [ ] Change @feat_shell("FEAT-IDEN-001") to @feat_shell("FEAT-IDEN-002")
- [ ] Extract user and seat state validation from app/routes/student.py:_get_claimed_setup_state()
- [ ] Verify user is uncredentialed before activation
- [ ] Initialize session fields (current_session_started_at, expires_at, nonce)
- [ ] Emit audit trace
- [ ] Add idempotency check (prevent re-activation)
- [ ] Update tests

---

## FEAT-IDEN-003: Teacher-Initiated Reset Code Generation

**Status: ✅ NEW CREATED (v1.0, 2026-08-09)**

**Key Features:**
- ✓ Teacher initiates recovery for claimed student
- ✓ Generates random 8-char reset code
- ✓ Sets 10-minute TTL
- ✓ Overwrites any existing code (single active code invariant)
- ✓ Emits audit trace

**File:** `docs/FEATURE-EXECUTION/FEAT-IDEN-003_TEACHER_RESET_CODE_GENERATION.md`

**Implementation Todos:**
- [ ] Create specification file (below)
- [ ] Update app/routes/recovery.py:generate_reset_code() to match spec
- [ ] Change @feat_shell("FEAT-IDEN-002") to @feat_shell("FEAT-IDEN-003")
- [ ] Validate teacher authorization (admin seat in same class)
- [ ] Emit audit trace (ACT-IDEN-003)
- [ ] Add rate limiting on reset code generation
- [ ] Update tests

---

## FEAT-IDEN-004: Student Recovery Code Validation

**Status: 📝 TODO (spec exists, needs creation)**

**Key Features (from DOM-IDEN-002 §IX Step 2):**
- Validate reset code (not expired, matches one user)
- Clear credentials (force fresh setup)
- Clear reset code (single-use)
- Emit audit trace

**File:** `docs/FEATURE-EXECUTION/FEAT-IDEN-004_STUDENT_RECOVERY_CODE_VALIDATION.md`

**Implementation Todos:**
- [ ] Create specification file (below)
- [ ] Update app/routes/recovery.py:account_lookup() to match spec
- [ ] Change @feat_shell("FEAT-IDEN-002") to @feat_shell("FEAT-IDEN-004")
- [ ] Validate reset code is not already used
- [ ] Clear all three credential hashes atomically
- [ ] Clear reset code and expiry
- [ ] Emit audit trace (ACT-IDEN-004)
- [ ] Add rate limiting on code submission
- [ ] Add lockout after repeated failures
- [ ] Update tests

---

## FEAT-IDEN-005: Authenticated Class Binding (Existing User)

**Status: 📝 TODO (not yet specified)**

**Governing Authority:** DOM-IDEN-005 §VII (separate from unauthenticated claim)

**Purpose:** Handle an existing logged-in user adding a new classroom to their account.

**Key Differences from FEAT-IDEN-001:**
- User is ALREADY authenticated (logged in)
- User is ALREADY has existing credentials
- May reuse user_id (unlike unauthenticated claim)
- Requires rouster seat match (like FEAT-IDEN-001)
- Creates NEW seat bound to EXISTING user

**Route:** `app/routes/student.py:add_class()` (currently lines 718+)

**Implementation Todos:**
- [ ] Create specification file
- [ ] Design workflow (does student re-enter name? Or auto-match?)
- [ ] Update route to proper FEAT
- [ ] Verify user authorization (can only bind user's own accounts)
- [ ] Emit audit trace
- [ ] Update tests

---

## FEAT-IDEN-006+: Future Operations

Potential additional FEATs:
- **FEAT-IDEN-006:** Authenticated Student Login (context restoration)
- **FEAT-IDEN-007:** Identity Deletion (when final seat removed)
- **FEAT-IDEN-008:** Cross-class identity verification (if needed)

These are out of scope for current remediation but should be created if code implements them.

---

## Remediation Sequence

### Phase 1: Specification (COMPLETE)
- ✅ FEAT-IDEN-001 v2.0 (remediated)
- ✅ FEAT-IDEN-002 v1.0 (new)
- ✅ FEAT-IDEN-003 v1.0 (new)
- 📝 FEAT-IDEN-004 v1.0 (to be created)
- 📝 FEAT-IDEN-005 v1.0 (to be created)

### Phase 2: Code Update (TODO)
1. Update FEAT tags on routes
2. Refactor routes to call FEATs, not inline operations
3. Add validation and audit traces
4. Update tests

### Phase 3: Verification (TODO)
1. Run full test suite
2. Verify no constitutional violations
3. Verify idempotency
4. Verify audit trail completeness

---

## Critical Implementation Constraints

1. **Atomicity:** All mutations within a FEAT must be in single transaction
2. **No Inference:** Unauthenticated claim (FEAT-IDEN-001) SHALL NOT search for existing users
3. **Always Create New (FEAT-IDEN-001):** Never reuse users in unauthenticated claim
4. **Audit Required:** Every FEAT MUST emit audit trace with outcome
5. **Idempotency:** Every FEAT MUST detect replays via idempotency_key
6. **Credential Setup:** Always use FEAT-IDEN-002 for activation (reused from both claim and recovery)

---

## Old vs New Mapping

| Old (Non-Compliant) | New (Compliant) | Issue |
|-------------------|-----------------|-------|
| FEAT-IDEN-001 v1.0 | FEAT-IDEN-001 v2.0 | DOB usage, user search, conflated workflows |
| (none) | FEAT-IDEN-002 v1.0 | Created (was missing) |
| FEAT-IDEN-002 (wrong) | FEAT-IDEN-003 v1.0 | Reset code generation needs own FEAT |
| FEAT-IDEN-002 (wrong) | FEAT-IDEN-004 v1.0 | Recovery code validation needs own FEAT |
| FEAT-OBL-001 (wrong) | FEAT-IDEN-005 v1.0 | Class binding is identity, not obligation |

---

## File Structure After Remediation

```
docs/FEATURE-EXECUTION/
├── FEAT-IDEN-001_UNAUTHENTICATED_STUDENT_SEAT_CLAIM_REMEDIATED.md ✅
├── FEAT-IDEN-002_STUDENT_CREDENTIAL_SETUP.md ✅
├── FEAT-IDEN-003_TEACHER_RESET_CODE_GENERATION.md ✅
├── FEAT-IDEN-004_STUDENT_RECOVERY_CODE_VALIDATION.md (TODO)
├── FEAT-IDEN-005_AUTHENTICATED_CLASS_BINDING.md (TODO)
└── [other FEAT files...]
```

---

## Backward Compatibility Notes

The old FEAT-IDEN-001 v1.0 (2026-04-23) is **declared non-compliant** and **withdrawn**.

Code currently using old FEAT tags will fail post-remediation validation checks. All routes must be updated to use corrected FEAT tags during Phase 2.

---

## Sign-Off

This roadmap establishes the complete FEAT-IDEN specification framework compliant with DOM-IDEN authority documents.

**Next step:** Begin Phase 2 (code update).
