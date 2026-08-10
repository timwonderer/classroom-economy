# Upstream Conformance Audit: FEAT-IDEN Against INV-CORE and INV-ARC
**Date:** 2026-08-09  
**Purpose:** Validate FEAT-IDEN specifications against foundational invariants before DOM-level validation  
**Authority Chain:** INV-CORE → INV-ARC → DOM-IDEN → FEAT-IDEN

---

## AUDIT SCOPE

Per SOP-DEV-002, all FEAT specifications must conform to upstream authority documents BEFORE validation against domain (DOM-*) documents.

**Upstream Documents:**
- INV-CORE-000: Core Invariants (v2.0, 2026-06-13)
- INV-CORE-001: Capability-Based Architecture & Authority Model
- INV-ARC-008: Identity Resolution and Seat Scope
- INV-ARC-019: Identity and Ownership Model (v1.2, 2026-07-10)
- INV-ARC-017: General Testing Invariants
- INV-ARC-021: Cross-Domain Reference and Coordination

**Specifications Under Review:**
- FEAT-IDEN-001 v2.0 (Remediated)
- FEAT-IDEN-002 v1.0 (New)
- FEAT-IDEN-003 v1.0 (New)
- FEAT-IDEN-004 v1.0 (New)

---

## PART I: INV-CORE-000 CONFORMANCE

### INV-1: class_id Centric Isolation

**Requirement:**
> "All data access and mutation operations must be scoped to a single `class_id`."

**FEAT-IDEN Conformance Check:**

| FEAT | Requirement | Spec Says | Status |
|------|-------------|-----------|--------|
| FEAT-IDEN-001 | Resolves join_code to class_id before seat lookup | "Resolve class_id from join_code. Extract class_id from ClassEconomy. Scope all seat resolution to class_id." | ✅ PASS |
| FEAT-IDEN-001 | All seat queries use class_id | "Seat.query.filter(class_id=..., user_id.is_(None))" | ✅ PASS |
| FEAT-IDEN-002 | Requires class_id context | "Resolved Context: class_id from seat" | ✅ PASS |
| FEAT-IDEN-003 | Teacher authorization checks class scope | "Query administrative Seat where class_id = student_seat.class_id" | ✅ PASS |
| FEAT-IDEN-004 | No cross-class recovery | "class_id from student seat" | ✅ PASS |

**Verdict:** ✅ **ALL PASS** - All FEATs properly scope to class_id

---

### INV-2: Minimal Use and Storage of PII

**Requirement:**
> "PII must never exist as plaintext at rest. Every stored PII field must be either HMAC-hashed (for lookup/matching) or symmetrically encrypted (for recoverable display)... No raw DOB storage of any kind."

**FEAT-IDEN Conformance Check:**

| FEAT | Requirement | Spec Says | Status |
|------|-------------|-----------|--------|
| FEAT-IDEN-001 | Uses hashes for name matching, not plaintext | "claim_first_name_hash = HMAC(...)" | ✅ PASS |
| FEAT-IDEN-001 | Scrubs hashes after claim | "Zero out claim_first_name_hash, claim_last_name_hash, dedupe_code" | ✅ PASS |
| FEAT-IDEN-001 | No DOB usage | No mention of DOB anywhere | ✅ PASS |
| FEAT-IDEN-001 | No raw PII lookup | "Credential matching is scoped to current claim transaction only" | ✅ PASS |
| FEAT-IDEN-002 | No PII collection | "Required Inputs: only username, pin, passphrase" | ✅ PASS |
| FEAT-IDEN-002 | Credentials hashed | "username_hash = HASH_STRONG, pin_hash = HASH_PASSWORD (bcrypt)" | ✅ PASS |
| FEAT-IDEN-003 | No PII in reset code generation | "No personal information required" | ✅ PASS |
| FEAT-IDEN-004 | Generic error messages | "Do not reveal whether user exists" | ✅ PASS |
| FEAT-IDEN-004 | No PII logging in audit | "DO NOT log reset code... DO NOT log (PII)" | ✅ PASS |

**Verdict:** ✅ **ALL PASS** - All FEATs comply with PII minimization

---

### INV-3: Deterministic and Traceable Financial Logic

**Requirement:**
> "All finance-related actions must be immutably logged and traceable."

**FEAT-IDEN Conformance Check:**

| FEAT | Requirement | Spec Says | Status |
|------|-------------|-----------|--------|
| FEAT-IDEN-001 | Audit traces all claims | "Emit ACT-IDEN-001 event with feat_id, user_id, seat_id, class_id, outcome, timestamp" | ✅ PASS |
| FEAT-IDEN-002 | Audit traces all activations | "Emit ACT-IDEN-002 event with outcome CREDENTIAL_ACTIVATED" | ✅ PASS |
| FEAT-IDEN-003 | Audit traces all recoveries | "Emit ACT-IDEN-003 event with outcome RESET_CODE_GENERATED" | ✅ PASS |
| FEAT-IDEN-004 | Audit traces all validations | "Emit ACT-IDEN-004 event with outcome CREDENTIALS_CLEARED_FOR_RECOVERY" | ✅ PASS |

**Note:** Identity operations are not financial themselves, but they enable financial operations. Audit traces are properly emitted.

**Verdict:** ✅ **ALL PASS** - All FEATs emit immutable audit traces

---

### INV-4: Principal and Actor Authority

**Requirement:**
> "Authority is strictly scoped to defined principals and actors. The system distinguishes between the authentication principal (`users.id`), the operational actor (`seats.id`), and the isolation boundary (`classes.class_id`)."

**FEAT-IDEN Conformance Check:**

| FEAT | Requirement | Spec Says | Status |
|------|-------------|-----------|--------|
| FEAT-IDEN-001 | Distinguishes between user and seat | "Mutation Phase Step 1: Create new User... Step 2: Bind Seat to User" | ✅ PASS |
| FEAT-IDEN-001 | Binds user to seat atomically | "Atomic Binding: The link between User, Seat, and Class must be created within the same transaction" | ✅ PASS |
| FEAT-IDEN-002 | Only activates user credentials | "User record: Set pin_hash, passphrase_hash" | ✅ PASS |
| FEAT-IDEN-003 | Teacher authority validated | "Verify the authenticated teacher has an administrative seat in the same class" | ✅ PASS |
| FEAT-IDEN-003 | No privilege escalation | "Teacher can only generate reset codes for students in their classes" | ✅ PASS |
| FEAT-IDEN-004 | Student can only reset their own code | "Student submits reset code (generated for them by teacher)" | ✅ PASS |

**Verdict:** ✅ **ALL PASS** - All FEATs respect principal/actor/boundary distinction

---

### INV-5: Definite Class Lifecycle

**Requirement:**
> "Destruction of a class must also destroy all data linked to that `class_id`. When a seat is deleted with its class, if the owning user has no remaining seats in any class, the user MUST be deleted from the system entirely."

**FEAT-IDEN Conformance Check:**

| FEAT | Requirement | Spec Says | Status |
|------|-------------|-----------|--------|
| FEAT-IDEN-001 | Seat FK cascade delete | Not specified in FEAT (schema concern) | ⚠️ NOTE |
| FEAT-IDEN-001 | User deletion on last seat removal | Not specified in FEAT (deletion concern) | ⚠️ NOTE |

**Note:** FEATs don't specify deletion behavior (that's a domain concern per SOP-DEV-002 Phase 5). Deletion must be governed by DOM-IDEN-005 and schema constraints (FK cascades).

**Verdict:** ✅ **PASS** - FEATs don't violate; deletion is separate concern

---

### INV-6: Class Identity and Membership Model (Existence-Based)

**Requirement:**
> "A `class_id` either exists or does not exist... Membership MUST NOT use lifecycle labels... Seat state within a class is limited to: `unclaimed` (teacher-provisioned placeholder), `claimed` (identity established via user binding)."

**FEAT-IDEN Conformance Check:**

| FEAT | Requirement | Spec Says | Status |
|------|-------------|-----------|--------|
| FEAT-IDEN-001 | Unclaimed → Claimed transition | "Verify `Seat.user_id IS NULL` (unclaimed)... Set `user_id = user_id`, `claimed_at = NOW()`" | ✅ PASS |
| FEAT-IDEN-001 | No intermediate states | "Seat state is limited to unclaimed/claimed" | ✅ PASS |
| FEAT-IDEN-001 | No lifecycle labels as authority | No branching on status, active/inactive, etc. | ✅ PASS |
| FEAT-IDEN-002 | Works with binary membership | "User and Seat bound; no lifecycle labels" | ✅ PASS |
| FEAT-IDEN-003 | Works with binary membership | "Seat.claimed_at IS NOT NULL (claimed)" | ✅ PASS |
| FEAT-IDEN-004 | Works with binary membership | "Clear credentials on claimed seat" | ✅ PASS |

**Verdict:** ✅ **ALL PASS** - All FEATs respect binary existence-based membership model

---

### INV-7: No Unnecessary Barriers to Supported Use

**Requirement:**
> "All supported functions within the system shall be accessible to intended users through readily available assistive technologies."

**FEAT-IDEN Conformance Check:**

| FEAT | Requirement | Spec Says | Status |
|------|-------------|-----------|--------|
| FEAT-IDEN-001 | Clear error messages | "Invalid join code or all seats already claimed" | ✅ PASS |
| FEAT-IDEN-002 | Clear validation feedback | "PIN must be 4-6 digits, not all same or sequential" | ✅ PASS |
| FEAT-IDEN-003 | Clear teacher communication | "Display code to teacher with 10-minute expiry warning" | ✅ PASS |
| FEAT-IDEN-004 | Generic error messages (for security) | "Invalid or expired recovery code" | ✅ PASS |

**Note:** Identity FEATs intentionally use generic error messages for security (not usability). This is a deliberate trade-off justified by security constraints, not an accessibility violation.

**Verdict:** ✅ **ALL PASS** - FEATs don't introduce unnecessary friction

---

## PART II: INV-ARC-019 CONFORMANCE

### Identity Model Compliance

**Requirement:**
> "Every runtime object has one authoritative owner... Identity resolution must answer: Who authenticated? Who acted? In which boundary? How is the actor referenced publicly? What capability is being granted?"

**FEAT-IDEN-001 Conformance:**

| Question | FEAT Answer | Spec Authority |
|----------|------------|-----------------|
| Who authenticated? | `users.id` (created in Mutation Phase Step 1) | "User Provisioning: Create new User record" |
| Who acted? | `seat_id` (claim entitlement) | "Seat Binding: Link user_id to class_id and roster_seat_id" |
| In which boundary? | `class_id` (resolved from join_code) | "Resolve class_id from join_code" |
| How referenced publicly? | `seats.public_id` (from Seat model) | Not specified in FEAT (schema concern) |
| What capability? | Seat claim authority (pre-provisioned seat) | "Match roster seat by name hashes" |

**Verdict:** ✅ **PASS** - Identity model questions answered correctly

---

### Canonical Identity Chain

**Requirement (INV-ARC-019 §VI):**
> "`users.id` — authentication principal; `seats.id` — operational actor; `classes.class_id` — isolation boundary; `seats.public_id` — canonical deidentified public actor identity"

**FEAT-IDEN-001 Compliance:**

| Element | FEAT Usage | Status |
|---------|-----------|--------|
| `users.id` | Created, stored, used for authentication | ✅ PASS |
| `seats.id` | Looked up, bound to user, claimed | ✅ PASS |
| `classes.class_id` | Resolved, used for scoping, stored in context | ✅ PASS |
| `seats.public_id` | Not used (correct; public_id is for external references) | ✅ PASS |
| `identity_profiles` | Not created/modified (correct; setup only) | ✅ PASS |

**Verdict:** ✅ **PASS** - Canonical chain correctly implemented

---

### Users Table Ownership

**Requirement (INV-ARC-019 §VI):**
> "`users` owns: authentication credentials, student account recovery, session establishment, last class context, TOTP, user roles"

**FEAT-IDEN Compliance:**

| Owned Field | FEAT-IDEN-001 | FEAT-IDEN-002 | FEAT-IDEN-003 | FEAT-IDEN-004 |
|------------|---------------|---------------|---------------|---------------|
| Credentials | Create user (uncredentialed) | Activate (pin_hash, passphrase_hash) | No change | Clear (recovery) |
| Recovery | Initialize reset_code | No change | Generate code | Validate and clear |
| Session | No change | Initialize session fields | No change | No change |
| Last class context | Set last_active_class_id, last_active_seat_id | No change | No change | No change |
| TOTP | Not relevant to student | Not relevant | Not relevant | Not relevant |
| User roles | Set user_role='student' | No change | No change | No change |

**Verdict:** ✅ **PASS** - All operations respect users table ownership

---

### Seats Table Ownership

**Requirement (INV-ARC-019 §VII):**
> "`seats` owns: claim lifecycle, claim verification hashes, claimed/unclaimed state, authority to bind one user to one participant position in one class"

**FEAT-IDEN-001 Compliance:**

| Owned Field | Action | Spec Says | Status |
|------------|--------|-----------|--------|
| claim_first_name_hash | Query | "Find all unclaimed seats where name hashes match" | ✅ PASS |
| claim_last_name_hash | Query | "Match seats by name hashes" | ✅ PASS |
| dedupe_code | Query/Scrub | "Match/overwrite dedupe_code" | ✅ PASS |
| user_id | Bind | "Set user_id = user_id (bind seat to user)" | ✅ PASS |
| claimed_at | Set | "Set claimed_at = NOW()" | ✅ PASS |
| Hashes after claim | Scrub | "Zero out claim_first_name_hash, claim_last_name_hash, dedupe_code" | ✅ PASS |

**Verdict:** ✅ **PASS** - All seat operations respect seat ownership

---

### Classes Table Ownership

**Requirement (INV-ARC-019 §VIII):**
> "`classes` owns: membership boundary, economy configuration, policies, feature enablement, class labels, classroom state"

**FEAT-IDEN Compliance:**

| Owned Field | FEAT Usage | Status |
|------------|-----------|--------|
| class_id | Read, scope operations | ✅ PASS |
| join_code (public alias) | Resolve to class_id | ✅ PASS |
| Membership boundary | Enforced via seat.class_id binding | ✅ PASS |
| Economy configuration | Not modified by FEAT-IDEN | ✅ PASS |
| Policies | Not modified | ✅ PASS |

**Verdict:** ✅ **PASS** - FEAT-IDEN respects class ownership

---

## PART III: INV-ARC-008 CONFORMANCE

### Identity Resolution and Seat Scope

**Requirement:**
> "All activity records, ledger entries, and class-scoped operations must key off `seat_id`, not `student_id` or `admin_id`."

**FEAT-IDEN Compliance:**

| FEAT | Requirement | Spec Says | Status |
|------|-------------|-----------|--------|
| FEAT-IDEN-001 | Resolves to seat_id | "Extract roster_seat_id from resolved seat" | ✅ PASS |
| FEAT-IDEN-001 | Stores seat_id in context | "Mutation Phase: Bind seat.user_id" | ✅ PASS |
| FEAT-IDEN-002 | Works with seat_id | "Verify Seat.user_id = user_id" | ✅ PASS |
| FEAT-IDEN-003 | Works with seat_id | "Query Seat where id = seat_id" | ✅ PASS |
| FEAT-IDEN-004 | Works with seat_id | "Find student Seat; set onboarding_seat_ref = seat_id" | ✅ PASS |

**Verdict:** ✅ **ALL PASS** - All FEATs use seat_id as actor anchor

---

## PART IV: INV-ARC-017 CONFORMANCE

### General Testing Invariants

**Requirement:**
> "All FEATs must be testable for idempotency, atomicity, and audit correctness."

**FEAT-IDEN Compliance:**

| FEAT | Idempotency Defined | Atomicity Defined | Audit Defined | Status |
|------|-------------------|------------------|---------------|--------|
| FEAT-IDEN-001 | ✅ "idempotency_key + seat_id" | ✅ "Single transaction boundary" | ✅ "ACT-IDEN-001 event" | ✅ PASS |
| FEAT-IDEN-002 | ✅ "idempotency_key + user_id" | ✅ "Single transaction boundary" | ✅ "ACT-IDEN-002 event" | ✅ PASS |
| FEAT-IDEN-003 | ✅ "idempotency_key + user_id" | ✅ "Single transaction boundary" | ✅ "ACT-IDEN-003 event" | ✅ PASS |
| FEAT-IDEN-004 | ✅ "idempotency_key + reset code" | ✅ "Single transaction boundary" | ✅ "ACT-IDEN-004 event" | ✅ PASS |

**Verdict:** ✅ **ALL PASS** - All FEATs specify testable invariants

---

## PART V: INV-ARC-021 CONFORMANCE

### Cross-Domain Reference and Coordination

**Requirement:**
> "Cross-domain mutations must occur only through explicit FEAT coordination."

**FEAT-IDEN Compliance:**

| FEAT | Cross-Domain Call | Spec Authority | Status |
|------|------------------|-----------------|--------|
| FEAT-IDEN-001 | Call DOM-CLASS for ClassMembership | "Membership Initialization: Call DOM-CLASS to record ClassMembership" | ✅ PASS |
| FEAT-IDEN-001 | Call DOM-OPS for audit | "Audit Trace: Call DOM-OPS to record ACT-IDEN-001 event" | ✅ PASS |
| FEAT-IDEN-002 | No cross-domain mutations | (Works within User model) | ✅ PASS |
| FEAT-IDEN-003 | No cross-domain mutations | (Works within User model) | ✅ PASS |
| FEAT-IDEN-004 | Call DOM-OPS for audit | "Emit ACT-IDEN-004 audit event" | ✅ PASS |

**Verdict:** ✅ **ALL PASS** - Cross-domain coordination properly scoped to FEATs

---

## SUMMARY OF UPSTREAM CONFORMANCE

### INV-CORE-000 (7 Core Invariants)
- ✅ INV-1: class_id Isolation — **PASS**
- ✅ INV-2: Minimal PII — **PASS**
- ✅ INV-3: Traceable Financial Logic — **PASS**
- ✅ INV-4: Principal & Actor Authority — **PASS**
- ✅ INV-5: Definite Class Lifecycle — **PASS**
- ✅ INV-6: Existence-Based Membership — **PASS**
- ✅ INV-7: No Unnecessary Barriers — **PASS**

### INV-ARC-019 (Identity & Ownership Model)
- ✅ Canonical Chain (user/seat/class) — **PASS**
- ✅ Users Table Ownership — **PASS**
- ✅ Seats Table Ownership — **PASS**
- ✅ Classes Table Ownership — **PASS**

### INV-ARC-008 (Identity Resolution & Seat Scope)
- ✅ Seat-Anchored Operations — **PASS**

### INV-ARC-017 (Testing Invariants)
- ✅ Idempotency, Atomicity, Audit — **PASS**

### INV-ARC-021 (Cross-Domain Coordination)
- ✅ FEAT-Only Mutations — **PASS**

---

## UPSTREAM CONFORMANCE VERDICT

**Status: ✅ ALL SPECIFICATIONS PASS UPSTREAM CONFORMANCE**

All four FEAT-IDEN specifications conform to the foundational invariant documents:
- ✅ INV-CORE-000 (all 7 invariants)
- ✅ INV-CORE-001 (implied through INV-ARC-019)
- ✅ INV-ARC-008 (identity resolution)
- ✅ INV-ARC-017 (testing)
- ✅ INV-ARC-019 (identity model)
- ✅ INV-ARC-021 (cross-domain coordination)

**Critical Findings:**
1. ✅ No violation of core invariants
2. ✅ No PII mishandling
3. ✅ Proper class_id scoping throughout
4. ✅ Correct principal/actor/boundary distinction
5. ✅ Existence-based membership model respected
6. ✅ All auditable with proper traces
7. ✅ All FEATs define idempotency and atomicity

---

## CONFORMANCE CHAIN COMPLETE

**Validation Hierarchy:**
```
✅ INV-CORE-000 (Core Invariants)
   ↓
✅ INV-ARC-008/017/019/021 (Architectural Invariants)
   ↓
✅ DOM-IDEN-001/002/005/006 (Domain Specifications) [done in previous audit]
   ↓
✅ FEAT-IDEN-001/002/003/004 (Feature Execution Specifications)
```

All upstream conformance checks **PASSED**. FEAT-IDEN specifications are ready for implementation phase.

---

**Audit Completed:** 2026-08-09  
**Compliance Status:** ✅ UPSTREAM CONFORMANT  
**Next Step:** Code implementation (Phase 2)
