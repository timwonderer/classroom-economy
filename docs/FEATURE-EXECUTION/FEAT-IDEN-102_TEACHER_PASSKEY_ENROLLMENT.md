# FEAT-IDEN-102: Teacher Passkey Enrollment
**[NEW - Compliant with DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-102 | 1.0 | 2026-08-09 | N/A (new) | Normative | NEW |

---

## I. Purpose

This FEAT enrolls an optional passkey credential (WebAuthn/FIDO2) on a teacher `User` account as an alternative or supplementary authentication factor. Per DOM-IDEN-003 §III.B:
> "Teachers MAY enroll passkey credentials as an optional second factor (in addition to required TOTP)."

This FEAT stores passkey metadata in the `passkey_credentials` table, allowing the teacher to authenticate using biometric or security key after initial TOTP enrollment.

**Governing Authority:**
- DOM-IDEN-003 §III.B (Teacher Authentication - Passkey Optional)
- DOM-IDEN-005 §VIII (Identity Binding)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `user_id`: The teacher `User` enrolling passkey (from session or context).
* `seat_id`: The admin `Seat` in the target class (from context).
* `class_id`: The class context (from session or context).
* `webauthn_response`: The raw WebAuthn attestation response from the authenticator.
  - Contains: `id`, `rawId`, `response.clientDataJSON`, `response.attestationObject`.
* `authenticator_name`: Human-readable name for the passkey (e.g., "YubiKey 5", "Windows Hello").
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
3. Verify that `totp_secret_encrypted IS NOT NULL` (TOTP already enrolled).
   - Passkey enrollment requires TOTP to be set up first (per DOM-IDEN-003).
4. **Failure Behavior**: Abort with `INVALID_USER_STATE` if user is not a teacher or TOTP not enrolled.

#### Step 2: Validate Seat State
1. Query `Seat` record where `id = seat_id`.
2. Verify that `user_id = user_id` (seat is bound to the target user).
3. Verify that `role = 'admin'` (seat is an admin/teacher seat).
4. **Failure Behavior**: Abort with `INVALID_SEAT_STATE` if seat is not an admin seat.

#### Step 3: Validate WebAuthn Response
1. Verify that `webauthn_response` is valid JSON.
2. Extract and decode `rawId` (base64url).
3. Decode and validate `response.attestationObject` (CBOR format).
4. Extract attested credential data and public key.
5. **Failure Behavior**: Abort with `INVALID_WEBAUTHN_RESPONSE` if response cannot be parsed or validated.

#### Step 4: Verify Attestation Chain (Optional, Security Enhancement)
1. If attestation verification is enabled, validate attestation chain (requires root certificate management).
2. **Failure Behavior**: Abort with `ATTESTATION_FAILED` if attestation cannot be verified (for non-FIDO2 authenticators).

**Note:** Passkey enrollment can proceed without attestation verification in development/testing; production should enforce it.

#### Step 5: Check Credential Uniqueness
1. Query `passkey_credentials` where `credential_id = EXTRACTED_CREDENTIAL_ID`.
2. **Failure Behavior**: Abort with `CREDENTIAL_EXISTS` if this authenticator is already enrolled on another user.

---

### B. Mutation Phase (Atomic Transaction)

All mutations in this section **MUST** occur within a single database transaction.

#### Step 1: Extract and Store Credential Metadata

From the `webauthn_response`, extract:
1. `credential_id`: The public credential ID (base64url encoded, from `rawId`).
2. `public_key`: The extracted public key (CBOR-encoded, persisted as-is or base64url).
3. `sign_count`: The initial signature counter (for rollback detection in future authentications).
4. `aaguid`: The authenticator's AAGUID (for device identification).
5. `transports`: Supported transports (if available; e.g., ["usb", "internal"]).

#### Step 2: Create PasskeyCredential Record

Insert into `passkey_credentials` table:
1. `user_id`: The teacher user.
2. `credential_id`: The public credential ID (base64url).
3. `public_key`: The public key (stored encrypted or plaintext depending on security requirements).
4. `sign_count`: Initial signature counter (0 or extracted value).
5. `aaguid`: Authenticator AAGUID.
6. `authenticator_name`: User-provided name (e.g., "YubiKey 5").
7. `transports`: JSON array of supported transports (optional).
8. `created_at`: ISO 8601 UTC timestamp.
9. `last_used_at`: NULL (not yet used).

#### Step 3: Audit Trace

Per FEAT-CORE-000 §III.4:

1. Call `DOM-OPS` to emit an `ACT-IDEN-102` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-102"
   - `user_id`: The teacher `user_id`
   - `seat_id`: The admin `seat_id`
   - `class_id`: The classroom context
   - `idempotency_key`: The provided key
   - `authenticator_name`: The passkey name (safe to log)
   - `outcome`: `"PASSKEY_ENROLLED"` (only possible outcome)
   - `timestamp`: ISO 8601 UTC timestamp

**Note:** DO NOT log `credential_id` or `public_key` (security-sensitive).

---

## IV. Invariants & Constraints

### 1. Passkey is Optional (MANDATORY)
Per DOM-IDEN-003 §III.B:
> "Passkey credentials are optional (not required)."

A teacher can authenticate with TOTP alone; passkey is supplementary.

### 2. TOTP Required First (MANDATORY)
Passkey enrollment SHALL only proceed if `totp_secret_encrypted IS NOT NULL`. TOTP is the mandatory primary factor.

### 3. Credential Uniqueness (MANDATORY)
Each `credential_id` SHALL be unique across all users. Two users cannot enroll the same physical authenticator.

### 4. Immutable Metadata (MANDATORY)
Once stored, passkey metadata (credential_id, public_key, aaguid) **SHALL NOT** be modified. Changes require credential revocation (FEAT-IDEN-107) and re-enrollment.

### 5. Atomic Transaction (MANDATORY)
All mutations SHALL occur in a single transaction. If any step fails, complete rollback occurs.

### 6. Multiple Passkeys Allowed (MANDATORY)
A single teacher can enroll multiple passkey credentials. There is no limit on the number of passkeys per user (policy can enforce a soft limit in future versions).

---

## V. Idempotency

**Mechanism:** The combination of `idempotency_key` and `credential_id` acts as the idempotency lock.

**Behavior:**
- If a retry occurs with the same `idempotency_key`:
  - Check if `passkey_credentials` row exists for this `credential_id` and `user_id`.
  - If true, return success with outcome `ALREADY_ENROLLED` (no duplicate state).
  - If false, re-attempt the full mutation.
- Replayed requests with the same `idempotency_key` **SHALL NOT** create duplicate passkey records.

**Client Responsibility:**
- Generate a stable `idempotency_key` (e.g., based on session or authenticator response).
- Retry on transient errors with the same key.
- Server stores key on audit log to detect and skip replays.

---

## VI. Failure Scenarios

When the FEAT fails, the system SHALL:

1. **Rollback all mutations** atomically.
2. **Emit audit event** with outcome `FAILED` and error code.
3. **Return error response** to client.
4. **NOT store incomplete passkey metadata**.

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| User not a teacher | `INVALID_USER_ROLE` | 403 | "Only teachers can enroll passkeys." |
| TOTP not enrolled | `TOTP_NOT_ENROLLED` | 409 | "TOTP must be set up first. Please enable TOTP authentication." |
| Invalid seat | `INVALID_SEAT_STATE` | 409 | "Invalid seat. Please start over." |
| Invalid WebAuthn response | `INVALID_WEBAUTHN_RESPONSE` | 400 | "Invalid passkey registration. Please try again with your authenticator." |
| Attestation failed | `ATTESTATION_FAILED` | 400 | "Authenticator attestation verification failed. This authenticator may not be supported." |
| Credential already exists | `CREDENTIAL_EXISTS` | 409 | "This authenticator is already enrolled on another account." |
| Database error | `INTERNAL_ERROR` | 500 | "An error occurred during enrollment. Please try again." |

---

## VII. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies the FEAT (always "FEAT-IDEN-102") |
| `user_id` | Integer | ✓ | The teacher user |
| `seat_id` | Integer | ✓ | The admin seat |
| `class_id` | UUID | ✓ | The classroom context |
| `idempotency_key` | String | ✓ | Replay detection |
| `authenticator_name` | String | ✓ | User-provided passkey name (safe to log) |
| `outcome` | Enum | ✓ | Must be: `PASSKEY_ENROLLED` or `ALREADY_ENROLLED` |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of enrollment |
| `credential_id` | String | ✗ | DO NOT log (security) |
| `public_key` | String | ✗ | DO NOT log (security) |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes:**
- `PASSKEY_ENROLLED`: Successful passkey enrollment.
- `ALREADY_ENROLLED`: Idempotent return; passkey was already enrolled.

---

## VIII. Integration with Authentication Flow

**Passkey enrollment enables optional biometric/security-key authentication:**

```
TOTP Setup (FEAT-IDEN-101)
└─ Teacher enrolled in TOTP (required)

Passkey Setup (FEAT-IDEN-102)
└─ Teacher enrolls optional security key/biometric

Authentication (Separate FEAT)
├─ Primary: TOTP code verification (required)
└─ Secondary: Passkey assertion (optional, if enrolled)
```

Both TOTP and passkey are stored on the same `User` record (`totp_secret_encrypted` and records in `passkey_credentials` table).

---

## IX. Relationship to Passkey Revocation

**FEAT-IDEN-107 (Revoke Passkey)** removes individual passkey credentials:
- Teacher can revoke a specific passkey without affecting others.
- Revoking all passkeys does NOT affect TOTP (teacher can still log in with TOTP alone).

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
- [ ] TOTP enrollment verification prevents pre-TOTP passkey setup
- [ ] WebAuthn response parsing and validation is correct
- [ ] Credential ID uniqueness is checked across all users
- [ ] Public key is stored securely (encrypted if necessary)
- [ ] Authenticator metadata is preserved (AAGUID, transports)
- [ ] Authenticator name is validated (3-128 characters, safe characters)
- [ ] Seat binding is verified before setup
- [ ] All mutations occur in a single transaction
- [ ] Audit event emitted with all required fields
- [ ] Rollback occurs on any failure
- [ ] Credential ID and public key are NOT logged
- [ ] Multiple passkeys per user are supported
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
5. Maintain consistency with FEAT-IDEN-107 (Revoke Passkey).

**This is version 1.0 of FEAT-IDEN-102 (new specification, 2026-08-09).**
