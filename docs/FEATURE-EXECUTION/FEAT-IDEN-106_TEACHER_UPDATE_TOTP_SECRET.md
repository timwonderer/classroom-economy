# FEAT-IDEN-106: Teacher Update TOTP Secret
**[NEW - Compliant with DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-106 | 1.0 | 2026-08-09 | N/A (new) | Normative | NEW |

---

## I. Purpose

This FEAT allows a teacher to change their TOTP (Time-based One-Time Password) secret. This is needed in two scenarios:

1. **Account Recovery**: After successful student-verified recovery (FEAT-IDEN-105), teacher must reset TOTP.
2. **Credential Rotation**: Teacher proactively changes TOTP for security (e.g., lost authenticator device).

Per DOM-IDEN-003 §III.B:
> "Teachers can update their TOTP secret at any time. The old secret is invalidated immediately upon update."

This FEAT generates a new TOTP secret, encrypts and stores it, and optionally generates new backup codes.

**Governing Authority:**
- DOM-IDEN-003 §III.B (Teacher Authentication - TOTP Update)
- DOM-IDEN-005 §VIII (Identity Binding)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `user_id`: The teacher `User` updating TOTP (from session, authenticated).
* `seat_id`: The admin `Seat` in the target class (from context).
* `class_id`: The class context (from session or context).
* `recovery_context_id`: Optional recovery request ID if this is part of account recovery (FEAT-IDEN-105).
* `idempotency_key`: Client-provided unique request ID for retry safety.

### 2. Resolved Context (MANDATORY)

Before mutation, the FEAT MUST resolve:
* The `User` record matching `user_id` in the `users` table.
* The `Seat` record matching `seat_id` in the `seats` table.
* Verify that `User.id == Seat.user_id` (seat is bound to this user).
* Verify that `Seat.role = 'admin'` (seat is a teacher seat).
* Verify that `Seat.class_id == class_id` (seat is in the correct class).

---

## III. Orchestration Logic

### A. Verification Phase (Read-Only)

#### Step 1: Validate Teacher User State
1. Query `User` record where `id = user_id`.
2. Verify that `user_role = 'teacher'`.
3. **Failure Behavior**: Abort with `INVALID_USER_ROLE` if user is not a teacher.

#### Step 2: Validate Seat State
1. Query `Seat` record where `id = seat_id`.
2. Verify that `user_id = user_id` (seat is bound to the target user).
3. Verify that `role = 'admin'` (seat is an admin/teacher seat).
4. **Failure Behavior**: Abort with `INVALID_SEAT_STATE` if seat is not an admin seat.

#### Step 3: Verify Recovery Context (If Provided)
1. If `recovery_context_id` is provided:
   - Query `recovery_requests` where `id = recovery_context_id`.
   - Verify that `user_id = user_id` (recovery is for this teacher).
   - Verify that `status = 'verified'` (recovery has completed successfully).
   - Verify that `expires_at > NOW()` (recovery not expired).
2. **Failure Behavior**: Abort with `RECOVERY_CONTEXT_INVALID` if recovery context is invalid.

**Note:** If no recovery context, this is a proactive TOTP rotation (not part of recovery).

#### Step 4: Check Current TOTP
1. Query `User.totp_secret_encrypted`.
2. Verify that TOTP is already enrolled (not NULL).
3. **Failure Behavior**: Abort with `TOTP_NOT_ENROLLED` if no TOTP exists (use FEAT-IDEN-101 for initial setup).

---

### B. Mutation Phase (Atomic Transaction)

All mutations in this section **MUST** occur within a single database transaction.

#### Step 1: Generate New TOTP Secret

Perform secret generation outside the transaction:
1. `new_secret = pyotp.random_base32()` (generates 32-character base32-encoded secret).
2. `encrypted_secret = NORMALIZE_TOTP_FOR_STORAGE(new_secret)` (applies AES-128 encryption with `ENCRYPTION_KEY`).

**Note:** The unencrypted new secret is displayed to the teacher ONLY ONCE. It is NOT stored in plaintext.

#### Step 2: Replace TOTP on User

Update the `User` record:
1. Set `totp_secret_encrypted = encrypted_secret` (store encrypted new TOTP seed, overwriting old secret).

Per DOM-IDEN-003 §III.B:
> "Updating the TOTP secret invalidates the previous secret immediately."

**Important:** The old secret is overwritten, not preserved. There is no rollback to old credentials after update.

#### Step 3: Generate New Backup Codes

Generate recovery backup codes (optional, same as FEAT-IDEN-101):
1. Create 10 new backup codes (alphanumeric, format: XXXX-XXXX-XXXX-XXXX).
2. Hash each backup code with `HASH_PASSWORD()` (same bcrypt + pepper as student credentials).
3. Store hashes in a temporary in-memory structure (do NOT persist during setup; backup codes are displayed once and discarded).

**Note:** Old backup codes are invalidated. New codes must be secured by the teacher.

#### Step 4: Clear Recovery Context (If Applicable)

If `recovery_context_id` was provided:
1. Update `recovery_requests` where `id = recovery_context_id`:
   - Set `status = 'completed'` (recovery fully resolved).
   - Set `updated_at = NOW()`.
2. **Note:** This marks the recovery as complete. The teacher can now authenticate normally.

#### Step 5: Audit Trace

Per FEAT-CORE-000 §III.4:

1. Call `DOM-OPS` to emit an `ACT-IDEN-106` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-106"
   - `user_id`: The teacher `user_id`
   - `seat_id`: The admin `seat_id`
   - `class_id`: The classroom context
   - `recovery_context_id`: If part of recovery, the recovery request ID (optional)
   - `idempotency_key`: The provided key
   - `outcome`: `"TOTP_UPDATED"` (only possible outcome)
   - `timestamp`: ISO 8601 UTC timestamp

**Note:** DO NOT log the old or new unencrypted secrets or backup codes.

---

## IV. Invariants & Constraints

### 1. Old Secret Invalidated (MANDATORY)
Per DOM-IDEN-003 §III.B:
> "Updating TOTP immediately invalidates the old secret. There is no grace period or rollback."

Once the new secret is stored, the old secret cannot be used to generate valid TOTP codes.

### 2. TOTP Must Already Be Enrolled (MANDATORY)
This FEAT only updates existing TOTP. For initial enrollment, use FEAT-IDEN-101.

### 3. One-Time Display (MANDATORY)
The unencrypted new secret is displayed to the teacher ONLY ONCE during update. After display, it is never revealed again.

### 4. Atomic Transaction (MANDATORY)
All mutations SHALL occur in a single transaction. If any step fails, complete rollback occurs and old secret remains valid.

### 5. New Backup Codes (MANDATORY)
When updating TOTP, new backup codes must be generated. Old backup codes become invalid.

### 6. Recovery Context Optional (MANDATORY)
TOTP update can occur:
- As part of account recovery (with `recovery_context_id`), OR
- As proactive credential rotation (without recovery context).

Both scenarios use the same FEAT logic.

---

## V. Idempotency

**Mechanism:** The combination of `idempotency_key` and `user_id` acts as the idempotency lock.

**Behavior:**
- If a retry occurs with the same `idempotency_key`:
  - Check if `recovery_requests.status = 'completed'` (recovery already complete) OR the secret has been updated recently.
  - If true, return success with outcome `ALREADY_UPDATED` (no duplicate state).
  - If false, re-attempt the full mutation.
- Replayed requests with the same `idempotency_key` **SHALL NOT** create duplicate TOTP resets or backup code generations.

**Client Responsibility:**
- Generate a stable `idempotency_key` (e.g., based on session).
- Retry on transient errors with the same key.
- Server stores key on audit log to detect and skip replays.

**Important:** Once a TOTP secret is updated, there is no "previous" secret to restore. Idempotency means returning success on retry with the same key, not rolling back to an old secret.

---

## VI. Failure Scenarios

When the FEAT fails, the system SHALL:

1. **Rollback all mutations** atomically.
2. **Emit audit event** with outcome `FAILED` and error code.
3. **Return error response** to client.
4. **Keep old TOTP secret intact** (no partial updates).

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| User not a teacher | `INVALID_USER_ROLE` | 403 | "Only teachers can update TOTP." |
| Invalid seat | `INVALID_SEAT_STATE` | 409 | "Invalid seat. Please start over." |
| TOTP not enrolled | `TOTP_NOT_ENROLLED` | 409 | "TOTP is not yet enrolled. Use setup to enable TOTP first." |
| Recovery context invalid | `RECOVERY_CONTEXT_INVALID` | 409 | "Recovery context is invalid. Please start a new recovery." |
| Encryption error | `ENCRYPTION_FAILED` | 500 | "Failed to encrypt new TOTP secret. Please try again." |
| Database error | `INTERNAL_ERROR` | 500 | "An error occurred during update. Please try again." |

---

## VII. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies the FEAT (always "FEAT-IDEN-106") |
| `user_id` | Integer | ✓ | The teacher user |
| `seat_id` | Integer | ✓ | The admin seat |
| `class_id` | UUID | ✓ | The classroom context |
| `recovery_context_id` | Integer | ⚠️ | Recovery request ID if part of recovery, else NULL |
| `idempotency_key` | String | ✓ | Replay detection |
| `outcome` | Enum | ✓ | Must be: `TOTP_UPDATED` or `ALREADY_UPDATED` |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of update |
| `old_secret` | String | ✗ | DO NOT log (security) |
| `new_secret` | String | ✗ | DO NOT log (security) |
| `backup_codes` | Array | ✗ | DO NOT log (security) |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes:**
- `TOTP_UPDATED`: Successful TOTP secret update.
- `ALREADY_UPDATED`: Idempotent return; TOTP already updated in a previous request.

---

## VIII. Display Requirements

After successful TOTP update, the route handler SHALL display to the teacher:

1. **Confirmation**: "TOTP secret updated successfully!"
2. **New QR Code**: Scannable image for the new secret.
   - Generated from `new_secret` using `qrcode.QRCode()`.
   - Encodes: `otpauth://totp/classroom-economy:{user_id}@{class_id}?secret={new_secret}&issuer=ClassroomEconomy`.

3. **Text Representation**: Raw base32 new secret for manual entry.
   - Format: `{new_secret}` (32-character string).
   - Display once, then hide.

4. **New Backup Codes**: 10 single-use recovery codes.
   - Format: XXXX-XXXX-XXXX-XXXX.
   - Display once, then hide.
   - Instruct teacher to store securely (replacing old codes).

5. **Setup Confirmation**: Button to confirm teacher has saved new codes.
   - Clicking confirms teacher has secured the new secret and backup codes.
   - Cannot proceed without confirmation (if part of recovery).

6. **If Recovery Context**: "Your account access has been restored. Your TOTP is now updated."

---

## IX. Integration with FEAT-IDEN-105 (Recovery)

**TOTP update completes the account recovery flow:**

```
FEAT-IDEN-103: Teacher Initiates Recovery
└─ Creates recovery_request

FEAT-IDEN-104: Students Generate Recovery Codes
└─ Creates student_recovery_code records

FEAT-IDEN-105: Teacher Validates Recovery Codes
└─ Verifies all-or-nothing, marks recovery as verified

FEAT-IDEN-106: Update TOTP Secret (THIS FEAT)
├─ Teacher resets TOTP with new secret
└─ Completes recovery (marks status: completed)
```

After FEAT-IDEN-106 completes with recovery context, the teacher has full account access restored.

---

## X. Security Considerations

### Old Secret Invalidation
The moment the new secret is stored, the old secret becomes invalid. There is NO grace period. If the teacher needs to revert, they must restart account recovery.

### Backup Code Replacement
Old backup codes are invalidated. The teacher MUST save the new backup codes. If they lose both the new secret AND all backup codes, they must initiate account recovery again.

### Rate Limiting (Recommended)
To prevent brute-force TOTP changes, rate-limit TOTP updates:
- Max 5 updates per day per user (or similar threshold).
- Log all updates for anomaly detection.

---

## XI. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-101_TEACHER_TOTP_SETUP.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md`
- `docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`

---

## XII. Implementation Checklist

Before code review, verify:

- [ ] User role validation ensures only teachers can update
- [ ] Current TOTP verification (TOTP already enrolled)
- [ ] New secret generation with `pyotp.random_base32()`
- [ ] New secret encrypted with `NORMALIZE_TOTP_FOR_STORAGE()`
- [ ] Old secret completely replaced (no fallback)
- [ ] Seat binding is verified before update
- [ ] Recovery context validation (if provided)
- [ ] QR code generated correctly for new secret
- [ ] New backup codes generated and hashed
- [ ] Old backup codes invalidated (implicitly, by not storing separately)
- [ ] All mutations occur in a single transaction
- [ ] RecoveryRequest marked as completed (if recovery context)
- [ ] Audit event emitted with all required fields
- [ ] Rollback occurs on any failure
- [ ] Secrets and backup codes are NOT logged
- [ ] Idempotency check prevents duplicate updates
- [ ] Tests cover successful update and idempotent retry
- [ ] Tests cover recovery context scenario
- [ ] Tests cover proactive rotation scenario (no recovery context)

---

## XIII. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-003 §III.B.
4. Maintain consistency with FEAT-CORE-000.
5. Maintain consistency with FEAT-IDEN-101 (initial TOTP setup).

**This is version 1.0 of FEAT-IDEN-106 (new specification, 2026-08-09).**
