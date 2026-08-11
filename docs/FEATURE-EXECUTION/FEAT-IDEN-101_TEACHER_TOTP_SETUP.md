# FEAT-IDEN-101: Teacher TOTP Setup
**[NEW - Compliant with DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-101 | 1.0 | 2026-08-09 | N/A (new) | Normative | NEW |

---

## I. Purpose

This FEAT activates TOTP (Time-based One-Time Password) two-factor authentication on a teacher `User` account during initial setup or reconfiguration. Per DOM-IDEN-003 §III.B:
> "Teachers MUST enroll in TOTP (required 2FA) before gaining classroom access."

This FEAT generates a TOTP secret, stores it encrypted on the `User` record, and provides QR code and backup codes for the teacher to secure.

**Governing Authority:**
- DOM-IDEN-003 §III.B (Teacher Authentication - TOTP Required)
- DOM-IDEN-003 §IV (Teacher Recovery with Student-Verified Codes)
- DOM-IDEN-005 §VIII (Identity Binding)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `user_id`: The teacher `User` being onboarded (from session or context).
* `seat_id`: The admin `Seat` in the target class (from context).
* `class_id`: The class context (from session or context).
* `idempotency_key`: Client-provided unique request ID for retry safety.

### 2. Resolved Context (MANDATORY)

Before mutation, the FEAT MUST resolve:
* The `User` record matching `user_id` in the `users` table.
* The `Seat` record matching `seat_id` in the `seats` table.
* Verify that `User.id == Seat.user_id` (seat is bound to this user).
* Verify that `Seat.role = 'teacher'` (seat is a teacher seat).
* Verify that `Seat.class_id == class_id` (seat is in the correct class).

---

## III. Orchestration Logic

### A. Verification Phase (Read-Only)

#### Step 1: Validate Teacher User State
1. Query `User` record where `id = user_id`.
2. Verify that `user_role = 'teacher'`.
3. **Failure Behavior**: Abort with `INVALID_USER_ROLE` if user is not a teacher.

#### Step 2: Check TOTP Enrollment Status
1. Query `User.totp_secret_encrypted`.
2. If already enrolled (not NULL), return `ALREADY_ENROLLED` (idempotent success).
3. If not enrolled (NULL), proceed to generate secret.

#### Step 3: Validate Seat State
1. Query `Seat` record where `id = seat_id`.
2. Verify that `user_id = user_id` (seat is bound to the target user).
3. Verify that `role = 'teacher'` (seat is a teacher seat).
4. **Failure Behavior**: Abort with `INVALID_SEAT_STATE` if seat is not a teacher seat.

---

### B. Mutation Phase (Atomic Transaction)

All mutations in this section **MUST** occur within a single database transaction.

#### Step 1: Generate TOTP Secret

Perform secret generation outside the transaction:
1. `secret = pyotp.random_base32()` (generates 32-character base32-encoded secret).
2. `encrypted_secret = NORMALIZE_TOTP_FOR_STORAGE(secret)` (applies AES-128 encryption with `ENCRYPTION_KEY`).

**Note:** The unencrypted secret is displayed to the teacher ONLY during this initial setup. It is NOT stored in plaintext.

#### Step 2: Activate TOTP on User

Update the `User` record:
1. Set `totp_secret_encrypted = encrypted_secret` (store encrypted TOTP seed).

Per DOM-IDEN-003 §III.B:
> "Teacher-specific fields: `totp_secret_encrypted`"

#### Step 3: Generate Backup Codes

Generate recovery backup codes (optional, for manual fallback):
1. Create 10 backup codes (alphanumeric, format: XXXX-XXXX-XXXX-XXXX).
2. Hash each backup code with `HASH_PASSWORD()` (same bcrypt + pepper as student credentials).
3. Store hashes in a temporary in-memory structure (do NOT persist during initial setup; backup codes are displayed once and discarded).

**Note:** Backup codes are distinct from student-verified recovery codes (FEAT-IDEN-104). These are for manual fallback only.

#### Step 4: Audit Trace

Per FEAT-CORE-000 §III.4:

1. Call `DOM-OPS` to emit an `ACT-IDEN-101` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-101"
   - `user_id`: The teacher `user_id`
   - `seat_id`: The admin `seat_id`
   - `class_id`: The classroom context
   - `idempotency_key`: The provided key
   - `outcome`: `"TOTP_ENROLLED"` (only possible outcome for new enrollment)
   - `timestamp`: ISO 8601 UTC timestamp

**Note:** DO NOT log the unencrypted secret or backup codes.

---

## IV. Invariants & Constraints

### 1. TOTP Required for Teachers (MANDATORY)
Per DOM-IDEN-003 §III.B:
> "All teacher users MUST have TOTP enrolled before they can authenticate."

Once this FEAT completes, the teacher's login flow requires TOTP code verification (orchestrated by a separate authentication FEAT, T-001).

### 2. Secret Encryption (MANDATORY)
The TOTP secret SHALL be encrypted at rest using `NORMALIZE_TOTP_FOR_STORAGE()` with `ENCRYPTION_KEY` from environment.

### 3. Single Enrollment (MANDATORY)
Once enrolled, this FEAT **SHALL NOT** re-enroll (idempotent). Changing TOTP secret requires FEAT-IDEN-106 (Update TOTP Secret), which invalidates the old secret.

### 4. Atomic Transaction (MANDATORY)
All mutations SHALL occur in a single transaction. If any step fails, complete rollback occurs.

### 5. One-Time Display (MANDATORY)
The unencrypted secret is displayed to the teacher ONLY ONCE during initial setup via QR code and text representation. After display, the secret is never revealed again (only the encrypted version is stored).

---

## V. Idempotency

**Mechanism:** The combination of `idempotency_key` and `user_id` acts as the idempotency lock.

**Behavior:**
- If a retry occurs with the same `idempotency_key`:
  - Check if `User.totp_secret_encrypted IS NOT NULL` (TOTP already enrolled).
  - If true, return success with outcome `ALREADY_ENROLLED` (no duplicate state).
  - If false, re-attempt the full mutation.
- Replayed requests with the same `idempotency_key` **SHALL NOT** create duplicate audit events.

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
4. **NOT advance the teacher** past the TOTP setup step.

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| User not a teacher | `INVALID_USER_ROLE` | 403 | "Only teachers can enroll TOTP." |
| Invalid seat | `INVALID_SEAT_STATE` | 409 | "Invalid seat. Please start over." |
| Already enrolled | `ALREADY_ENROLLED` | 200 | "TOTP is already enrolled on this account. To change it, use the Update TOTP option." |
| Encryption error | `ENCRYPTION_FAILED` | 500 | "Failed to encrypt TOTP secret. Please try again." |
| Database error | `INTERNAL_ERROR` | 500 | "An error occurred during setup. Please try again." |

---

## VII. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies the FEAT (always "FEAT-IDEN-101") |
| `user_id` | Integer | ✓ | The teacher user |
| `seat_id` | Integer | ✓ | The admin seat |
| `class_id` | UUID | ✓ | The classroom context |
| `idempotency_key` | String | ✓ | Replay detection |
| `outcome` | Enum | ✓ | Must be: `TOTP_ENROLLED` or `ALREADY_ENROLLED` |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of enrollment |
| `totp_secret` | String | ✗ | DO NOT log (security) |
| `backup_codes` | Array | ✗ | DO NOT log (security) |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes:**
- `TOTP_ENROLLED`: Successful TOTP enrollment on a previously-uncredentialed teacher.
- `ALREADY_ENROLLED`: Idempotent return; TOTP was already enrolled (no new secret generated).

---

## VIII. Display Requirements

After successful enrollment, the route handler SHALL display to the teacher:

1. **QR Code**: Scannable image representing the TOTP secret.
   - Generated from `secret` using `qrcode.QRCode()` or similar.
   - Encodes: `otpauth://totp/classroom-economy:{user_id}@{class_id}?secret={secret}&issuer=ClassroomEconomy`.

2. **Text Representation**: Raw base32 secret for manual entry.
   - Format: `{secret}` (32-character string).
   - Display once, then hide (user must write down or save).

3. **Backup Codes**: 10 single-use recovery codes.
   - Format: XXXX-XXXX-XXXX-XXXX.
   - Display once, then hide.
   - Instruct teacher to store securely.

4. **Setup Confirmation**: Button to confirm teacher has saved codes.
   - Clicking confirms teacher has secured the secret and backup codes.
   - Cannot proceed without confirmation.

---

## IX. Integration with FEAT-IDEN-104 (Student-Verified Recovery)

**TOTP setup enables the recovery mechanism:**

```
TOTP Setup (FEAT-IDEN-101)
├─ Teacher enrolls TOTP secret
└─ Teacher secures backup codes

Teacher Recovery Flow (FEAT-IDEN-103 through FEAT-IDEN-105)
├─ If teacher loses access, initiate recovery (FEAT-IDEN-103)
├─ Students provide recovery codes (FEAT-IDEN-104)
└─ Teacher identity verified, TOTP can be reset (FEAT-IDEN-106)
```

Both TOTP enrollment and recovery use the same `recovery_requests` and `student_recovery_codes` tables. Recovery is triggered separately but assumes TOTP is already enrolled.

---

## X. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`
- `docs/DOMAIN/DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md`

---

## XI. Implementation Checklist

Before code review, verify:

- [ ] User role validation ensures only teachers can enroll
- [ ] TOTP secret is generated with `pyotp.random_base32()`
- [ ] Secret is encrypted with `NORMALIZE_TOTP_FOR_STORAGE()` before storage
- [ ] Seat binding is verified before setup
- [ ] QR code generated correctly for authenticator apps
- [ ] Backup codes are hashed with bcrypt + pepper
- [ ] Unencrypted secret displayed only once
- [ ] All mutations occur in a single transaction
- [ ] Audit event emitted with all required fields
- [ ] Rollback occurs on any failure
- [ ] Secret and backup codes are NOT logged in audit
- [ ] Idempotency check prevents duplicate enrollment
- [ ] Tests cover successful enrollment and idempotent retry
- [ ] Tests cover already-enrolled scenario

---

## XII. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-003 §III.B.
4. Maintain consistency with FEAT-CORE-000.
5. Maintain consistency with FEAT-IDEN-103, FEAT-IDEN-104, FEAT-IDEN-106.

**This is version 1.0 of FEAT-IDEN-101 (new specification, 2026-08-09).**
