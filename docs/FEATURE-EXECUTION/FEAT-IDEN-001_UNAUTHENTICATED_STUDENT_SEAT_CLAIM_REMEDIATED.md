# FEAT-IDEN-001: Unauthenticated Student Seat Claim
**[REMEDIATED - Compliant with DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-001 | 2.0 | 2026-08-09 | 1.0 (non-compliant) | Normative | REMEDIATED |

---

## I. Purpose

This FEAT orchestrates the unauthenticated binding of a newly provisioned `User` to a classroom `Seat`. It is the primary entry point for a student to claim their classroom participation through a teacher-provided join code.

> [!IMPORTANT]
>
> **Scope Clarification:** This FEAT handles **unauthenticated claim only**. It is for students claiming a classroom seat without prior authentication. For authenticated users joining a new classroom (reusing existing credentials), see **FEAT-IDEN-004** (Authenticated Class Binding).

**Governing Authority:**
- DOM-IDEN-005 §VII (Student Identity Lifecycle)
- DOM-IDEN-002 §VIII (Student Claim Flow)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `join_code`: Valid join code for the target class.
* `credentials`:
    * `first_name`: Student's first name (full or partial, as provided by teacher roster)
    * `last_name`: Student's last name (full or partial, as provided by teacher roster)
    * `dedupe_code`: (Optional) Short code provided by teacher to disambiguate duplicate names
* `idempotency_key`: Client-provided unique request ID for retry safety.

**Prohibited Inputs:** None of the following may be accepted:
- ❌ DOB or DOB derivatives (per DOM-IDEN-002 §XI)
- ❌ `existing_user_id` (unauthenticated claim cannot reference existing users)
- ❌ `identity_hash` (no cross-user identity inference)

### 2. Resolved Context (MANDATORY)

The FEAT MUST resolve the following before mutation:
* `class_id`: Resolved via `join_code` (classroom universe)
* `roster_seat_id`: The unclaimed seat in the classroom's roster matching the credential hashes

---

## III. Orchestration Logic

### A. Verification Phase (Read-Only)

The following validation steps SHALL occur before any mutations:

#### Step 1: Resolve Class
1. Look up `ClassEconomy` record where `join_code` matches the provided code.
2. Extract `class_id` from the resolved `ClassEconomy`.
3. **Failure Behavior**: If no class found, abort with `INVALID_JOIN_CODE`.

#### Step 2: Resolve Roster Seat
1. Query all unclaimed seats where:
   - `class_id` matches the resolved class
   - `user_id IS NULL` (unclaimed per DOM-IDEN-005 §VII)
2. Compute name match hashes:
   - `claim_first_name_hash = HMAC(server_secret, normalize(first_name))`
   - `claim_last_name_hash = HMAC(server_secret, normalize(last_name))`
3. Find all seats where both name hashes match the computed hashes.
4. **Deduplication Logic**:
   - If exactly one seat matches: Use that seat.
   - If multiple seats match: Require `dedupe_code` from student.
     - Find seats where `dedupe_code` matches the provided code.
     - If exactly one seat matches after dedupe: Use that seat.
     - If zero or multiple seats match: abort with `INVALID_CREDENTIALS` or `AMBIGUOUS_IDENTITY`.
   - If zero seats match: abort with `INVALID_CREDENTIALS`.
5. Extract `roster_seat_id` from the resolved seat.
6. **Failure Behavior**: Abort immediately if any step fails, with no user discovery.

#### Step 3: Identity Inference Prohibition Check
Per DOM-IDEN-005 §VII (Identity Inference Prohibition):
> "unauthenticated claim SHALL NOT search for or infer existing User identities outside the current claim transaction."

This FEAT **SHALL NOT**:
- ❌ Search for existing `User` records
- ❌ Compute or use identity_hash (DOB-based or otherwise)
- ❌ Check if a user with similar credentials already exists
- ❌ Reuse or link to any pre-existing `User`

**Rationale**: The unauthenticated claim context provides no way to authenticate that a returning student is the same human. Therefore, identity merging is prohibited by constitutional law.

---

### B. Mutation Phase (Atomic Transaction)

All mutations in this section **MUST** occur within a single database transaction. **Any failure SHALL trigger complete rollback.**

#### Step 1: User Provisioning (NEW USER ONLY)

Per DOM-IDEN-005 §VII:
> "the workflow SHALL provision a new User because no authenticated principal exists and the system SHALL NOT infer or merge existing identities."

1. Create a new `User` record with `user_role = 'student'`.
2. **DO NOT** populate authentication credentials (`pin_hash`, `passphrase_hash`, `username_hash`) yet.
   - These will be activated in **FEAT-IDEN-002** (Credential Setup).
   - Per DOM-IDEN-002 §VI: "A `users` row may be provisioned before claim; credentials are activated when a student claims a seat and completes setup."
3. Write the new `User` record.
4. Capture `user_id` for the next steps.

#### Step 2: Seat Binding

Per DOM-IDEN-005 §VIII (Identity Binding):
> "Binding SHALL occur atomically."

1. Update the resolved `Seat` record:
   - Set `user_id = user_id` (bind seat to the newly provisioned user)
   - Set `claimed_at = NOW()` (mark claim timestamp)
   - Set `role = 'student'` (or verify already set)
2. Verify `UNIQUE(user_id, class_id)` constraint is satisfied (only one seat per user per class).

#### Step 3: Roster Finalization (PII Scrubbing)

Per FEAT-IDEN-001 §IV (Invariants), PII on the roster seat SHALL be scrubbed:

1. **ZERO OUT claim lookup hashes** on the resolved `Seat` record:
   - Set `claim_first_name_hash = NULL`
   - Set `claim_last_name_hash = NULL`
   - Set `dedupe_code = NULL` (if used)

**Rationale**: Once a seat is claimed, these hashes are no longer needed for lookup. Leaving them creates a PII liability. If a future password reset or recovery flow were to leak the roster, the hashes would still identify the student.

#### Step 4: Membership Initialization

Per DOM-IDEN-005 §V (Membership by Existence) and FEAT-IDEN-001 §III.2.4:

1. **Call DOM-CLASS** to record the student's participation in the classroom.
   - Expected outcome: Create a formal `ClassMembership` or equivalent record (if applicable in current schema).
   - This step ensures the identity domain and class domain are synchronized.

#### Step 5: Context Restoration

Per DOM-IDEN-002 §VIII.IV.9:
> "Initialize `last_active_class_id` and `last_active_seat_id` to the newly bound class and seat context."

1. Set `User.last_active_class_id = class_id`
2. Set `User.last_active_seat_id = seat_id`

**Rationale**: These pointers enable DOM-IDEN-006 (Context Resolution) to restore the user's active class and seat upon login.

#### Step 6: Audit Trace

Per FEAT-CORE-000 §III.4 (Audit Logging & Correlation):
> "Every FEAT execution **MUST** emit an audit record via DOM-OPS."

1. Call `DOM-OPS` to emit an `ACT-IDEN-001` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-001"
   - `user_id`: The newly created `user_id`
   - `seat_id`: The claimed `seat_id`
   - `class_id`: The class context
   - `roster_seat_id`: The original unclaimed seat (for traceability)
   - `idempotency_key`: The provided key (for replay detection)
   - `outcome`: `"NEW_USER_CLAIMED"` (only possible outcome)
   - `timestamp`: ISO 8601 UTC timestamp

---

## IV. Invariants & Constraints

### 1. Atomic Binding (MANDATORY)
The link between `User`, `Seat`, and `Class` must be created within the same transaction (per DOM-IDEN-005 §VIII):
- User creation, seat binding, and context restoration all within one transaction.
- Failure at any step triggers full rollback.
- No partial claims.

### 2. New User Only (MANDATORY)
Per DOM-IDEN-005 §VII:
- **ALWAYS** create a new `User` record.
- **NEVER** search for or reuse existing users.
- **NEVER** merge identities.

### 3. PII Scrubbing (MANDATORY)
Once a seat is claimed:
- Claim lookup hashes (`claim_first_name_hash`, `claim_last_name_hash`, `dedupe_code`) SHALL be zeroed out.
- No DOB or DOB-derived data exists (per DOM-IDEN-002 §XI).

### 4. Deduplication (MANDATORY)
Per DOM-IDEN-001 §VII (line 106):
> "One `User` SHALL own at most one `Seat` within a `Class`."

The seat binding step SHALL verify this constraint is satisfied.

### 5. No Identity Inference (MANDATORY)
Per DOM-IDEN-005 §VII:
- This FEAT **SHALL NOT** use identity_hash, DOB, or any cross-user identification.
- Credential matching is scoped to the current claim transaction only.

---

## V. Idempotency

**Mechanism:** The combination of `idempotency_key` and claimed `seat_id` acts as the idempotency lock.

**Behavior:**
- If a retry occurs with the same `idempotency_key` and `seat_id`:
  - Detect that the seat is already claimed (`user_id IS NOT NULL`).
  - Return the existing `user_id` and `seat_id` with outcome `"NEW_USER_CLAIMED"` (the claim already succeeded).
  - Do NOT create a duplicate `User` or re-bind the seat.
  - Do NOT emit duplicate audit events (same `idempotency_key` indicates a replay).

**Implications:**
- Client MUST provide a deterministic `idempotency_key` (e.g., derived from session ID or request fingerprint).
- Server MUST store the `idempotency_key` on the audit log to detect replays.

---

## VI. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies the FEAT (always "FEAT-IDEN-001") |
| `user_id` | Integer | ✓ | The newly provisioned user |
| `seat_id` | Integer | ✓ | The claimed seat |
| `class_id` | UUID | ✓ | The classroom context |
| `roster_seat_id` | Integer | ✓ | The original unclaimed seat (for traceability) |
| `idempotency_key` | String | ✓ | Replay detection; enables idempotency verification |
| `outcome` | Enum | ✓ | Must be: `NEW_USER_CLAIMED` (only valid outcome) |
| `join_code` | String | ✓ | The ingress code (for audit trail) |
| `first_name` | String | ✗ | DO NOT log (PII) |
| `last_name` | String | ✗ | DO NOT log (PII) |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of claim completion |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes (Only One Possible):**
- `NEW_USER_CLAIMED`: Successful claim of a new unclaimed seat for a new user.

**Explicitly Prohibited Outcomes:**
- ❌ `EXISTING_USER_LINKED`: Cannot occur; unauthenticated claim always creates new user.
- ❌ `USER_REUSED`: Cannot occur per DOM-IDEN-005.

---

## VII. Failure Scenarios

When the FEAT fails, the system SHALL:

1. **Rollback all mutations** atomically.
2. **Emit audit event** with outcome `FAILED` and error code.
3. **Return error response** to client with appropriate HTTP status.

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| Invalid join code | `INVALID_JOIN_CODE` | 400 | "Invalid join code or all seats already claimed. Check with your teacher." |
| No unclaimed seats in class | `NO_UNCLAIMED_SEATS` | 400 | "Invalid join code or all seats already claimed. Check with your teacher." |
| Name credentials don't match any seat | `INVALID_CREDENTIALS` | 400 | "No matching account found. Please check your join code and credentials." |
| Multiple name matches, dedupe required but not provided | `AMBIGUOUS_IDENTITY` | 400 | "Multiple students in this class share that name. Enter your deduplication code from your teacher." |
| Invalid dedupe code | `INVALID_DEDUPE_CODE` | 400 | "Invalid deduplication code. Check with your teacher." |
| Seat binding constraint violated | `DUPLICATE_SEAT_BINDING` | 409 | "This seat is already claimed. Contact your teacher." |
| Database transaction failure | `INTERNAL_ERROR` | 500 | "An error occurred during account claim. Please try again or contact support." |

---

## VIII. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md`
- `docs/DOMAIN/DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`
- `docs/DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md`

---

## IX. Implementation Checklist

Before code review, verify:

- [ ] No DOB or DOB-derived fields are accepted or used
- [ ] No existing user search or inference occurs
- [ ] Only outcome is `NEW_USER_CLAIMED`
- [ ] Idempotency_key is stored and used for replay detection
- [ ] Both `last_active_class_id` AND `last_active_seat_id` are set
- [ ] Claim lookup hashes are zeroed after binding
- [ ] ClassMembership initialization occurs (if applicable)
- [ ] Audit event is emitted with all required fields
- [ ] All mutations occur in a single transaction
- [ ] Rollback occurs on any failure
- [ ] No intermediate user states are observable
- [ ] Test covers idempotent retry case

---

## X. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-005 §VII and DOM-IDEN-002 §VIII.
4. Maintain consistency with FEAT-CORE-000.
5. Maintain consistency with INV-CORE-000.

**This is version 2.0 of FEAT-IDEN-001. Version 1.0 (2026-04-23) is superseded and withdrawn due to constitutional non-compliance.**
