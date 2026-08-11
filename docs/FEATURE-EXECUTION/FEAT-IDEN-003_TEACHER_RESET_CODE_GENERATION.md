# FEAT-IDEN-003: Teacher-Initiated Reset Code Generation
**[NEW - Compliant with DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-003 | 1.0 | 2026-08-09 | N/A (new) | Normative | NEW |

---

## I. Purpose

This FEAT is the first step of the student account recovery workflow. A teacher initiates recovery for a student who has lost access to their account, generating a short-lived reset code that the student will use to regain access.

Per DOM-IDEN-002 §IX (Student Account Recovery) Step 1:
> "A teacher with an active administrative seat in the student's class initiates a recovery reset for a claimed student seat... Generates a new 8-character random alphanumeric reset code; Sets `reset_code_generated_at = now`; Sets `reset_code_expires_at = reset_code_generated_at + 10 minutes`"

This FEAT implements Step 1 of the recovery flow.

**Governing Authority:**
- DOM-IDEN-002 §IX (Student Account Recovery)
- DOM-IDEN-005 §IX (Identity Recovery)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `seat_id`: The claimed student seat (identifying the account to recover).
* `teacher_user_id`: The authenticated teacher initiating the recovery (from request context).
* `idempotency_key`: Client-provided unique request ID.

### 2. Resolved Context (MANDATORY)

Before mutation, the FEAT MUST resolve:
* `student_seat`: The `Seat` record matching `seat_id`.
* `student_user`: The `User` record bound to `student_seat.user_id`.
* `class_id`: From `student_seat.class_id`.
* `teacher_authorization`: Verify the authenticated teacher has an administrative seat in the same class.

---

## III. Orchestration Logic

### A. Verification Phase (Read-Only)

#### Step 1: Validate Student Seat
1. Query `Seat` where `id = seat_id`.
2. Verify `Seat.claimed_at IS NOT NULL` (seat must be claimed).
3. Verify `Seat.user_id IS NOT NULL` (seat must be bound to a user).
4. Verify `Seat.role = 'student'` (seat must be a student seat, not admin).
5. Extract `user_id` and `class_id` from the seat.
6. **Failure Behavior**: Abort with `STUDENT_SEAT_NOT_FOUND` or `INVALID_SEAT_STATE`.

#### Step 2: Validate Student User
1. Query `User` where `id = student_user_id`.
2. Verify `User.user_role = 'student'`.
3. **Failure Behavior**: Abort with `STUDENT_USER_NOT_FOUND`.

#### Step 3: Validate Teacher Authorization
Per DOM-IDEN-005 §IX:
> "Recovery MAY... restore credentials... Recovery SHALL NOT... create Users... Recovery never reconstructs identity."

The teacher initiating recovery MUST have administrative authority in the class:
1. Query administrative `Seat` where:
   - `user_id = teacher_user_id`
   - `class_id = student_seat.class_id`
   - `role = 'admin'`
2. If no matching seat found: Abort with `UNAUTHORIZED` (403).
3. **Failure Behavior**: Return 403 Forbidden.

#### Step 4: Check Single Active Code Invariant
Per DOM-IDEN-002 §IX:
> "Single active code: Only one active reset code per student identity at any time."

1. Check if `student_user.reset_code` already exists.
2. If yes: Log that the existing code will be overwritten.
3. This is not a failure; new code overwrites old (per spec).

---

### B. Mutation Phase (Atomic Transaction)

#### Step 1: Generate Reset Code
1. Generate a random 8-character alphanumeric reset code.
   - Characters: A-Z, 0-9 (no lowercase, no special chars)
   - Example: "A7F2K9M1"
2. Verify the code is not trivially weak:
   - ❌ NOT all the same character (e.g., "AAAAAAAA")
   - ❌ NOT sequential (e.g., "ABCDEFGH")
3. **Single Active Code Invariant**: If a code already exists, it will be overwritten (no extra check needed).

#### Step 2: Write Reset Code to User
Update the `User` record:
1. Set `reset_code = generated_code` (overwrites any existing code).
2. Set `reset_code_generated_at = NOW()` (UTC).
3. Set `reset_code_expires_at = NOW() + 10 minutes`.

Per DOM-IDEN-002 §IX:
> "Reset codes are short-lived (10-minute TTL), teacher-visible, and communicated in person. Plaintext storage is acceptable for this handoff artifact."

**Note:** Reset codes are stored in plaintext because they are:
- Short-lived (10 min)
- Teacher-visible only
- Communicated verbally to student
- Not a permanent credential

#### Step 3: Emit Audit Trace

Per FEAT-CORE-000 §III.4:

1. Call `DOM-OPS` to emit `ACT-IDEN-003` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-003"
   - `user_id`: `student_user_id`
   - `seat_id`: `student_seat_id`
   - `class_id`: The class context
   - `initiator_user_id`: The teacher's user_id
   - `idempotency_key`: The provided key
   - `outcome`: `"RESET_CODE_GENERATED"` (only possible outcome)
   - `timestamp`: ISO 8601 UTC timestamp

**Security Note:** DO NOT log the reset code itself (even though it's not hashed). Log only that a code was generated.

---

## IV. Invariants & Constraints

### 1. Single Active Code (MANDATORY)
Per DOM-IDEN-002 §IX:
> "Only one active reset code per student identity at any time. New code generation will overwrite the existing code."

- If a code already exists, it is silently overwritten (no error).
- Only one valid code can be active per user.

### 2. 10-Minute TTL (MANDATORY)
Per DOM-IDEN-002 §IX:
> "Hard TTL: 10 minutes."

- `reset_code_expires_at = reset_code_generated_at + 10 minutes (exactly)`.
- No sliding window, no renewal on activity.
- Code is invalid after 10 minutes.

### 3. Teacher Initiation Only (MANDATORY)
Per DOM-IDEN-002 §IX:
> "Teacher-initiated. Students cannot self-initiate recovery. A teacher must generate the reset code."

- Only teachers with administrative seat in the class can initiate.
- Students cannot request code generation directly.
- No self-service recovery code path.

### 4. No Credential Modification (MANDATORY)
Per DOM-IDEN-005 §IX:
> "Recovery restores authentication capability without altering participation..."

This FEAT:
- ✓ Sets reset code (for authorization)
- ❌ Does NOT modify username, PIN, or passphrase (done in FEAT-IDEN-004/FEAT-IDEN-002)
- ❌ Does NOT modify seat bindings
- ❌ Does NOT modify economic records

### 5. Idempotency (MANDATORY)
- Idempotency key + student_user_id ensures replay safety.
- Retrying the same teacher recovery for the same student returns success.
- Audit log uses key to detect duplicate events.

---

## V. Failure Scenarios

When the FEAT fails, the system SHALL:

1. **Rollback all mutations** (if any).
2. **Emit audit event** with outcome `FAILED` and error code.
3. **Return error response** to teacher.
4. **NOT display the reset code** (if code generation failed).

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Teacher Message |
|----------|-----------|-------------|-----------------|
| Student seat not found | `STUDENT_SEAT_NOT_FOUND` | 404 | "Student seat not found. Check the student ID." |
| Seat not claimed | `INVALID_SEAT_STATE` | 409 | "This student has not completed account setup yet." |
| Seat not bound to user | `INVALID_SEAT_STATE` | 409 | "Student seat has no linked user account." |
| Student user not found | `STUDENT_USER_NOT_FOUND` | 404 | "Student account not found." |
| Teacher not in class | `UNAUTHORIZED` | 403 | "You do not have permission to recover accounts in this class." |
| Database error | `INTERNAL_ERROR` | 500 | "An error occurred. Please try again." |

---

## VI. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies FEAT (always "FEAT-IDEN-003") |
| `user_id` | Integer | ✓ | The student user (not the teacher) |
| `seat_id` | Integer | ✓ | The student seat |
| `class_id` | UUID | ✓ | The classroom context |
| `initiator_user_id` | Integer | ✓ | The teacher who initiated recovery |
| `idempotency_key` | String | ✓ | Replay detection |
| `outcome` | Enum | ✓ | Must be: `RESET_CODE_GENERATED` |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of code generation |
| `reset_code` | String | ✗ | DO NOT log (security) |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes (Only One Possible):**
- `RESET_CODE_GENERATED`: Reset code successfully created.

---

## VII. Integration with Recovery Flow

**FEAT-IDEN-003 is Step 1 of the student recovery workflow:**

```
Step 1: FEAT-IDEN-003 (Teacher Initiates)
├─ Teacher action: Select student, request recovery
├─ System: Generate reset code, write to user.reset_code
├─ Expiry: NOW() + 10 minutes
└─ Output: Display code to teacher (e.g., "A7F2K9M1")

Step 2: FEAT-IDEN-004 (Student Validates Code)
├─ Student action: Receive code from teacher, enter it
├─ System: Validate code, clear old credentials
└─ Output: Redirect to credential setup

Step 3: FEAT-IDEN-002 (Credential Setup - reused)
├─ Student action: Enter new username, PIN, passphrase
├─ System: Activate credentials
└─ Output: Student can log in with new credentials
```

---

## VIII. Rate Limiting

Per DOM-IDEN-002 §IX:
> "Rate-limit reset code generation and submission."

Recommended limits:
- **Per teacher per student**: Max 5 code generations per hour
- **Per teacher per class**: Max 20 code generations per hour
- **Global**: Max 100 code generations per hour

Exceeding limits returns 429 Too Many Requests.

---

## IX. Teacher UX Considerations

After code generation, the system displays the code to the teacher with:

1. **Clear prominence** (large, readable font)
2. **Expiry warning** ("Expires in 10 minutes")
3. **Action prompt** ("Give this code to the student verbally")
4. **Re-display option** (teacher can view code again until it expires or is used)
5. **Confirmation** (success message with timestamp)

Example message:
> "Reset code generated for [Student Name]: **A7F2K9M1** — Expires in 10 minutes. Give this code to the student."

---

## X. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`
- `docs/DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md`

---

## XI. Implementation Checklist

Before code review, verify:

- [ ] Teacher authorization is checked (admin seat in same class)
- [ ] Student seat is claimed and bound to a user
- [ ] Reset code is 8 characters, alphanumeric only
- [ ] Code is not trivially weak (all same char, sequential)
- [ ] Expiry is exactly 10 minutes (not sliding, not renewable)
- [ ] Old code is overwritten (single active code invariant)
- [ ] Audit event is emitted with all required fields
- [ ] Reset code is NOT logged in audit
- [ ] Idempotency check prevents duplicate audit events
- [ ] Rate limiting is enforced
- [ ] Error messages don't reveal whether user exists
- [ ] Tests cover success, authorization failure, and replay scenarios

---

## XII. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-002 §IX.
4. Maintain consistency with FEAT-CORE-000.
5. Maintain consistency with FEAT-IDEN-004.

**This is version 1.0 of FEAT-IDEN-003 (new specification, 2026-08-09).**
