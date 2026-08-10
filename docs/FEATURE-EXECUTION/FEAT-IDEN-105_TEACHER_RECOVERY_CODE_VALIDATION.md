# FEAT-IDEN-105: Teacher Recovery Code Validation
**[NEW - Compliant with DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-105 | 1.0 | 2026-08-09 | N/A (new) | Normative | NEW |

---

## I. Purpose

This FEAT validates all recovery codes provided by students and restores teacher account access upon successful verification. Per DOM-IDEN-003 §IV:
> "Teachers recover accounts by submitting all recovery codes provided by students. Once all codes are verified, the recovery request is marked verified and the teacher can reset credentials."

This FEAT performs all-or-nothing validation: all recovery codes must be present and correct, or the entire recovery fails.

**Governing Authority:**
- DOM-IDEN-003 §IV (Teacher Recovery - All-or-Nothing Student Code Validation)
- DOM-IDEN-005 §VIII (Identity Binding)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `recovery_request_id`: The active recovery request from FEAT-IDEN-103.
* `user_id`: The teacher `User` recovering account (from context or recovery request).
* `class_id`: The class context (from session or context).
* `submitted_codes`: Array of recovery codes provided by the teacher (from form/input).
  - Format: Array of strings, each code as typed/provided by student.
* `idempotency_key`: Client-provided unique request ID for retry safety.

### 2. Resolved Context (MANDATORY)

Before mutation, the FEAT MUST resolve:
* The `RecoveryRequest` record matching `recovery_request_id`.
* The `User` record matching `user_id`.
* Verify that `User.id == RecoveryRequest.user_id` (recovery is for this teacher).
* Verify that `RecoveryRequest.class_id == class_id` (recovery is for this class).

---

## III. Orchestration Logic

### A. Verification Phase (Read-Only)

#### Step 1: Validate Recovery Request State
1. Query `recovery_requests` where `id = recovery_request_id`.
2. Verify that `status IN ('pending', 'in_progress')` (recovery is active).
3. Verify that `expires_at > NOW()` (recovery request not expired).
4. Verify that `user_id = user_id` (recovery belongs to this teacher).
5. **Failure Behavior**: Abort with `RECOVERY_NOT_ACTIVE` if recovery is closed or expired.

#### Step 2: Fetch Expected Recovery Codes
1. Query all `student_recovery_codes` where `recovery_request_id = recovery_request_id`.
2. Get count of expected codes (one per claimed student in class).
3. Build a mapping of `seat_id -> code_hash` for verification.

#### Step 3: Validate Code Count
1. If `submitted_codes` array length != expected code count, abort with `INCOMPLETE_SUBMISSION`.
   - This is all-or-nothing: every student's code is required.
2. **Failure Behavior**: Return count of codes provided vs. expected (generic, no PII leaks).

#### Step 4: Verify Each Code
1. For each code in `submitted_codes`:
   - Hash the submitted code with `HASH_PASSWORD()` (same bcrypt + pepper).
   - Check if the hash matches any `student_recovery_codes.code_hash`.
   - Mark the code as verified.
2. If any code does not match, abort with `INVALID_CODE`.
   - **Security:** Use generic error message (do not disclose which code is wrong).
3. **Failure Behavior**: Return generic error without revealing which codes are correct/incorrect.

#### Step 5: Verify All Codes Accounted For
1. Ensure that ALL `student_recovery_codes` for this recovery request have been verified.
2. If any codes are missing, return `INCOMPLETE_SUBMISSION`.

#### Step 6: Check Expiration on Each Code
1. Verify that no code has expired (tied to recovery_request expiration).
2. **Failure Behavior**: Abort with `CODES_EXPIRED` if recovery request is past TTL.

---

### B. Mutation Phase (Atomic Transaction)

All mutations in this section **MUST** occur within a single database transaction.

#### Step 1: Mark Codes as Used

Update all verified `student_recovery_codes`:
1. Set `used_at = NOW()` (mark as consumed).
2. Verify that each code is marked used exactly once (no re-use).

#### Step 2: Update Recovery Request Status

Update the `recovery_requests` record:
1. Set `status = 'verified'` (recovery codes validated successfully).
2. Set `updated_at = NOW()`.

Per DOM-IDEN-003 §IV:
> "`recovery_requests` status transitions: pending → in_progress → verified"

#### Step 3: Audit Trace

Per FEAT-CORE-000 §III.4:

1. Call `DOM-OPS` to emit an `ACT-IDEN-105` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-105"
   - `user_id`: The teacher `user_id`
   - `class_id`: The classroom context
   - `recovery_request_id`: The recovery request ID
   - `idempotency_key`: The provided key
   - `code_count`: Number of codes verified
   - `outcome`: `"RECOVERY_VERIFIED"` (only possible outcome)
   - `timestamp`: ISO 8601 UTC timestamp

**Note:** DO NOT log any recovery codes or validation details.

#### Step 4: Trigger TOTP Reset Capability (Optional)

After successful verification:
1. Internally mark that this teacher can now reset TOTP via FEAT-IDEN-106.
2. Can be accomplished by:
   - Storing a temporary flag in the recovery request record, OR
   - Returning authorization token to the client (expires in 1 hour), OR
   - Directly invoking FEAT-IDEN-106 with recovery context.

**Note:** The actual TOTP reset happens in FEAT-IDEN-106 (separate FEAT).

---

## IV. Invariants & Constraints

### 1. All-or-Nothing Validation (MANDATORY)
Per DOM-IDEN-003 §IV:
> "ALL recovery codes must be provided and valid. A single missing or incorrect code fails the entire recovery."

This is not a majority-vote or threshold mechanism — all codes are required.

### 2. Active Recovery Required (MANDATORY)
Validation only proceeds if an active recovery request exists (`status IN ('pending', 'in_progress')` and `expires_at > NOW()`).

### 3. Expiration Tied to RecoveryRequest (MANDATORY)
If the recovery request expires, all associated codes expire. Validation fails if codes are expired.

### 4. One-Time Use (MANDATORY)
Each recovery code can be used only once. After successful validation, `student_recovery_codes.used_at` is set to prevent re-use.

### 5. Atomic Transaction (MANDATORY)
All mutations SHALL occur in a single transaction. If any step fails, complete rollback occurs.

### 6. Generic Error Messages (MANDATORY)
Do not disclose:
- Which specific code is invalid
- How many codes are expected vs. provided (beyond count)
- Student identities or seat information

---

## V. Idempotency

**Mechanism:** The combination of `idempotency_key` and `recovery_request_id` acts as the idempotency lock.

**Behavior:**
- If a retry occurs with the same `idempotency_key`:
  - Check if `recovery_requests.status = 'verified'` (codes already validated).
  - If true, return success with outcome `ALREADY_VERIFIED` (no duplicate state).
  - If false, re-attempt the full validation.
- Replayed requests with the same `idempotency_key` **SHALL NOT** double-consume recovery codes.

**Client Responsibility:**
- Generate a stable `idempotency_key` (e.g., based on session).
- Retry on transient errors with the same key.
- Server stores key on audit log to detect and skip replays.

---

## VI. Failure Scenarios

When the FEAT fails, the system SHALL:

1. **Rollback all mutations** atomically.
2. **Emit audit event** with outcome `FAILED` and error code.
3. **Return error response** to client (generic message).
4. **NOT mark recovery as verified**.
5. **NOT consume recovery codes** (remain available for retry).

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| Recovery not active | `RECOVERY_NOT_ACTIVE` | 409 | "Recovery is not active. Please contact support." |
| Recovery expired | `RECOVERY_EXPIRED` | 410 | "Recovery request has expired. Please start a new recovery request." |
| Incomplete submission | `INCOMPLETE_SUBMISSION` | 400 | "You must provide all recovery codes. Check that you have one code per student." |
| Invalid code | `INVALID_CODE` | 400 | "One or more recovery codes are invalid. Please check and try again." |
| Codes expired | `CODES_EXPIRED` | 410 | "Recovery codes have expired. Please start a new recovery request." |
| Database error | `INTERNAL_ERROR` | 500 | "An error occurred. Please try again." |

---

## VII. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies the FEAT (always "FEAT-IDEN-105") |
| `user_id` | Integer | ✓ | The teacher user |
| `class_id` | UUID | ✓ | The classroom context |
| `recovery_request_id` | Integer | ✓ | The recovery request being validated |
| `idempotency_key` | String | ✓ | Replay detection |
| `code_count` | Integer | ✓ | Number of codes verified |
| `outcome` | Enum | ✓ | Must be: `RECOVERY_VERIFIED` or `ALREADY_VERIFIED` |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of validation |
| `submitted_codes` | Array | ✗ | DO NOT log (security) |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes:**
- `RECOVERY_VERIFIED`: Successful validation of all recovery codes.
- `ALREADY_VERIFIED`: Idempotent return; recovery already verified.

---

## VIII. Display Requirements

After successful code validation, the route handler SHALL display to the teacher:

1. **Success Confirmation**: "Your identity has been verified!"
2. **Next Steps**: "You can now reset your TOTP authentication."
3. **Action Button**: "Reset TOTP" or "Set Up New Authentication"
   - Links to FEAT-IDEN-106 (Update TOTP Secret) or FEAT-IDEN-101 (fresh TOTP setup).

---

## IX. Integration with FEAT-IDEN-103, FEAT-IDEN-104, FEAT-IDEN-106

**Teacher recovery involves multiple coordinated FEATs:**

```
FEAT-IDEN-103: Teacher Initiates Recovery
└─ Creates recovery_request (status: pending)

FEAT-IDEN-104: Students Generate Recovery Codes
└─ Creates one student_recovery_code per student

FEAT-IDEN-105: Teacher Validates Recovery Codes (THIS FEAT)
├─ Teacher submits all recovery codes
├─ System validates all-or-nothing
└─ Marks recovery as verified

FEAT-IDEN-106: Update TOTP Secret (ENABLED AFTER RECOVERY)
├─ Teacher resets their TOTP authentication
└─ Generates new secret and backup codes
```

FEAT-IDEN-105 is the culmination of the recovery flow. After successful validation, the teacher has restored access and can reconfigure TOTP (FEAT-IDEN-106) or passkeys (similar FEAT).

---

## X. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-103_TEACHER_RECOVERY_INITIATION.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-104_STUDENT_RECOVERY_CODE_GENERATION_FOR_TEACHER.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-106_TEACHER_UPDATE_TOTP_SECRET.md`
- `docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`

---

## XI. Implementation Checklist

Before code review, verify:

- [ ] Recovery request validation (active and not expired)
- [ ] Teacher identity matching (recovery belongs to this teacher)
- [ ] Expected code count calculation (one per claimed student)
- [ ] Code count validation (all-or-nothing: reject if incomplete)
- [ ] Code hashing matches submission (bcrypt + pepper)
- [ ] All codes validated before updating state
- [ ] Expiration check on recovery request
- [ ] StudentRecoveryCode records marked used (used_at set)
- [ ] RecoveryRequest status updated to verified
- [ ] All mutations occur in a single transaction
- [ ] Audit event emitted with all required fields
- [ ] Rollback occurs on any failure
- [ ] Recovery codes are NOT logged (only count)
- [ ] Generic error messages (no code/seat info leaked)
- [ ] Idempotency check prevents double-verification
- [ ] Tests cover successful validation and idempotent retry
- [ ] Tests cover incomplete submission scenario
- [ ] Tests cover invalid code scenario
- [ ] Tests cover expired recovery scenario

---

## XII. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-003 §IV.
4. Maintain consistency with FEAT-CORE-000.
5. Maintain consistency with FEAT-IDEN-103, FEAT-IDEN-104, and FEAT-IDEN-106.

**This is version 1.0 of FEAT-IDEN-105 (new specification, 2026-08-09).**
