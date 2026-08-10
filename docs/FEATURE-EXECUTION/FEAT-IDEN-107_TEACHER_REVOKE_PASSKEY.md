# FEAT-IDEN-107: Teacher Revoke Passkey
**[NEW - Compliant with DOM-IDEN Authority]**

| Reference Number | Version | Effective Date | Supersedes | Authority Level | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-107 | 1.0 | 2026-08-09 | N/A (new) | Normative | NEW |

---

## I. Purpose

This FEAT allows a teacher to revoke (remove) an enrolled passkey credential from their account. Per DOM-IDEN-003 §III.B:
> "Teachers can revoke passkey credentials at any time. Revoking a passkey does not affect TOTP (the mandatory factor)."

This FEAT deletes a single `passkey_credentials` record, disabling that authenticator for login. The teacher can still authenticate using TOTP alone.

**Governing Authority:**
- DOM-IDEN-003 §III.B (Teacher Authentication - Passkey Management)
- DOM-IDEN-005 §VIII (Identity Binding)
- FEAT-CORE-000 (Feature Execution Constitutional Directive)

---

## II. Execution Context

### 1. Required Inputs

* `user_id`: The teacher `User` revoking passkey (from session, authenticated).
* `seat_id`: The admin `Seat` in the target class (from context).
* `class_id`: The class context (from session or context).
* `credential_id`: The base64url-encoded credential ID of the passkey to revoke.
* `idempotency_key`: Client-provided unique request ID for retry safety.

### 2. Resolved Context (MANDATORY)

Before mutation, the FEAT MUST resolve:
* The `User` record matching `user_id` in the `users` table.
* The `Seat` record matching `seat_id` in the `seats` table.
* The `PasskeyCredential` record matching `credential_id` and `user_id`.
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

#### Step 3: Lookup Passkey Credential
1. Query `passkey_credentials` where `credential_id = credential_id` and `user_id = user_id`.
2. Verify the credential exists.
3. **Failure Behavior**: Abort with `CREDENTIAL_NOT_FOUND` if the credential does not exist or belongs to a different user.

#### Step 4: Verify Credential Ownership
1. Ensure `passkey_credentials.user_id == user_id` (credential belongs to this teacher).
2. **Failure Behavior**: Abort with `OWNERSHIP_MISMATCH` if credential belongs to someone else (data integrity issue).

#### Step 5: Check Remaining Authentication Factors
1. Query `User.totp_secret_encrypted`.
2. Verify that TOTP is still enrolled (not NULL).
   - Passkey is optional; revoking it should not leave the teacher unable to authenticate.
   - If TOTP is NULL, this indicates a data integrity issue.
3. **Failure Behavior**: Abort with `CANNOT_REVOKE_LAST_FACTOR` if revoking this passkey would leave no authentication methods.

**Note:** TOTP is mandatory, so it should always exist. This is a safety check.

---

### B. Mutation Phase (Atomic Transaction)

All mutations in this section **MUST** occur within a single database transaction.

#### Step 1: Delete PasskeyCredential Record

Delete from `passkey_credentials` table:
1. WHERE `credential_id = credential_id` and `user_id = user_id`.
2. Confirm exactly one row was deleted (idempotency check).

Per DOM-IDEN-003 §III.B:
> "Passkey credentials can be revoked (deleted) at any time."

**Note:** This is a hard delete, not a soft delete (status flag). The credential is completely removed.

#### Step 2: Audit Trace

Per FEAT-CORE-000 §III.4:

1. Call `DOM-OPS` to emit an `ACT-IDEN-107` audit event.
2. **Required fields**:
   - `feat_id`: "FEAT-IDEN-107"
   - `user_id`: The teacher `user_id`
   - `seat_id`: The admin `seat_id`
   - `class_id`: The classroom context
   - `authenticator_name`: The name of the revoked passkey (safe to log)
   - `credential_id_hash`: A hash of the credential ID (optional, for identification without storing full ID)
   - `idempotency_key`: The provided key
   - `outcome`: `"PASSKEY_REVOKED"` (only possible outcome)
   - `timestamp`: ISO 8601 UTC timestamp

**Note:** DO NOT log the full credential ID or public key.

---

## IV. Invariants & Constraints

### 1. Optional Factor (MANDATORY)
Passkey is optional. Revoking all passkeys does not prevent authentication (TOTP is mandatory and sufficient).

### 2. Cannot Revoke Last Factor (MANDATORY)
While TOTP is mandatory, this check prevents data integrity issues where both TOTP and passkey are missing.

### 3. Ownership Verification (MANDATORY)
A teacher can ONLY revoke their own passkeys. Cross-user revocation is prevented.

### 4. Atomic Transaction (MANDATORY)
The deletion SHALL occur in a single transaction. If any step fails, complete rollback occurs.

### 5. Hard Delete (MANDATORY)
Revoked credentials are permanently deleted, not marked inactive. There is no recovery or restoration path.

### 6. Multiple Passkeys Allowed (MANDATORY)
A teacher can revoke individual passkeys without affecting others. Multiple passkeys can coexist.

---

## V. Idempotency

**Mechanism:** The combination of `idempotency_key` and `credential_id` acts as the idempotency lock.

**Behavior:**
- If a retry occurs with the same `idempotency_key`:
  - Check if `passkey_credentials` row exists for this `credential_id` and `user_id`.
  - If false (already deleted), return success with outcome `ALREADY_REVOKED` (no duplicate state).
  - If true (still exists), re-attempt the full deletion.
- Replayed requests with the same `idempotency_key` **SHALL NOT** cause errors on retry if the credential is already gone.

**Client Responsibility:**
- Generate a stable `idempotency_key` (e.g., based on session and credential ID).
- Retry on transient errors with the same key.
- Server stores key on audit log to detect and skip replays.

---

## VI. Failure Scenarios

When the FEAT fails, the system SHALL:

1. **Rollback all mutations** atomically.
2. **Emit audit event** with outcome `FAILED` and error code.
3. **Return error response** to client.
4. **Keep the passkey credential intact** (no partial deletes).

**Failure Cases:**

| Scenario | Error Code | HTTP Status | Message |
|----------|-----------|-------------|---------|
| User not a teacher | `INVALID_USER_ROLE` | 403 | "Only teachers can manage passkeys." |
| Invalid seat | `INVALID_SEAT_STATE` | 409 | "Invalid seat. Please start over." |
| Credential not found | `CREDENTIAL_NOT_FOUND` | 404 | "Passkey not found. It may have already been removed." |
| Ownership mismatch | `OWNERSHIP_MISMATCH` | 403 | "You don't have permission to revoke this passkey." |
| Cannot revoke last factor | `CANNOT_REVOKE_LAST_FACTOR` | 409 | "Cannot revoke the last authentication factor." |
| Database error | `INTERNAL_ERROR` | 500 | "An error occurred. Please try again." |

---

## VII. Audit Requirements

The `DOM-OPS` audit log **MUST** contain:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `feat_id` | String | ✓ | Identifies the FEAT (always "FEAT-IDEN-107") |
| `user_id` | Integer | ✓ | The teacher user |
| `seat_id` | Integer | ✓ | The admin seat |
| `class_id` | UUID | ✓ | The classroom context |
| `idempotency_key` | String | ✓ | Replay detection |
| `authenticator_name` | String | ✓ | User-provided passkey name (safe to log) |
| `credential_id_hash` | String | ⚠️ | Hash of credential ID for identification (optional) |
| `outcome` | Enum | ✓ | Must be: `PASSKEY_REVOKED` or `ALREADY_REVOKED` |
| `timestamp` | ISO 8601 | ✓ | UTC timestamp of revocation |
| `credential_id` | String | ✗ | DO NOT log (security) |
| `public_key` | String | ✗ | DO NOT log (security) |
| `error_code` | String | ⚠️ | Only if outcome is `FAILED` |

**Outcomes:**
- `PASSKEY_REVOKED`: Successful passkey credential revocation.
- `ALREADY_REVOKED`: Idempotent return; credential already revoked.

---

## VIII. Display Requirements

After successful passkey revocation, the route handler SHALL display to the teacher:

1. **Confirmation**: "Passkey revoked successfully!"
2. **Authenticator Name**: Show the name of the revoked passkey (e.g., "YubiKey 5").
3. **Impact Message**: "You can still authenticate using TOTP. This passkey will no longer work for login."
4. **Option to Return**: Link or button to return to passkey management view.
   - Show list of remaining passkeys (if any).
   - Option to enroll new passkeys.

---

## IX. Integration with Passkey Management

**Passkey revocation is part of credential management:**

```
FEAT-IDEN-102: Enroll Passkey
└─ Teacher adds a new passkey credential

Teacher Passkey Management (EXISTING FEATS)
├─ View enrolled passkeys (read-only)
└─ Revoke individual passkeys (FEAT-IDEN-107)

FEAT-IDEN-107: Revoke Passkey (THIS FEAT)
└─ Remove a single passkey credential
```

Multiple passkeys can be managed independently. Revoking one does not affect others.

---

## X. Security Considerations

### Credential Deletion is Permanent
Once revoked, a credential cannot be recovered or restored. The teacher must re-enroll the same authenticator if they want to use it again.

### Ownership Verification is Critical
The FEAT strictly verifies that the passkey belongs to the authenticated teacher. Cross-user revocation attempts are rejected.

### Hard Delete vs. Soft Delete
This FEAT uses hard delete (permanent removal) rather than soft delete (marking inactive). This keeps the database clean and prevents accumulation of revoked credentials.

---

## XI. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-IDEN-102_TEACHER_PASSKEY_ENROLLMENT.md`
- `docs/DOMAIN/DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`

---

## XII. Implementation Checklist

Before code review, verify:

- [ ] User role validation ensures only teachers can revoke
- [ ] Seat binding is verified before revocation
- [ ] Credential lookup by ID and user ownership
- [ ] Ownership verification prevents cross-user revocation
- [ ] TOTP existence check (prevent last-factor revocation)
- [ ] Hard delete from passkey_credentials table
- [ ] Exactly one row deleted (idempotency)
- [ ] All mutations occur in a single transaction
- [ ] Audit event emitted with all required fields
- [ ] Rollback occurs on any failure
- [ ] Credential ID is NOT logged (only hash if needed)
- [ ] Idempotency check handles already-revoked credentials
- [ ] Tests cover successful revocation
- [ ] Tests cover idempotent retry (already revoked)
- [ ] Tests cover ownership mismatch (cross-user attempt)
- [ ] Tests cover last-factor prevention

---

## XIII. Amendments

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-003 §III.B.
4. Maintain consistency with FEAT-CORE-000.
5. Maintain consistency with FEAT-IDEN-102 (Enroll Passkey).

**This is version 1.0 of FEAT-IDEN-107 (new specification, 2026-08-09).**
