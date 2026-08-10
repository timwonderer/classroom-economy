# EMERGENCY AUDIT: Student Claim Flow (/claim-account)
**Date:** 2026-08-09  
**Scope:** End-to-end inspection of `/student/claim-account` against FEAT-IDEN-001 and DOM-IDEN-002  
**Finding:** **CRITICAL - Constitutional violations detected**

---

## Executive Summary

The `/student/claim-account` flow implements claim identity resolution inline within route handlers instead of through proper FEAT orchestration. This violates:

1. **FEAT-CORE-000 §III.1** — Context must be resolved before any domain interaction
2. **FEAT-CORE-000 §III.2** — All mutations must occur in a single atomic transaction
3. **FEAT-CORE-000 §VII.2** — Identity binding must be atomic within a single FEAT
4. **FEAT-IDEN-001 §III (Orchestration Logic)** — Claim must atomically provision User AND bind Seat
5. **DOM-IDEN-002 §VIII (Claim Flow)** — Binding happens as part of claim completion, not deferred

The claim flow is split across TWO HTTP requests:
- **Request 1** (`/claim-account` POST): Resolves class_id and seat_id, stores seat_ref in session
- **Request 2** (`/setup-pin-passphrase` POST): Creates User, binds seat.user_id

This violates atomicity constraints and defers User provisioning beyond the claim boundary.

---

## Detailed Findings

### 1. INLINE DOMAIN OPERATIONS (Against FEAT-CORE-000 §IV)

The `claim_account()` route directly performs these domain operations that should be delegated to a FEAT:

**Table: Inline Domain Operations in claim_account()**

| Line | Operation | Domain | Constitutional Requirement |
|------|-----------|--------|---------------------------|
| 549 | `ClassEconomy.query.filter_by(join_code=...)` | Class resolution | FEAT-IDEN-001 §III.1 Step 1 |
| 560-566 | `Seat.query.filter(class_id=..., user_id.is_(None))` | Roster lookup | FEAT-IDEN-001 §III.1 Step 2 |
| 576-577 | `hash_username_lookup(first_name.lower())` | Credential hashing | FEAT-IDEN-001 §III.1 preparation |
| 580-582 | Loop matching seats by hashes | Seat matching | FEAT-IDEN-001 §III.1 Step 2 |
| 603-611 | Dedupe code matching | Disambiguation | FEAT-IDEN-001 §III.1 Step 2 |
| 616 | `session['onboarding_seat_ref'] = matched_seat.id` | Session mutation | Not in FEAT specification |

**Constitutional Violation:**
- FEAT-CORE-000 §IV states: "Domains **MUST NOT** call other domains; All cross-domain coordination **MUST** occur inside a FEAT."
- The route IS performing cross-domain coordination (Class + Seat + Hash operations) instead of delegating to FEAT-IDEN-001.

---

### 2. BROKEN ATOMICITY (Against FEAT-CORE-000 §III.2 and FEAT-IDEN-001 §IV)

**FEAT-IDEN-001 §IV states:**
> "Atomic Binding: The link between `User`, `Seat`, and `Class` must be created within the same transaction."

**Current Implementation (BROKEN):**

```
HTTP Request 1: POST /student/claim-account
├── Resolve class_id from join_code
├── Query unclaimed seats
├── Match seat by name hash
└── Store seat_id in SESSION
    (No User created, No Seat.user_id bound, No atomicity)

                    ↓ [User navigates to next page]

HTTP Request 2: POST /student/setup-pin-passphrase  
├── Retrieve seat_id from session
├── Create User (lines 693-699)
├── Bind seat.user_id = user.id
└── Commit transaction
    (But now claims are split across requests)
```

**Problem:**
- If the user closes the browser after `/claim-account` but before `/setup-pin-passphrase`, the seat remains unclaimed
- The two operations are **not** atomic — there is no transaction boundary spanning both requests
- Each HTTP request has its own transaction; session state is not transactional

**Correct Pattern (per FEAT-IDEN-001 §III.2):**
```
Single FEAT-IDEN-001 Execution (atomic transaction):
├── Verify Phase: Resolve class_id, seat_id, check for existing User
└── Mutation Phase (single transaction):
    ├── Provision User (create or reuse)
    ├── Bind seat.user_id = user.id
    ├── Scrub PII from roster
    ├── Initialize ClassMembership
    └── Emit audit trace
    
Result: Commit atomically or rollback completely
```

---

### 3. MISSING IDENTITY RESOLUTION PHASE (Against FEAT-IDEN-001 §III.1.3)

**FEAT-IDEN-001 §III.1.3 specifies:**
> "Lookup: Search for an existing `User` matching the `identity_hash` (First Initial + DOB Sum)."
> "Validation: If an `existing_user_id` was provided in the request, it MUST match the found user."
> "Conflict Check: If the found `User` is already bound to a different `seat_id` in the SAME `class_id`, abort with `ALREADY_CLAIMED`."

**Current Implementation:**
- ❌ No `dob_sum` credential is collected (form only has `first_name` and `last_name`)
- ❌ No `identity_hash` is computed
- ❌ No search for existing User
- ❌ No `existing_user_id` validation
- ❌ No "already claimed in same class" check

**Routes/Student.py Evidence:**
```python
# Lines 542-546: Form data collection
if form.validate_on_submit():
    display_join_code = format_join_code(form.join_code.data)
    first_name = (form.first_name.data or "").strip()
    last_name = form.last_name.data.strip()
    dedupe_code = (form.dedupe_code.data or "").strip().upper()
    # NO dob_sum, NO existing_user_id
```

**Impact:**
- A user claiming their second class will create a DUPLICATE User record instead of reusing the existing one
- No safeguard against a teacher maliciously binding a student to another teacher's class
- Violates DOM-IDEN-001 Participation Model (line 87): "A `User` may own **at most one `Seat` per `Class`."

---

### 4. MISSING USER PROVISIONING PHASE (Against FEAT-IDEN-001 §III.2.1)

**FEAT-IDEN-001 §III.2.1 states:**
> "1. User Provisioning:
>    * If `User` found: Use `user_id`.
>    * If `User` not found: Create new `User` record in `DOM-IDEN`."

**Current Implementation:**
- ❌ User is NOT created in `claim_account()` 
- ❌ User creation is deferred to `setup_pin_passphrase()` (3 HTTP requests later)
- ❌ No path for "reuse existing User"

**Violation of DOM-IDEN-002 §VIII.IV (Claim Flow), Step 7:**
> "On successful claim, the seat is bound to `user_id`"

The seat is NOT bound to user_id upon claim completion. It's only bound after the passphrase setup.

---

### 5. MISSING ROSTER FINALIZATION (Against FEAT-IDEN-001 §III.2.3)

**FEAT-IDEN-001 §III.2.3 states:**
> "Roster Finalization (PII Scrubbing):
>    * Update Roster Seat: set `is_claimed = True`, `claimed_at = NOW`, and bind the resolved `user_id` to the claimed seat record.
>    * **Explicit Scrub**: MUST zero out `last_name_hash_part` and `dob_sum_hash` to prevent future collision or recovery leaks."

**Current Implementation:**
- ✓ `claimed_at` is set in `create_student_user_for_seat()` (line 237)
- ✓ `seat.user_id` is bound (line 236)
- ❌ **PII scrubbing never happens** — claim hashes are left on the seat forever

**Evidence:**
- [app/models.py:237-239] — `Seat` model has `claim_first_name_hash`, `claim_last_name_hash`
- [app/routes/student.py:576-577] — Hashes are computed during claim
- **Nowhere in the codebase** are these hashes zeroed out after claim succeeds

**Security Implication:**
- If `claim_first_name_hash` and `claim_last_name_hash` are ever compromised, an attacker could impersonate the student in recovery flows
- The hashes should be scrubbed immediately after claim succeeds

---

### 6. MISSING MEMBERSHIP INITIALIZATION (Against FEAT-IDEN-001 §III.2.4)

**FEAT-IDEN-001 §III.2.4 states:**
> "Membership Initialization:
>    * Call `DOM-CLASS` to record `ClassMembership`."

**Current Implementation:**
- ❌ `ClassMembership` is never created during the claim flow
- Checked: No code in claim_account(), create_username(), or setup_pin_passphrase() creates ClassMembership

**Consequence:**
- The student seat is claimed but has no formal class membership record
- Violates DOM-IDEN-002 §II (Scope): "This document governs... student-specific claim data model"

---

### 7. MISSING CONTEXT RESTORATION (Against FEAT-IDEN-001 §III.2.5 and DOM-IDEN-002 §VIII.IV.9)

**FEAT-IDEN-001 §III.2.5 states:**
> "Context Restoration:
>    * Set `User.last_active_seat_id` to the newly bound `seat_id`."

**DOM-IDEN-002 §VIII.IV.9 states:**
> "Initialize `last_active_class_id` and `last_active_seat_id` to the newly bound class and seat context (per DOM-IDEN-006 §XIII)"

**Current Implementation:**
- ✓ Both fields ARE set in `create_student_user_for_seat()` (lines 238-239)
- ✓ This part is correctly implemented

**Status:** ✅ PASS (This step is done correctly)

---

### 8. MISSING AUDIT TRACE (Against FEAT-IDEN-001 §III.2.6 and FEAT-CORE-000 §III.4)

**FEAT-IDEN-001 §III.2.6 states:**
> "Audit Trace:
>    * Call `DOM-OPS` to record the `ACT-IDEN-001` event with `correlation_id` linked to the `roster_seat_id`."

**FEAT-CORE-000 §III.4 (Audit Logging & Correlation) states:**
> "Every FEAT execution **MUST** emit an audit record via DOM-OPS containing:
>    * FEAT identifier
>    * actor (`user_id`, `seat_id`, `class_id`)
>    * `correlation_id`: A unique identifier...
>    * input payload (sanitized)
>    * result (success/failure)
>    * timestamp"

**Current Implementation:**
- ❌ **No audit record is emitted anywhere in the claim flow**
- Checked: No calls to DOM-OPS, no ACT-IDEN-001 events, no correlation_id tracking

**Violation Category:** CRITICAL
- Claim operations are completely unauditable
- No evidence trail for security analysis
- Violates FEAT-CORE-000 §IX (Compliance Requirements): "All FEAT implementations **MUST**... emit audit logs"

---

### 9. FEAT-IDEN-001 IDEMPOTENCY NOT ENFORCED (Against FEAT-IDEN-001 §V)

**FEAT-IDEN-001 §V states:**
> "Mechanism: The combination of `user_id` (or identity hash) and `class_id` acts as a natural idempotency lock."
> "Behavior: If a retry occurs with the same credentials for a seat already claimed by that user, the FEAT SHOULD return the existing `seat_id` with a `SUCCESS` status rather than failing."

**Current Implementation:**
- ❌ No idempotency_key is tracked
- ❌ If the user submits the form twice, two separate seat-lookup queries happen
- ❌ No retry protection

---

## Root Cause Analysis

### Why Is This Broken?

The route is decorated with `@feat_shell("FEAT-IDEN-001")` (line 524 in app/routes/student.py), but:

1. **FEAT-IDEN-001 is not implemented as a callable FEAT module** — There is no `app/feats/identity_claim_feat.py` or similar
2. **The route handler directly performs domain operations** instead of delegating to a FEAT
3. **The `feat_shell` decorator is a "legacy containment shell"** (per app/feats/base.py:421) that only logs FEAT-SHELL-DIRTY warnings
4. **The route was built before FEAT-CORE-000 enforcement** and hasn't been refactored to comply

### Why Was Identity Domain Certified Despite This?

The Identity Domain was likely certified on the basis that:
- ✅ DOM-IDEN-001 objects (User, Seat, Class, IdentityProfile) are correctly modeled
- ✅ DOM-IDEN-002 credential and claim fields are present on the schema
- ❌ But the **FEAT-IDEN-001 orchestration** that's supposed to use these objects is incomplete
- ❌ And the **route implementation** doesn't use a FEAT at all

This is a case of **domain-level certification without FEAT-level orchestration** — the objects are right, but the operations are broken.

---

## Constitutional Violations Summary

| FEAT-CORE-000 Rule | Requirement | Current Status | Severity |
|------------------|-------------|-----------------|----------|
| §III.1 | Resolve context (user_id, seat_id, class_id) before domain interaction | ❌ Deferred | CRITICAL |
| §III.2 | Single atomic transaction for all mutations | ❌ Split across requests | CRITICAL |
| §III.4 | Emit audit record with FEAT ID, actor, correlation_id | ❌ Missing | CRITICAL |
| §IV | Cross-domain coordination ONLY within FEAT | ❌ Inline in route | CRITICAL |
| §VII.1 | Scoped to resolved seat_id | ❌ Deferred | CRITICAL |
| §VII.2 | Binding integrity — atomic within FEAT | ❌ Split & deferred | CRITICAL |

| FEAT-IDEN-001 Section | Requirement | Current Status | Severity |
|-----------------|-------------|-----------------|----------|
| §II | Accept join_code, credentials (first_initial, last_name, dob_sum), idempotency_key | ⚠️ Partial (no dob_sum) | MEDIUM |
| §III.1 Step 1 | Resolve class_id from join_code | ✓ Done | PASS |
| §III.1 Step 2 | Resolve roster seat matching credential hashes | ⚠️ Done but incomplete (no dob_sum) | MEDIUM |
| §III.1 Step 3 | Identity Resolution (search for existing User) | ❌ Missing | CRITICAL |
| §III.2.1 | User Provisioning (create or reuse atomically) | ❌ Deferred to later request | CRITICAL |
| §III.2.2 | Seat Binding (atomic with user creation) | ❌ Deferred to later request | CRITICAL |
| §III.2.3 | PII Scrubbing (zero out hashes) | ❌ Missing | CRITICAL |
| §III.2.4 | Membership Initialization | ❌ Missing | CRITICAL |
| §III.2.5 | Context Restoration (set last_active_*) | ✓ Done | PASS |
| §III.2.6 | Audit Trace (ACT-IDEN-001 event) | ❌ Missing | CRITICAL |
| §IV | Atomic Binding | ❌ Split across requests | CRITICAL |
| §V | Idempotency lock (user_id + class_id) | ❌ Not implemented | MEDIUM |

---

## Evidence References

**File: app/routes/student.py**
- Line 524: `@feat_shell("FEAT-IDEN-001")` — Decorator says FEAT-IDEN-001 but implementation is inline
- Lines 542-546: Form collects `join_code`, `first_name`, `last_name` (missing `dob_sum`, `existing_user_id`)
- Lines 549-574: Inline ClassEconomy and Seat queries (should be in FEAT)
- Lines 576-611: Inline hash computation and seat matching (should be in FEAT)
- Line 616: Store seat_ref in session (breaks atomicity)
- Lines 693-699: User creation deferred to `setup_pin_passphrase()` (breaks FEAT contract)

**File: app/services/classroom_setup.py**
- Lines 215-241: `create_student_user_for_seat()` does binding but missing ClassMembership and audit
- Line 277-279: `roster_fingerprint` is computed but never used as identity_hash for existing User search

**File: app/feats/base.py**
- Line 421: `feat_shell()` decorator is "legacy containment shell" — not enforcing FEAT boundaries
- Lines 461-468: Special handling for FEAT-IDEN-002 but nothing for FEAT-IDEN-001 claim

**File: docs/FEATURE-EXECUTION/FEAT-IDEN-001_STUDENT_SEAT_CLAIM.md**
- §II: Specifies required inputs (dob_sum, existing_user_id) — NOT collected in form
- §III: Specifies verification and mutation phases — NOT both performed atomically
- §III.1.3: Specifies identity resolution — NOT implemented in route
- §IV: Specifies atomic binding — violated by request split

**File: docs/DOMAIN/DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE.md**
- §VIII.IV Step 7: "On successful claim, the seat is bound to user_id" — deferred instead
- §VIII.IV Step 9: Initialize last_active_* — ✓ done in classroom_setup
- §VIII, Line 204: "identity inference prohibition" — not violated (because inference isn't attempted)

---

## Recommendations

### Immediate Actions (P0)

1. **Implement proper FEAT-IDEN-001 orchestration**
   - Create `app/feats/identity_claim_feat.py` with callable FEAT that encapsulates all claim logic
   - Move inline domain operations from route into FEAT
   - Enforce single atomic transaction

2. **Add missing identity resolution phase**
   - Collect `dob_sum` and optional `existing_user_id` from form
   - Implement identity_hash (first_initial + dob_sum) search
   - Validate no duplicate claims in same class

3. **Add PII scrubbing on successful claim**
   - Zero out `claim_first_name_hash` and `claim_last_name_hash` after claim completes
   - Or move to read-only lookup table separate from Seat

4. **Add audit trace emission**
   - Emit ACT-IDEN-001 event after successful claim
   - Include correlation_id, user_id, seat_id, class_id

### Short-term Actions (P1)

5. **Add ClassMembership initialization**
   - Call DOM-CLASS during claim to record formal membership

6. **Implement idempotency protection**
   - Track idempotency_key as (user_id|identity_hash) + class_id
   - Prevent duplicate claims from retry requests

7. **Update form and route**
   - Change route to call FEAT-IDEN-001 orchestration instead of inline logic
   - Update form validation to match FEAT spec

### Documentation Actions (P2)

8. **Update Domain Certification Status**
   - Identity Domain is **not** fully certified until FEAT-IDEN-001 orchestration is compliant
   - Current certification was based on object-level review, not operation-level

9. **Add FEAT compliance checker to CI**
   - Lint for inline domain operations in routes
   - Detect missing FEAT-CORE-000 audit traces
   - Flag deferred mutations (session-stored state that should be atomic)

---

## Conclusion

The `/student/claim-account` flow is **NOT FEAT-IDEN-001 compliant**. It performs domain operations inline instead of delegating to a FEAT, splits atomic operations across HTTP requests, and omits critical phases (identity resolution, PII scrubbing, membership initialization, audit tracing).

This is a **constitutional violation** of FEAT-CORE-000 and FEAT-IDEN-001 that must be remediated before the claim flow can be considered production-ready.

The fact that it "works" for simple cases (single student, first class) masks deeper architectural problems that will manifest as:
- Identity conflicts when students claim multiple classes
- Unauditable claim operations
- Orphaned roster hashes after claim
- Missing membership records
- Inability to retry failed claims idempotently
