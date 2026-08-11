# FEAT-IDEN-103: Teacher Recovery Initiation
**[NEW - Compliant with DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-103 | 1.0 | 2026-08-09 | N/A (new) | Normative | NEW |

---

## I. Purpose

This FEAT initiates a recovery request for a teacher who has lost access to their account (e.g., lost TOTP authenticator, forgotten passkey). Per DOM-IDEN-003 §IV:
> "Teachers can initiate account recovery by requesting verification from their students. Recovery requests are 5-day TTL and require all students in the class to provide recovery codes."

This FEAT creates a `recovery_request` record with status `pending`, allowing students to assist in teacher identity verification via FEAT-IDEN-104.

**Governing Authority:**
- DOM-IDEN-003 §IV (Teacher Recovery - Student-Verified Mechanism)
- DOM-IDEN-005 §VIII (Identity Binding)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `user_id`: The teacher `User` requesting recovery (from session or context, unauthenticated request).
* `class_id`: The class context (from session or context).
* `idempotency_key`: Client-provided unique request ID for retry safety.

### 2. Resolved Context (MANDATORY)

Before mutation, the FEAT MUST resolve:
* The `User` record matching `user_id` in the `users` table.
* The `ClassEconomy` record matching `class_id`.
* Verify that `User.user_role = 'teacher'` (requestor is a teacher).

---

## III. Orchestration Logic

### A. Verification Phase (Read-Only)

#### Step 1: Validate Teacher User State
1. Query `User` record where `id = user_id`.
2. Verify that `user_role = 'teacher'`.
3. Verify that `totp_secret_encrypted IS NOT NULL` (TOTP was enrolled).
   - Recovery only makes sense if TOTP was enrolled (otherwise account is already accessible).
4. **Failure Behavior**: Abort with `INVALID_USER_ROLE` if user is not a teacher.

#### Step 2: Check Existing Recovery Requests
1. Query `recovery_requests` where `user_id = user_id` and `status = 'pending'` and `expires_at > NOW()`.
2. If an active recovery request exists, return `RECOVERY_IN_PROGRESS` (idempotent success).
3. If multiple pending requests exist, this indicates a data integrity issue — abort with `DATA_INTEGRITY_ERROR`.

#### Step 3: Validate Class Context
1. Query `ClassEconomy` record where `class_id = class_id`.
2. Verify `class_id` exists and is active.
3. **Failure Behavior**: Abort with `INVALID_CLASS_CONTEXT` if class does not exist.

#### Step 4: Verify Teacher Affiliation
1. Query `Seat` where `user_id = user_id` and `class_id = class_id` and `role = 'teacher'`.
2. Verify at least one teacher seat exists for this teacher in the class.
3. **Failure Behavior**: Abort with `NO_TEACHER_SEAT` if teacher has no teacher seat in this class.

#### Step 5: Check Student Population
1. Query `Seat` where `class_id = class_id` and `role = 'student'` and `claimed_at IS NOT NULL`.
2. Get count of claimed student seats.
3. If count == 0, return warning: "No students in class. Recovery cannot proceed without student verification."
   - Recovery still succeeds, but notification should indicate students are needed.

---

### B. Mutation Phase (Atomic Transaction)

All mutations in this section **MUST** occur within a single database transaction.

#### Step 1: Calculate Recovery Window

Perform time calculation outside the transaction:
1. `expires_at = NOW() + 5 DAYS` (per DOM-IDEN-003: 5-day TTL for teacher recovery).
2. `status = 'pending'` (recovery request created but not yet in progress).

#### Step 2: Create RecoveryRequest Record

Insert into `recovery_requests` table:
1. `user_id`: The teacher user.
2. `class_id`: The class context (for scoping).
3. `status`: "pending" (awaiting student code generation).
4. `expires_at`: Calculated 5-day expiration (NOW() + 5 DAYS).
5. `created_at`: ISO 8601 UTC timestamp (set by database default).

Per DOM-IDEN-003 §IV:
> "`recovery_requests` table stores teacher recovery requests with 5-day TTL."

#### Step 3: Audit Trace

Per FEAT-CORE-000 §III.4:

1. Call `DOM-OPS` to emit an `ACT-IDEN-103` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-103"
   - `user_id`: The teacher `user_id`
   - `class_id`: The classroom context
   - `recovery_request_id`: The created `recovery_requests.id`
   - `idempotency_key`: The provided key
   - `outcome`: `"RECOVERY_INITIATED"` (only possible outcome for new request)
   - `expires_at`: The 5-day expiration timestamp
   - `timestamp`: ISO 8601 UTC timestamp

**Note:** DO NOT log any credentials or authentication details.

---

## IV. Invariants & Constraints

### 1. Student-Verified Recovery (MANDATORY)
Per DOM-IDEN-003 §IV:
> "Teacher recovery requires verification from students. All students must provide recovery codes."

This FEAT creates the recovery request; students provide verification through FEAT-IDEN-104.

### 2. 5-Day TTL (MANDATORY)
Recovery requests expire after 5 days. After expiration, the recovery request is discarded and must be re-initiated.

### 3. Single Active Recovery Request (MANDATORY)
A teacher may have only ONE active (`pending` or `in_progress`) recovery request at a time. Initiating recovery while one is already in progress returns idempotent success (no duplicate).

### 4. TOTP-Only Recovery (MANDATORY)
Recovery makes sense only if TOTP was already enrolled. If TOTP is not enrolled, the account is already accessible via alternate means.

### 5. Atomic Transaction (MANDATORY)
All mutations SHALL occur in a single transaction. If any step fails, complete rollback occurs.

### 6. Class-Scoped Recovery (MANDATORY)
Recovery is scoped to a single class. A teacher with multiple classes must initiate separate recovery requests per class.

---

## V. Idempotency

**Mechanism:** The combination of `idempotency_key` and `user_id` acts as the idempotency lock.

**Behavior:**
- If a retry occurs with the same `idempotency_key`:
  - Check if `recovery_requests` row exists for `user_id` with `status IN ('pending', 'in_progress')`.
  - If true, return success with outcome `RECOVERY_IN_PROGRESS` (no duplicate state).
  - If false, re-attempt the full mutation.
- Replayed requests with the same `idempotency_key` **SHALL NOT** create duplicate recovery requests.

**Client Responsibility:**
- Generate a stable `idempotency_key` (e.g., based on session or user context).
- Retry on transient errors with the same key.
- Server stores key on audit log to detect and skip replays.

---

## VI. Failure Scenarios

When the FEAT fails, the system SHALL:

1. **Rollback all mutations** atomically.
2. **Emit audit event** with outcome `FAILED` and error code.
3. **Return error response** to client.
4. **NOT create a recovery request**.

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| User not a teacher | `INVALID_USER_ROLE` | 403 | "Only teachers can initiate recovery." |
| TOTP not enrolled | `TOTP_NOT_ENROLLED` | 409 | "Recovery is only available if TOTP is enrolled." |
| No admin seat | `NO_ADMIN_SEAT` | 409 | "You don't have an admin seat in this class." |
| Recovery already in progress | `RECOVERY_IN_PROGRESS` | 200 | "Recovery is already in progress for this account." |
| Invalid class | `INVALID_CLASS_CONTEXT` | 400 | "Invalid class context." |
| No students | `NO_STUDENTS_WARNING` | 201 | "Recovery initiated, but there are no students in class to provide codes." |
| Database error | `INTERNAL_ERROR` | 500 | "An error occurred during recovery initiation. Please try again." |

---

## VII. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies the FEAT (always "FEAT-IDEN-103") |
| `user_id` | Integer | ✓ | The teacher user requesting recovery |
| `class_id` | UUID | ✓ | The classroom context |
| `recovery_request_id` | Integer | ✓ | The created recovery request |
| `idempotency_key` | String | ✓ | Replay detection |
| `outcome` | Enum | ✓ | Must be: `RECOVERY_INITIATED` or `RECOVERY_IN_PROGRESS` |
| `expires_at` | ISO 8601 | ✓ | The 5-day expiration timestamp |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of initiation |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes:**
- `RECOVERY_INITIATED`: Successful recovery request creation.
- `RECOVERY_IN_PROGRESS`: Idempotent return; recovery is already underway.

---

## VIII. Display Requirements

After successful recovery initiation, the route handler SHALL display to the teacher:

1. **Recovery Code Entry Form**: Instructions for students to provide recovery codes.
   - Display unique recovery request ID (for students to reference).
   - Display expiration timestamp.
   - Link/QR code to student-facing form for code generation (FEAT-IDEN-104).

2. **Countdown Timer**: Display remaining time until recovery request expires.
   - Refresh every 60 seconds or real-time if using WebSocket.
   - Show warning if < 1 hour remaining.

3. **Student Status**: Display number of students who have provided codes (updated as students participate).
   - Show "Awaiting codes from X students" or similar.
   - Refresh on completion.

4. **Next Steps**: Instructions for what happens after all students provide codes.
   - "Once all students provide codes, your account will be restored."

---

## IX. Integration with FEAT-IDEN-104 & FEAT-IDEN-105

**Teacher recovery involves three coordinated FEATs:**

```
FEAT-IDEN-103: Teacher Initiates Recovery
├─ Teacher creates recovery_request
└─ Status: pending (awaiting student codes)

FEAT-IDEN-104: Students Generate Recovery Codes
├─ Students verify teacher identity through class roster
└─ Create student_recovery_code records (one per student)

FEAT-IDEN-105: Teacher Validates Recovery & Restores Access
├─ Check that all students provided codes
├─ Verify codes are correct
└─ Update recovery_request.status to verified
└─ Reset TOTP secret (allow FEAT-IDEN-101 or FEAT-IDEN-106)
```

All three FEATs operate on the same `recovery_requests` record.

---

## X. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-104_STUDENT_RECOVERY_CODE_GENERATION_FOR_TEACHER.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md`
- `docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`
- `docs/DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md`

---

## XI. Implementation Checklist

Before code review, verify:

- [ ] User role validation ensures only teachers can initiate recovery
- [ ] TOTP enrollment verification (recovery assumes TOTP exists)
- [ ] Class context validation (verify class exists)
- [ ] Teacher affiliation verification (verify teacher has admin seat in class)
- [ ] Student population check (warn if no students)
- [ ] Existing recovery request check (idempotent on active request)
- [ ] Expiration calculation is correct (NOW() + 5 DAYS)
- [ ] RecoveryRequest status is set to "pending"
- [ ] All mutations occur in a single transaction
- [ ] Audit event emitted with all required fields
- [ ] Rollback occurs on any failure
- [ ] Credentials are NOT logged in audit
- [ ] Idempotency check prevents duplicate recovery requests
- [ ] Tests cover successful initiation and idempotent retry
- [ ] Tests cover no-students warning scenario

---

## XII. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-003 §IV.
4. Maintain consistency with FEAT-CORE-000.
5. Maintain consistency with FEAT-IDEN-104 and FEAT-IDEN-105.

**This is version 1.0 of FEAT-IDEN-103 (new specification, 2026-08-09).**
