# Constitutional Audit: FEAT-IDEN-* Documents
**Date:** 2026-08-09  
**Scope:** All FEAT-IDEN-* specifications against governing DOM-IDEN-* authority  
**Authority Chain:** INV-CORE → INV-ARC → DOM-IDEN → FEAT-IDEN

---

## AUDIT SCOPE

### Documents Under Review
- ✓ FEAT-IDEN-001: Student Seat Claim (exists)
- ❌ FEAT-IDEN-002: (referenced in code, NO document)
- ❌ FEAT-IDEN-003+: (no documents)

### Governing Authority Documents
- DOM-IDEN-001: Canonical Identity Model (v2.2, 2026-07-10)
- DOM-IDEN-002: Student Identity Architecture (v2.3, 2026-07-10)
- DOM-IDEN-005: Identity Binding and Lifecycle (v2.0, 2026-06-29)
- DOM-IDEN-006: Canonical Context Resolution (v1.3, 2026-07-10)
- FEAT-CORE-000: Feature Execution Constitutional Directive (v1.0, 2026-04-23)

---

## PART I: FEAT-IDEN-001 CONSTITUTIONAL AUDIT

**Document:** docs/FEATURE-EXECUTION/FEAT-IDEN-001_STUDENT_SEAT_CLAIM.md (v1.0, 2026-04-23)

### Section I: Purpose

**Document Claims:**
> "This FEAT orchestrates the binding of a Global User to a Class-Local Seat. It is the primary entry point for a student to join a class, either as a new user or an existing user joining a new class."

**Validation Against Governing Authority:**

- ✓ **DOM-IDEN-005 §VII**: "Student participation SHALL become active through either unauthenticated claim or authenticated class binding."
  - **Status**: COMPLIANT — FEAT-IDEN-001 handles unauthenticated claim

- ⚠️ **"existing user joining a new class"**: 
  - **DOM-IDEN-005 §VII, line 107**: "If a human entity with existing `user` row used an unauthenticated claim path to claim a new seat, the workflow SHALL provision a new User because no authenticated principal exists..."
  - **ISSUE**: FEAT-IDEN-001 says it handles "existing user joining a new class" but DOM-IDEN-005 says unauthenticated claim **SHALL NOT** reuse existing users
  - **Status**: ❌ **CONTRADICTORY** — Document promises reuse, spec forbids it

---

### Section II: Execution Context

#### Subsection II.1: Required Inputs

**Document Claims:**
```
* `join_code`: Valid join code for the target class.
* `credentials`:
    * `first_initial`
    * `last_name` (Fuzzy matched)
    * `dob_sum` (Hashed)
* `idempotency_key`: Client-provided unique request ID.
* `existing_user_id`: (Optional) If the student is already logged in and adding a second class.
```

**Validation:**

1. **`join_code`**: ✓ COMPLIANT with DOM-IDEN-006 §VI (join_code is valid boundary ingress)

2. **`first_initial`**: ⚠️ **AMBIGUOUS**
   - Document says "first_initial" (one character)
   - DOM-IDEN-002 §VIII doesn't specify exact granularity
   - **Issue**: Current code uses full `first_name` (lines 544, 576), not `first_initial`
   - **Status**: ⚠️ NEEDS CLARIFICATION

3. **`last_name` (Fuzzy matched)**: ✓ COMPLIANT
   - DOM-IDEN-002 §VIII.IV shows last_name matching in current implementation
   - Use of "Fuzzy matched" is implementation detail (not constitutional)

4. **`dob_sum` (Hashed)**: ❌ **NOT IMPLEMENTED**
   - FEAT-IDEN-001 requires `dob_sum` as identity credential
   - DOM-IDEN-002 does NOT mention DOB at all
   - **CRITICAL CONTRADICTION**: FEAT-IDEN-001 requires DOB, DOM-IDEN-002 forbids it
   - **Evidence**: DOM-IDEN-002 §IX (Account Recovery) line 320: "No identity verification fields (name, DOB, or any PII) are re-entered"
   - **Evidence**: DOM-IDEN-002 §XI (Forbidden Patterns) line 342: "DOB or DOB-derived fields for any purpose"
   - **Status**: ❌ **CONSTITUTIONAL VIOLATION** — FEAT-IDEN-001 requires DOB, but DOM-IDEN-002 explicitly forbids DOB usage

5. **`idempotency_key`**: ✓ COMPLIANT with FEAT-CORE-000 §III.3 (Idempotency MANDATORY)

6. **`existing_user_id`**: ❌ **CONTRADICTS DOM-IDEN-005**
   - FEAT-IDEN-001 §II requires optional `existing_user_id` for "existing user joining new class"
   - DOM-IDEN-005 §VII §VII forbids existing user search in unauthenticated claim
   - **Status**: ❌ **CONSTITUTIONAL VIOLATION**

---

#### Subsection II.2: Resolved Context

**Document Claims:**
```
* `class_id`: Resolved via `join_code`.
* `roster_seat_id`: The unclaimed seat in the teacher's roster matching the credentials.
```

**Validation:**

- ✓ `class_id` resolution: COMPLIANT with DOM-IDEN-006 and FEAT-IDEN-001 §III.1 Step 1
- ✓ `roster_seat_id` resolution: COMPLIANT with DOM-IDEN-005 §VII (match roster seat)

---

### Section III: Orchestration Logic

#### Subsection III.1: Verification Phase (Read-Only)

**Document Claims:**
> "1. Resolve Class: Look up `class_id` from `join_code`.
> 2. Resolve Roster Seat: Query `DOM-IDEN` (Roster) for an unclaimed seat matching the credential hashes.
> 3. Identity Resolution (Controlled Global):"

**Validation Step 1-2:** ✓ COMPLIANT

**Validation Step 3: Identity Resolution**

**Document Claims:**
```
* Objective: Find a `User` record that belongs to this human while preventing accidental binding to a different person with similar initials/DOB.
* Lookup: Search for an existing `User` matching the `identity_hash` (First Initial + DOB Sum).
* Validation: If an `existing_user_id` was provided in the request (e.g., they are logged in), it MUST match the found user.
* Conflict Check: If the found `User` is already bound to a different `seat_id` in the SAME `class_id`, abort with `ALREADY_CLAIMED`.
```

**Status: ❌ CONSTITUTIONAL VIOLATION (Multiple Issues)**

**Issue 1: DOB-based identity_hash**
- FEAT-IDEN-001 assumes `identity_hash = First Initial + DOB Sum`
- **Governing Authority:** DOM-IDEN-002 §XI (Forbidden Patterns, line 342): "DOB or DOB-derived fields for any purpose"
- **Consequence**: This entire section is built on a prohibited foundation
- **Status**: ❌ CONSTITUTIONAL VIOLATION

**Issue 2: Existing User Search in Unauthenticated Claim**
- FEAT-IDEN-001 says: "Search for an existing `User` matching the `identity_hash`"
- **Governing Authority:** DOM-IDEN-005 §VII, lines 107-108: 
  > "unauthenticated claim SHALL NOT search for or infer existing User identities outside the current claim transaction. If a human entity with existing `user` row used an unauthenticated claim path to claim a new seat, the workflow SHALL provision a new User because no authenticated principal exists and the system SHALL NOT infer or merge existing identities."
- **Status**: ❌ **EXPLICIT PROHIBITION** in governing spec

**Issue 3: existing_user_id Parameter**
- FEAT-IDEN-001 §III.1.3 says: "If an `existing_user_id` was provided in the request (e.g., they are logged in), it MUST match the found user."
- **Problem**: An unauthenticated user cannot provide `existing_user_id` — they are not logged in
- **If logged in**: That's not unauthenticated claim, that's "authenticated class binding" (separate workflow)
- **Status**: ⚠️ **CONFLATES TWO DIFFERENT WORKFLOWS**

**Issue 4: "Controlled Global" Phrase**
- Document says: "Identity Resolution (Controlled Global)"
- **Meaning unclear**: Is this saying the search is "global" but "controlled"?
- **Conflict with DOM-IDEN-005**: Which says "SHALL NOT search... outside the current claim transaction"
- **Status**: ⚠️ **AMBIGUOUS WORDING** masks constitutional violation

---

#### Subsection III.2: Mutation Phase (Atomic Transaction)

**Document Claims:**
```
1. User Provisioning:
   * If `User` found: Use `user_id`.
   * If `User` not found: Create new `User` record in `DOM-IDEN`.
```

**Status: ❌ CONTRADICTS DOM-IDEN-005**

- FEAT-IDEN-001 §III.2.1 says "If User found: Use user_id"
- **Governing Authority:** DOM-IDEN-005 §VII, lines 107-108: "the workflow SHALL provision a new User because no authenticated principal exists and the system SHALL NOT infer or merge existing identities"
- **Status**: ❌ **EXPLICIT CONTRADICTION** — Spec says always create new, FEAT says reuse if found

**Document Claims (continued):**
```
2. Seat Binding:
   * Create Authoritative `Seat`: Link `user_id` to `class_id` and the `roster_seat_id`.
```

**Status: ✓ COMPLIANT** with DOM-IDEN-005 §VIII (Identity Binding)

**Document Claims:**
```
3. Roster Finalization (PII Scrubbing):
   * Update Roster Seat: set `is_claimed = True`, `claimed_at = NOW`, and bind the resolved `user_id` to the claimed seat record.
   * Explicit Scrub: MUST zero out `last_name_hash_part` and `dob_sum_hash` to prevent future collision or recovery leaks.
```

**Status: ⚠️ CONTRADICTORY**

- Document says to "zero out `dob_sum_hash`"
- But DOM-IDEN-002 §XI forbids DOB storage entirely
- **Question**: Why scrub something that shouldn't exist in the first place?
- **Status**: ⚠️ **REVEALS INTERNAL CONTRADICTION** in FEAT-IDEN-001 design

**Document Claims:**
```
4. Membership Initialization:
   * Call `DOM-CLASS` to record `ClassMembership`.
```

**Status: ⚠️ UNDEFINED**

- No DOM-CLASS document exists to verify this
- **Current implementation**: ClassMembership is never created
- **Status**: ⚠️ **DEPENDENCY ON MISSING SPEC** (DOM-CLASS not in scope)

**Document Claims:**
```
5. Context Restoration:
   * Set `User.last_active_seat_id` to the newly bound `seat_id`.
```

**Status: ✓ PARTIALLY COMPLIANT**

- DOM-IDEN-002 §VIII.IV.9 says initialize `last_active_class_id` AND `last_active_seat_id`
- Document only mentions `last_active_seat_id`
- **Missing**: `last_active_class_id` initialization
- **Status**: ⚠️ **INCOMPLETE** (missing class_id)

**Document Claims:**
```
6. Audit Trace:
   * Call `DOM-OPS` to record the `ACT-IDEN-001` event with `correlation_id` linked to the `roster_seat_id`.
```

**Status: ✓ COMPLIANT** with FEAT-CORE-000 §III.4 (Audit Logging MANDATORY)

---

### Section IV: Invariants & Constraints

**Document Claims:**
```
1. Atomic Binding: The link between `User`, `Seat`, and `Class` must be created within the same transaction.
2. PII Scrubbing: Once a seat is claimed, the transient credential hashes (DOB Sum, Last Name Part) MUST be zeroed out in the roster record to prevent future collisions.
3. Deduplication: A `user_id` cannot be bound to two seats in the same `class_id`.
```

**Validation:**

1. **Atomic Binding**: ✓ COMPLIANT with DOM-IDEN-005 §VIII (line 130)

2. **PII Scrubbing**: ⚠️ **PROBLEMATIC**
   - References "DOB Sum, Last Name Part" as transient credentials
   - But DOM-IDEN-002 forbids DOB entirely
   - **Status**: ⚠️ **ASSUMES PROHIBITED CREDENTIAL TYPE**

3. **Deduplication**: ✓ COMPLIANT with DOM-IDEN-001 §VII (line 106: "One `User` SHALL own at most one `Seat` within a `Class`")

---

### Section V: Idempotency

**Document Claims:**
```
* Mechanism: The combination of `user_id` (or identity hash) and `class_id` acts as a natural idempotency lock.
* Behavior: If a retry occurs with the same credentials for a seat already claimed by that user, the FEAT SHOULD return the existing `seat_id` with a `SUCCESS` status rather than failing.
```

**Validation:**

- ⚠️ **"user_id (or identity hash)"**: 
  - If user not yet created, there is no user_id yet
  - If using identity_hash, that requires DOB (which is forbidden)
  - **Status**: ⚠️ **UNCLEAR IDEMPOTENCY MECHANISM** due to DOB contradiction

---

### Section VI: Audit Requirements

**Document Claims:**
```
The `DOM-OPS` audit log MUST contain:
* `user_id`
* `seat_id`
* `class_id`
* `roster_seat_id`
* `idempotency_key`
* `outcome`: (NEW_USER_CLAIMED | EXISTING_USER_LINKED | FAILED)
```

**Status: ⚠️ CONTRADICTORY OUTCOME**

- Outcome includes "EXISTING_USER_LINKED"
- But DOM-IDEN-005 forbids linking existing users in unauthenticated claim
- **Status**: ⚠️ **REVEALS DESIGN CONTRADICTION**

---

## PART II: MISSING FEAT-IDEN DOCUMENTS

### Code References to Undocumented FEATs

**FEAT-IDEN-002** referenced in:
- app/routes/student.py line 628: `@feat_shell("FEAT-IDEN-002")`
- app/routes/recovery.py (multiple references)
- tests/dom/identity/test_student_recovery.py

**Current Route:** `create_username()` (app/routes/student.py:627-657)

**DOM Authority for FEAT-IDEN-002:**
- Should be governed by DOM-IDEN-002 §VI (Student Identity Layers) and §VIII.IV (Claim Flow)
- DOM-IDEN-002 §VIII.IV Step 8: "Credential setup activates login on `users`"
- This suggests FEAT-IDEN-002 should handle credential creation

**Status**: ❌ **NO SPECIFICATION EXISTS**

---

### Other Identity-Related FEATs Referenced in Code But Undocumented

| FEAT ID | Referenced in | Purpose (Inferred) | Document Status |
|---------|--------------|-------------------|-----------------|
| FEAT-IDEN-001 | routes/student.py, recovery.py | Seat claim | ✓ Exists (but non-compliant) |
| FEAT-IDEN-002 | routes/student.py, recovery.py | Credential setup | ❌ Missing |
| FEAT-IDEN-003+ | (none found) | Recovery reset? | ❌ Unknown if needed |

---

## PART III: SYNTHESIS OF CONSTITUTIONAL VIOLATIONS

### Critical Violations (Must Fix)

| Violation ID | FEAT-IDEN-001 Assertion | Governing Authority | Issue | Severity |
|------------|----------------------|-------------------|-------|----------|
| V1 | DOB-based identity_hash | DOM-IDEN-002 §XI (line 342) | DOB usage explicitly forbidden | CRITICAL |
| V2 | Existing user search in unauthenticated claim | DOM-IDEN-005 §VII (lines 107-108) | Explicit prohibition | CRITICAL |
| V3 | User reuse path (§III.2.1) | DOM-IDEN-005 §VII (line 107) | "SHALL provision a new User" | CRITICAL |
| V4 | existing_user_id parameter | DOM-IDEN-005 §VII | Parameter doesn't make sense for unauthenticated claim | CRITICAL |
| V5 | PII scrubbing of DOB hashes | DOM-IDEN-002 §XI | DOB shouldn't exist to scrub | MEDIUM |
| V6 | Missing last_active_class_id init | DOM-IDEN-002 §VIII.IV.9 | Should set both class_id and seat_id | MEDIUM |
| V7 | Audit outcome "EXISTING_USER_LINKED" | DOM-IDEN-005 §VII | Outcome that shouldn't occur | MEDIUM |

---

## PART IV: ROOT CAUSE ANALYSIS

### Why FEAT-IDEN-001 Is Non-Compliant

1. **Specification Date Mismatch:**
   - FEAT-IDEN-001: v1.0, 2026-04-23
   - DOM-IDEN-002: v2.3, 2026-07-10 (updated AFTER FEAT)
   - DOM-IDEN-005: v2.0, 2026-06-29 (updated AFTER FEAT)
   - **Likely Cause**: FEAT was written before DOM specs were finalized

2. **DOB Assumption:**
   - FEAT-IDEN-001 assumes DOB-based identity_hash throughout
   - But DOM-IDEN-002 v2.3 explicitly forbids DOB
   - **Inference**: DOB usage was removed from DOM-IDEN-002 after FEAT-IDEN-001 was written

3. **Conflated Workflows:**
   - FEAT-IDEN-001 conflates "unauthenticated claim" with "existing user joining class"
   - DOM-IDEN-005 clearly distinguishes these as separate workflows
   - **Inference**: FEAT-IDEN-001 doesn't properly model the two separate pathways

---

## PART V: COMPLIANCE ASSESSMENT

### FEAT-IDEN-001 Overall Status: **NON-COMPLIANT**

**Verdict:** FEAT-IDEN-001 is constitutionally non-compliant and must be substantially rewritten.

**Non-Compliant Sections:**
- ✗ Section II.1 (Required Inputs) — References prohibited DOB
- ✗ Section III.1 Step 3 (Identity Resolution) — Contradicts DOM-IDEN-005
- ✗ Section III.2.1 (User Provisioning) — Contradicts DOM-IDEN-005
- ✗ Section IV (Invariants) — Assumes prohibited DOB
- ✗ Section V (Idempotency) — Unclear due to DOB contradiction
- ✗ Section VI (Audit) — References impossible outcome

**Compliant Sections:**
- ✓ Section I (Purpose) — Partially correct
- ✓ Section III.2.2 (Seat Binding) — Correct
- ✓ Section III.2.5 (Context Restoration) — Mostly correct
- ✓ Section III.2.6 (Audit Trace) — Correct concept (but outcome is wrong)

### FEAT-IDEN-002+ Status: **NON-EXISTENT**

FEAT-IDEN-002 is referenced in code but has no specification document. Cannot audit without document.

---

## RECOMMENDATIONS

### Immediate Actions (P0 - Block All Identity Work)

1. **Declare FEAT-IDEN-001 Non-Compliant**
   - Audit complete; document fails constitutional validation
   - Identity domain cannot be certified until FEAT-IDEN-001 is compliant

2. **Rewrite FEAT-IDEN-001 Against DOM Authority**
   - Remove all DOB references
   - Remove existing user search from unauthenticated claim path
   - Clarify the two separate workflows (unauthenticated claim vs authenticated class binding)
   - Fix all audit outcome options

3. **Create FEAT-IDEN-002 Specification**
   - Document the credential-setup phase
   - Specify how PIN and passphrase are activated
   - Link to DOM-IDEN-002 §VIII.IV Steps 8-9

4. **Identify Other Missing FEAT-IDEN-* Documents**
   - Account recovery likely needs FEAT-IDEN-003 or similar
   - Check code for FEAT-IDEN-003+, 004+ references

---

## APPENDIX A: Detailed Contradiction Matrices

### DOM-IDEN-005 vs FEAT-IDEN-001: Identity Resolution Workflow

| Aspect | DOM-IDEN-005 §VII | FEAT-IDEN-001 | Conflict |
|--------|-----------------|--------------|---------|
| Existing User Search | "SHALL NOT search for or infer existing User identities outside the current claim transaction" | "Search for an existing `User` matching the `identity_hash`" | ❌ Direct contradiction |
| User Reuse | "workflow SHALL provision a new User" | "If `User` found: Use `user_id`" | ❌ Direct contradiction |
| Identity Credential | Not specified (no DOB) | "identity_hash (First Initial + DOB Sum)" | ❌ Uses forbidden credential |
| New User Path | Allowed | Allowed | ✓ Agreement |
| Outcome Tracking | Not specified | "EXISTING_USER_LINKED" | ❌ References forbidden outcome |

### DOM-IDEN-002 vs FEAT-IDEN-001: PII Handling

| Aspect | DOM-IDEN-002 | FEAT-IDEN-001 | Conflict |
|--------|-------------|--------------|---------|
| DOB Usage | "DOB or DOB-derived fields for any purpose" — FORBIDDEN (§XI, line 342) | "dob_sum (Hashed)" — Required input | ❌ Fundamental contradiction |
| PII Scrubbing | Not mentioned | "MUST zero out... `dob_sum_hash`" | ⚠️ Assumes prohibited data |
| Credential Types | PIN, Passphrase only | PIN, Passphrase, + identity_hash | ❌ Extra credential forbidden |

---

## FINAL CERTIFICATION

**This audit certifies that:**

1. **FEAT-IDEN-001** is **NOT constitutionally compliant** with governing DOM-IDEN authority
2. **FEAT-IDEN-002+** documents **DO NOT EXIST** and must be created
3. **Identity domain certification** is **INVALID** until FEAT-IDEN-001 is rewritten and compliant
4. **Code implementation** reflects the non-compliant spec and must be updated after spec is fixed

---

**Audit Completed:** 2026-08-09  
**Authority:** Constitutional Audit per DOM-IDEN-005 §X (Cross-Domain Authority)  
**Next Action:** FEAT-IDEN-001 Rewrite (P0 blocking item)
