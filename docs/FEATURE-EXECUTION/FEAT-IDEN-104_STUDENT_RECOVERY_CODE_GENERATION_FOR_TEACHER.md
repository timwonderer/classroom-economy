# FEAT-IDEN-104: Student Recovery Code Generation for Teacher
**[NEW - Compliant with DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-104 | 1.0 | 2026-08-09 | N/A (new) | Normative | NEW |

---

## I. Purpose

This FEAT allows a student to generate a recovery code that helps verify their teacher's identity during account recovery. Per DOM-IDEN-003 §IV:
> "Teachers can recover their accounts by having all students verify identity through the class roster. Each student generates a unique recovery code that proves their affiliation with the class."

This FEAT creates a `student_recovery_code` record linked to an active `recovery_request`, allowing the student to participate in teacher identity verification.

**Governing Authority:**
- DOM-IDEN-003 §IV (Teacher Recovery - Student-Verified Mechanism)
- DOM-IDEN-002 §VIII.IV (Student Identity and Claim Flow — students are known by roster)
- DOM-IDEN-005 §VIII (Identity Binding)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `recovery_request_id`: The active recovery request from FEAT-IDEN-103.
* `student_user_id`: The student `User` generating the code (authenticated session).
* `seat_id`: The student `Seat` in the class (from context).
* `class_id`: The class context (from session or context).
* `idempotency_key`: Client-provided unique request ID for retry safety.

### 2. Resolved Context (MANDATORY)

Before mutation, the FEAT MUST resolve:
* The `RecoveryRequest` record matching `recovery_request_id`.
* The `User` record matching `student_user_id`.
* The `Seat` record matching `seat_id`.
* Verify that `User.id == Seat.user_id` (seat is bound to this user).
* Verify that `Seat.role = 'student'` and `Seat.claimed_at IS NOT NULL` (student is claimed).
* Verify that `Seat.class_id == class_id` (seat is in the correct class).
* Verify that `RecoveryRequest.class_id == class_id` (recovery is for the same class).

---

## III. Orchestration Logic

### A. Verification Phase (Read-Only)

#### Step 1: Validate Recovery Request State
1. Query `recovery_requests` where `id = recovery_request_id`.
2. Verify that `status IN ('pending', 'in_progress')` (recovery is active).
3. Verify that `expires_at > NOW()` (recovery request not expired).
4. **Failure Behavior**: Abort with `RECOVERY_NOT_ACTIVE` if recovery is closed or expired.

#### Step 2: Validate Student User State
1. Query `User` record where `id = student_user_id`.
2. Verify that `user_role = 'student'`.
3. Verify that `pin_hash IS NOT NULL` (student credentials are activated).
4. **Failure Behavior**: Abort with `INVALID_USER_ROLE` if user is not a student or not credentialed.

#### Step 3: Validate Student Seat State
1. Query `Seat` record where `id = seat_id`.
2. Verify that `user_id = student_user_id` (seat is bound to this student).
3. Verify that `role = 'student'` and `claimed_at IS NOT NULL` (seat is claimed).
4. Verify that `class_id = class_id` (seat is in the correct class).
5. **Failure Behavior**: Abort with `INVALID_SEAT_STATE` if seat is not a claimed student seat.

#### Step 4: Check Existing Recovery Code
1. Query `student_recovery_codes` where `recovery_request_id = recovery_request_id` and `seat_id = seat_id`.
2. If a code already exists for this recovery request and student, return `CODE_ALREADY_GENERATED` (idempotent success).
3. **Failure Behavior**: Do not allow duplicate codes from the same student for the same recovery request.

#### Step 5: Verify Class Affiliation
1. Verify that `RecoveryRequest.class_id == Seat.class_id` (student is in the same class as recovery request).
2. **Failure Behavior**: Abort with `CLASS_MISMATCH` if student is not in the recovery class.

---

### B. Mutation Phase (Atomic Transaction)

All mutations in this section **MUST** occur within a single database transaction.

#### Step 1: Generate Recovery Code

Perform code generation outside the transaction:
1. `recovery_code = GENERATE_CODE()` (generate random alphanumeric code, e.g., 12-16 characters).
   - Format: Uppercase alphanumeric (no confusing characters like O, I, 1, 0).
   - Length: 12-16 characters (balances security and usability).
2. `code_hash = HASH_PASSWORD(recovery_code)` (bcrypt with salt + pepper, same as student credentials).

**Note:** The unencrypted code is displayed to the student ONLY ONCE. Only the hash is stored.

#### Step 2: Create StudentRecoveryCode Record

Insert into `student_recovery_codes` table:
1. `recovery_request_id`: The active recovery request.
2. `seat_id`: The student's seat.
3. `class_id`: The class context (denormalized for scoping).
4. `code_hash`: The hashed recovery code (bcrypt).
5. `generated_at`: ISO 8601 UTC timestamp.
6. `used_at`: NULL (not yet used in FEAT-IDEN-105).

Per DOM-IDEN-003 §IV:
> "`student_recovery_codes` table stores one recovery code per student per recovery request."

#### Step 3: Update RecoveryRequest Status (Optional)

If no recovery codes existed and this is the first:
1. Optionally update `recovery_requests.status` from "pending" to "in_progress".
2. This signals that student code generation has begun.
3. **Note:** This is optional; status can remain "pending" until all codes are received.

#### Step 4: Audit Trace

Per FEAT-CORE-000 §III.4:

1. Call `DOM-OPS` to emit an `ACT-IDEN-104` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-104"
   - `user_id`: The student `user_id`
   - `seat_id`: The student `seat_id`
   - `class_id`: The classroom context
   - `recovery_request_id`: The recovery request ID
   - `idempotency_key`: The provided key
   - `outcome`: `"CODE_GENERATED"` (only possible outcome)
   - `timestamp`: ISO 8601 UTC timestamp

**Note:** DO NOT log the unencrypted recovery code.

---

## IV. Invariants & Constraints

### 1. Student-Verified Recovery (MANDATORY)
Per DOM-IDEN-003 §IV:
> "Each student in the class must provide a recovery code to verify the teacher's identity."

This FEAT creates one code per student per recovery request.

### 2. Active Recovery Required (MANDATORY)
Code generation only proceeds if an active recovery request exists in the class (`status IN ('pending', 'in_progress')` and `expires_at > NOW()`).

### 3. One Code Per Student Per Recovery (MANDATORY)
A single student cannot generate multiple codes for the same recovery request. If re-attempted with the same idempotency key, return existing code (idempotent).

### 4. One-Time Display (MANDATORY)
The unencrypted recovery code is displayed to the student ONLY ONCE. After display, only the hash is stored and retrieval is impossible.

### 5. Atomic Transaction (MANDATORY)
All mutations SHALL occur in a single transaction. If any step fails, complete rollback occurs.

### 6. Expiration Tied to RecoveryRequest (MANDATORY)
Recovery codes inherit expiration from their parent recovery request. When the recovery request expires, all associated codes are discarded.

---

## V. Idempotency

**Mechanism:** The combination of `idempotency_key` and `seat_id` acts as the idempotency lock.

**Behavior:**
- If a retry occurs with the same `idempotency_key`:
  - Check if `student_recovery_codes` row exists for `recovery_request_id` and `seat_id`.
  - If true, return success with outcome `CODE_ALREADY_GENERATED` (no duplicate state).
  - If false, re-attempt the full mutation.
- Replayed requests with the same `idempotency_key` **SHALL NOT** create duplicate recovery codes.

**Client Responsibility:**
- Generate a stable `idempotency_key` (e.g., based on session or student context).
- Retry on transient errors with the same key.
- Server stores key on audit log to detect and skip replays.

---

## VI. Failure Scenarios

When the FEAT fails, the system SHALL:

1. **Rollback all mutations** atomically.
2. **Emit audit event** with outcome `FAILED` and error code.
3. **Return error response** to client.
4. **NOT store incomplete recovery code**.

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| Recovery not active | `RECOVERY_NOT_ACTIVE` | 409 | "Recovery is not active. Please contact your teacher." |
| Recovery expired | `RECOVERY_EXPIRED` | 410 | "Recovery request has expired. Ask your teacher to start over." |
| User not a student | `INVALID_USER_ROLE` | 403 | "Only students can generate recovery codes." |
| Student not credentialed | `STUDENT_NOT_CREDENTIALED` | 409 | "Student account is not fully set up. Please complete setup first." |
| Invalid seat | `INVALID_SEAT_STATE` | 409 | "Invalid student seat. Please start over." |
| Class mismatch | `CLASS_MISMATCH` | 400 | "You are not in the same class as the recovery request." |
| Code already generated | `CODE_ALREADY_GENERATED` | 200 | "You have already generated a code for this recovery. Use the code provided earlier." |
| Database error | `INTERNAL_ERROR` | 500 | "An error occurred. Please try again." |

---

## VII. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies the FEAT (always "FEAT-IDEN-104") |
| `user_id` | Integer | ✓ | The student user generating the code |
| `seat_id` | Integer | ✓ | The student seat |
| `class_id` | UUID | ✓ | The classroom context |
| `recovery_request_id` | Integer | ✓ | The recovery request being assisted |
| `idempotency_key` | String | ✓ | Replay detection |
| `outcome` | Enum | ✓ | Must be: `CODE_GENERATED` or `CODE_ALREADY_GENERATED` |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of code generation |
| `recovery_code` | String | ✗ | DO NOT log (security) |
| `code_hash` | String | ✗ | DO NOT log (security) |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes:**
- `CODE_GENERATED`: Successful recovery code generation.
- `CODE_ALREADY_GENERATED`: Idempotent return; code already exists for this student.

---

## VIII. Display Requirements

After successful code generation, the route handler SHALL display to the student:

1. **Recovery Code Display**: Single-use code in large, readable format.
   - Format: Uppercase alphanumeric, possibly grouped (XXXX-XXXX-XXXX).
   - Display once, with instructions to write it down or take a screenshot.
   - Provide "Copy to Clipboard" button.

2. **Teacher Instructions**: Explain how the teacher will use this code.
   - "Give this code to your teacher. They will use it to restore their account."

3. **Expiration Notice**: Display when the code expires.
   - "This code expires in X days" (matching recovery request TTL).

4. **Confirmation**: Confirm student has saved the code.
   - Button: "I've saved my code" (allows progression).

---

## IX. Integration with FEAT-IDEN-103 & FEAT-IDEN-105

**Teacher recovery involves three coordinated FEATs:**

```
FEAT-IDEN-103: Teacher Initiates Recovery
└─ Creates recovery_request (status: pending)

FEAT-IDEN-104: Students Generate Recovery Codes
└─ Creates one student_recovery_code per student
└─ Each code is hash-stored, displayed once to student

FEAT-IDEN-105: Teacher Validates Recovery & Restores Access
├─ Teacher submits all recovery codes they collected
├─ System verifies all codes are present and valid
└─ Marks recovery as verified, resets TOTP credentials
```

All three FEATs operate on the same `recovery_requests` record and its related `student_recovery_codes`.

---

## X. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-103_TEACHER_RECOVERY_INITIATION.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md`
- `docs/DOMAIN/DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`

---

## XI. Implementation Checklist

Before code review, verify:

- [ ] Recovery request validation (active and not expired)
- [ ] Student user validation (correct role and credentialed)
- [ ] Student seat validation (claimed and in correct class)
- [ ] Class affiliation verification (student is in recovery class)
- [ ] Existing code check (idempotent on already-generated)
- [ ] Code generation produces correct format (12-16 alphanumeric)
- [ ] Code is hashed with bcrypt + pepper (same as student credentials)
- [ ] StudentRecoveryCode record created with all required fields
- [ ] All mutations occur in a single transaction
- [ ] Audit event emitted with all required fields
- [ ] Rollback occurs on any failure
- [ ] Recovery code is NOT logged (only hash)
- [ ] Idempotency check prevents duplicate codes
- [ ] Expiration tied to recovery request TTL
- [ ] Tests cover successful code generation and idempotent retry
- [ ] Tests cover expired recovery request scenario

---

## XII. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-003 §IV.
4. Maintain consistency with FEAT-CORE-000.
5. Maintain consistency with FEAT-IDEN-103 and FEAT-IDEN-105.

**This is version 1.0 of FEAT-IDEN-104 (new specification, 2026-08-09).**
