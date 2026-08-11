# DOM-IDEN Phase 3: Primitive Operations Table

| Reference | Version | Effective Date | Authority Level |
|-----------|---------|----------------|-----------------|
| DOM-IDEN-PHASE-3 | 2.0 | 2026-08-09 | Normative |

---

## I. Purpose

This document defines all lawful primitive operations (reads and writes) for the identity domain covering BOTH student and teacher identities. It is the Phase 3 deliverable of SOP-DEV-002 domain reconstruction.

Every operation is atomic, named, and carries a documented contract of inputs, preconditions, postconditions, and failure modes.

**Scope:** One unified identity domain with role-specific primitives. Student primitives (M-001 through M-005, R-001 through R-012) and teacher primitives (T-001 through T-008, T-R-001 through T-R-007) operate on the same canonical User, Seat, and Class models.

---

## II. Authority

Subordinate to:
- `INV-CORE-000` (Core Invariants)
- `INV-ARC-008` (Identity Resolution and Seat Scope)
- `DOM-IDEN-001` (Canonical Identity Model)
- `DOM-IDEN-002` (Student Identity Architecture)
- `DOM-IDEN-003` (Teacher Identity Architecture)
- `DOM-IDEN-005` (Identity Binding and Lifecycle)

---

## III. Mutation Primitives (Commands)

### M-001: Claim Seat (Unauthenticated)

**Owning FEAT:** FEAT-IDEN-001

**Type:** Command (write + authorization)

**Purpose:** First identity establishment: create new User, bind to unclaimed Seat

**Required Context:**
- `class_id` (from join_code resolution)
- `seat_id` or seat lookup: `(class_id, roster_fingerprint, dedupe_code)`

**Inputs:**
- `first_name` (plaintext, encrypted on storage)
- `dedupe_code` (8-char alphanumeric, student-provided)
- `seat_id` (resolved from join_code + name matching)
- `idempotency_key` (replay detection)

**Preconditions:**
- Seat exists and is unclaimed (`claimed_at IS NULL`)
- Seat is not yet bound to a User (`user_id IS NULL`)
- Name + dedupe code match roster fingerprint (per DOM-IDEN-002 §VIII.III)
- No User already exists with matching identity hash for this seat (per DOM-IDEN-005 §VII)
- Request is authenticated via verified seat selection, not global search

**Reads:**
- `Seat` by `(class_id, roster_fingerprint, dedupe_code)`
- Verify `claimed_at IS NULL`
- Verify `user_id IS NULL`
- `ClassEconomy` for `class_id` validation

**Writes:**
- Create `User` with `user_role = 'student'`, no credentials yet
- Set `Seat.user_id = new_user.id`
- Set `Seat.claimed_at = NOW()`
- Create `IdentityProfile` with encrypted name hash
- Initialize `User.last_active_class_id = class_id`

**Postconditions:**
- `User.id` exists
- `Seat.claimed_at IS NOT NULL`
- `Seat.user_id = User.id`
- `User.pin_hash IS NULL` (credentials not yet set)
- `User.passphrase_hash IS NULL` (credentials not yet set)
- User ready for credential setup (FEAT-IDEN-002)

**Failure Cases:**
- Seat already claimed → `SEAT_ALREADY_CLAIMED`
- Name/dedupe mismatch → `IDENTITY_MISMATCH`
- Seat not found → `SEAT_NOT_FOUND`
- Database error → `INTERNAL_ERROR` (rollback all writes)

**Atomicity:** Single transaction. On failure, rollback all writes.

**Audit:** Emits `ACT-IDEN-001` with outcome `NEW_USER_CLAIMED`

---

### M-002: Setup Credentials (Activate on Pre-Provisioned User)

**Owning FEAT:** FEAT-IDEN-002

**Type:** Command (write + validation)

**Purpose:** Activate username, PIN, and passphrase on pre-provisioned (uncredentialed) User

**Required Context:**
- `user_id` (from prior FEAT-IDEN-001 or FEAT-IDEN-004)
- `seat_id` (from session state prepared by prior FEAT)
- `class_id` (from Seat resolution)

**Inputs:**
- `username` (plaintext, must be unique per class)
- `pin` (4-digit numeric, hashed with bcrypt + pepper)
- `passphrase` (plaintext, hashed with bcrypt + pepper)
- `idempotency_key` (replay detection)

**Preconditions:**
- User exists and is uncredentialed: `user_role = 'student'` AND `pin_hash IS NULL` AND `passphrase_hash IS NULL`
- Seat exists and is bound to User: `Seat.user_id = user_id`
- Seat is claimed: `Seat.claimed_at IS NOT NULL`
- Username not already taken in class (check `UNIQUE(class_id, username_lookup_hash)`)
- Session state exists: `onboarding_seat_ref = seat_id`, `onboarding_user_ref = user_id`

**Reads:**
- `User` by `user_id`
- `Seat` by `seat_id`
- Query for existing username in class scope
- Verify user is uncredentialed

**Writes:**
- Hash username: `username_lookup_hash = hash_hmac(username, class_id)`
- Hash username (full): `username_hash = hash_password(username)`
- Hash PIN: `pin_hash = hash_password(pin)`
- Hash passphrase: `passphrase_hash = hash_password(passphrase)`
- Set `User.current_session_started_at = NOW()`
- Set `User.current_session_expires_at = NOW() + session_ttl`
- Set `User.current_session_nonce = generate_nonce()`
- Update `User.last_active_class_id = class_id`

**Postconditions:**
- `User.pin_hash IS NOT NULL`
- `User.passphrase_hash IS NOT NULL`
- `User.username_lookup_hash IS NOT NULL`
- User can now authenticate
- Session is established and valid

**Failure Cases:**
- User already credentialed → `USER_ALREADY_CREDENTIALED`
- Username taken in class → `USERNAME_TAKEN`
- Seat not found or unbound → `SEAT_INVALID`
- Session state missing → `SESSION_STATE_INVALID`
- Database error → `INTERNAL_ERROR` (rollback all writes)

**Atomicity:** Single transaction. On failure, rollback all writes.

**Audit:** Emits `ACT-IDEN-002` with outcome `CREDENTIAL_ACTIVATED`

---

### M-003: Generate Reset Code (Teacher Action)

**Owning FEAT:** FEAT-IDEN-003

**Type:** Command (write + authorization)

**Purpose:** Teacher initiates account recovery by generating single-use reset code

**Required Context:**
- `student_user_id` (target user for recovery)
- `student_seat_id` (seat being recovered)
- `class_id` (from seat resolution)
- `teacher_user_id` (authenticated actor)

**Inputs:**
- `student_seat_id` (identifies the account to recover)
- `idempotency_key` (replay detection)

**Preconditions:**
- Teacher is authenticated and has `user_role = 'admin'`
- Teacher has administrative Seat in same `class_id`: `Seat.role = 'admin'` AND `Seat.user_id = teacher_user_id`
- Student Seat exists and is claimed: `Seat.claimed_at IS NOT NULL`
- Student Seat is bound to User: `Seat.user_id = student_user_id`
- Student User exists with `user_role = 'student'`

**Reads:**
- `Seat` by `student_seat_id`
- `User` (student) by `Seat.user_id`
- `User` (teacher) by `teacher_user_id` to verify admin role
- Verify teacher has admin seat in class

**Writes:**
- Generate 8-character alphanumeric reset code (A-Z, 0-9 only)
- Set `User.reset_code = generated_code` (overwrites any existing code)
- Set `User.reset_code_generated_at = NOW()`
- Set `User.reset_code_expires_at = NOW() + 10 minutes`

**Postconditions:**
- `User.reset_code IS NOT NULL`
- `User.reset_code_expires_at = NOW() + 600 seconds` (exactly)
- Only one active code exists (overwrote any prior code)
- Code displayed to teacher

**Failure Cases:**
- Student Seat not found → `STUDENT_SEAT_NOT_FOUND`
- Seat not claimed → `INVALID_SEAT_STATE`
- Student User not found → `STUDENT_USER_NOT_FOUND`
- Teacher not authorized (no admin seat) → `UNAUTHORIZED` (403)
- Database error → `INTERNAL_ERROR` (rollback)

**Atomicity:** Single transaction. On failure, rollback all writes.

**Audit:** Emits `ACT-IDEN-003` with outcome `RESET_CODE_GENERATED`

**Rate Limiting:** Max 5 code generations per teacher per student per hour

---

### M-004: Clear Credentials for Recovery (Student Action)

**Owning FEAT:** FEAT-IDEN-004

**Type:** Command (write + validation)

**Purpose:** Student submits reset code, validates it, clears old credentials to force credential re-setup

**Required Context:**
- `user_id` (from reset code lookup)
- `seat_id` (from user's seat in active class)
- `class_id` (from seat resolution)

**Inputs:**
- `reset_code` (8-char alphanumeric, student-provided)
- `idempotency_key` (replay detection)

**Preconditions:**
- Reset code exists and is not expired: `User.reset_code = reset_code` AND `NOW() < reset_code_expires_at`
- Reset code has not been used: `User.reset_code IS NOT NULL` (will be cleared on use)
- User exists with `user_role = 'student'`
- At least one claimed Seat bound to User exists

**Reads:**
- `User` by `reset_code` lookup
- Verify `reset_code IS NOT NULL`
- Verify `reset_code_expires_at > NOW()`
- `Seat` by `user_id` (find claimed seat)
- Verify `Seat.claimed_at IS NOT NULL`

**Writes:**
- Set `User.username_lookup_hash = NULL` (invalidate old username)
- Set `User.username_hash = NULL` (invalidate old username)
- Set `User.pin_hash = NULL` (invalidate old PIN)
- Set `User.passphrase_hash = NULL` (invalidate old passphrase)
- Set `User.reset_code = NULL` (single-use invariant)
- Set `User.reset_code_generated_at = NULL`
- Set `User.reset_code_expires_at = NULL`

**Precondition Enforcement:** Seat MUST have `claimed_at IS NOT NULL` before this primitive executes. A NULL `claimed_at` indicates an invalid state; reject with `SEAT_NOT_CLAIMED` rather than silently setting it.

**Postconditions:**
- All four credential hashes are `NULL`
- User is uncredentialed and ready for FEAT-IDEN-002
- Reset code is cleared (cannot be reused)
- Session state prepared: `onboarding_user_ref = user_id`, `onboarding_seat_ref = seat_id`

**Failure Cases:**
- Code not provided or malformed → `INVALID_CODE_FORMAT`
- Code not found in system → `CODE_NOT_FOUND` (generic message: "Invalid or expired recovery code")
- Code expired (TTL exceeded) → `CODE_EXPIRED` (generic message)
- Code already used → `CODE_ALREADY_USED` (generic message)
- No claimed seat found for user → `NO_CLAIMED_SEAT` (generic message)
- Seat exists but `claimed_at IS NULL` → `SEAT_NOT_CLAIMED` (reject; do not mutate claim state)
- Database error → `INTERNAL_ERROR` (rollback)

**Atomicity:** Single transaction. All four credential hashes cleared together. On failure, none cleared.

**Audit:** Emits `ACT-IDEN-004` with outcome `CREDENTIALS_CLEARED_FOR_RECOVERY`

**Rate Limiting:** Max 5 attempts per 15 minutes per IP; lockout after 3 failures (5 min wait)

**Security:** Generic error messages for all failures; do NOT reveal whether user exists

---

### M-005: Bind Authenticated User to New Class Seat

**Owning FEAT:** FEAT-IDEN-005 (TO BE CREATED)

**Type:** Command (write + authorization)

**Purpose:** Authenticated user with existing credentials joins new class period and gets new Seat

**Required Context:**
- `user_id` (authenticated user with credentials)
- `new_class_id` (target class for binding)
- `seat_id` (unclaimed seat in new class)

**Inputs:**
- `join_code` (public alias for class_id)
- `seat_id` or seat lookup credentials (TBD - likely name + dedupe code again, or direct seat selection)
- `idempotency_key` (replay detection)

**Preconditions:**
- User is authenticated and credentialed: `user_role = 'student'` AND `pin_hash IS NOT NULL`
- User does not already have Seat in target class: NOT EXISTS (Seat WHERE user_id = user.id AND class_id = new_class_id)
- Target Seat exists and is unclaimed: `claimed_at IS NULL` AND `user_id IS NULL`
- User already has at least one claimed seat (to verify participation eligibility)

**Reads:**
- `User` by `user_id` (verify credentialed)
- `ClassEconomy` by `join_code` to get `class_id`
- `Seat` by `seat_id` to verify unclaimed
- Check for existing `Seat` for user in class
- (If name matching needed) Query `Seat` by roster fingerprint + dedupe code

**Writes:**
- Create new `Seat` or bind existing unclaimed Seat:
  - Set `Seat.user_id = user_id`
  - Set `Seat.claimed_at = NOW()`
- Set `User.last_active_class_id = new_class_id`
- (Optional) Update `IdentityProfile` if needed for new class context

**Postconditions:**
- User now has claimed Seat in new class
- User can participate in new class economy
- All prior credentials still valid

**Failure Cases:**
- Join code not found → `CLASS_NOT_FOUND`
- Seat not found → `SEAT_NOT_FOUND`
- Seat already claimed → `SEAT_ALREADY_CLAIMED`
- User already in class → `ALREADY_IN_CLASS`
- User not credentialed → `USER_NOT_CREDENTIALED`
- Database error → `INTERNAL_ERROR` (rollback)

**Atomicity:** Single transaction. On failure, rollback.

**Audit:** Emits `ACT-IDEN-005` with outcome `USER_BOUND_TO_NEW_CLASS_SEAT`

**Note:** Specification for this FEAT does not yet exist; must be created in Phase 4.

---

## III.B. Teacher Mutation Primitives (Commands)

### T-001: Teacher Authenticate (TOTP Challenge)

**Owning FEAT:** FEAT-IDEN-101 (TO BE CREATED)

**Type:** Query + validation (read-only, cryptographic verification)

**Purpose:** Verify teacher identity via TOTP 2FA (required for all teacher authentication)

**Required Context:**
- `teacher_user_id` (authenticated via prior login or session)
- `class_id` (optional, if class-scoped authentication)

**Inputs:**
- `totp_code` (6-digit code from authenticator app, time-based)
- `idempotency_key` (not strictly needed for read, but for consistency)

**Preconditions:**
- Teacher User exists with `user_role = 'teacher'`
- Teacher has `totp_secret_encrypted IS NOT NULL`
- TOTP code is fresh (within 30-second window per RFC 6238)

**Reads:**
- `User` by `user_id`
- Decrypt `totp_secret_encrypted` (symmetric key from config)
- Verify TOTP code against decrypted secret with `pyotp.TOTP(secret).verify(code, valid_window=1)`

**Writes:**
- None (pure verification)

**Returns:** `(authenticated: bool, error_code: str | None)`

**Postconditions:**
- No modifications
- If authenticated: teacher can proceed to protected routes
- If not authenticated: return generic error (do not reveal whether secret is set)

**Failure Cases:**
- User not found → `(False, 'INVALID_CREDENTIALS')`
- TOTP secret not enrolled → `(False, 'INVALID_CREDENTIALS')`
- Code invalid or expired → `(False, 'INVALID_CODE')`
- Code format wrong → `(False, 'INVALID_CODE')`

**Security:** Generic error messages; never reveal whether TOTP is enrolled or code is close to valid

**Rate Limiting:** Max 5 failed attempts per teacher per minute; lockout 5 min after 3 failures

---

### T-002: Enroll TOTP Secret (During Teacher Setup)

**Owning FEAT:** FEAT-IDEN-101 (TO BE CREATED)

**Type:** Command (write + validation) — two-step: **Prepare** then **Confirm**

**Purpose:** Activate Time-based One-Time Password (TOTP) 2FA on teacher account during initial setup

**Required Context:**
- `teacher_user_id` (new teacher account, uncredentialed)
- `class_id` (teacher's primary class context)

---

#### T-002a: Prepare TOTP Enrollment

**Inputs:**
- `idempotency_key` (replay detection)

**Preconditions:**
- Teacher User exists with `user_role = 'teacher'`
- Teacher is uncredentialed: `totp_secret_encrypted IS NULL`
- No pending enrollment already active for this user

**Reads:**
- `User` by `user_id`
- Verify no committed TOTP and no unexpired pending enrollment

**Writes:**
- Generate TOTP base32 secret: `pending_secret = pyotp.random_base32()`
- Store short-lived pending enrollment: `User.totp_pending_secret_encrypted = encrypt(pending_secret)`, `User.totp_pending_expires_at = NOW() + 10 minutes`

**Returns:** QR code artifact (data URI) and manual entry secret for display to teacher

**Postconditions:**
- Pending enrollment reference persisted and time-bound
- Teacher can open authenticator app, scan QR, and produce a valid code

**Failure Cases:**
- User not found → `USER_NOT_FOUND`
- TOTP already enrolled → `ALREADY_ENROLLED`
- Encryption failed → `INTERNAL_ERROR`

**Atomicity:** Single transaction. On failure, rollback.

---

#### T-002b: Confirm TOTP Enrollment

**Inputs:**
- `totp_code` (6-digit code from authenticator to verify secret was added)
- `idempotency_key` (replay detection)

**Preconditions:**
- Pending enrollment exists: `totp_pending_secret_encrypted IS NOT NULL` AND `totp_pending_expires_at > NOW()`
- `totp_secret_encrypted IS NULL` (not yet committed)
- Provided `totp_code` is valid against the pending secret

**Reads:**
- `User` by `user_id`
- Decrypt `totp_pending_secret_encrypted` → `pending_secret`
- Verify TOTP code against `pending_secret`

**Writes:**
- Encrypt and commit: `User.totp_secret_encrypted = encrypt(normalize_totp_for_storage(pending_secret))`
- Clear pending enrollment: `User.totp_pending_secret_encrypted = NULL`, `User.totp_pending_expires_at = NULL`

**Postconditions:**
- `User.totp_secret_encrypted IS NOT NULL`
- Pending enrollment fields cleared
- Teacher can now authenticate using T-001 (TOTP challenge)
- Recovery codes generated (backup in case of lost authenticator)

**Failure Cases:**
- User not found → `USER_NOT_FOUND`
- User already has TOTP enrolled → `ALREADY_ENROLLED`
- No pending enrollment or enrollment expired → `NO_PENDING_ENROLLMENT`
- TOTP code invalid/expired → `INVALID_CODE`
- Encryption failed → `INTERNAL_ERROR`

**Atomicity:** Single transaction. On failure, rollback.

**Audit:** Emits audit event with outcome `TOTP_ENROLLED`

**Backup Codes:** After successful confirmation, generate 10 backup codes and display to teacher (one-time only)

---

### T-003: Enroll Passkey Credential (Optional, After TOTP)

**Owning FEAT:** FEAT-IDEN-102 (TO BE CREATED)

**Type:** Command (write + WebAuthn registration)

**Purpose:** Optionally add WebAuthn passkey (fingerprint, security key, etc.) as backup to TOTP

**Required Context:**
- `teacher_user_id` (teacher with TOTP already enrolled)
- `class_id` (teacher's class)

**Inputs:**
- `credential_response` (WebAuthn registration response from browser)
- `authenticator_name` (user-friendly name, e.g., "Face ID", "YubiKey5Ci")
- `idempotency_key` (replay detection)

**Preconditions:**
- Teacher User exists with `user_role = 'teacher'`
- TOTP already enrolled: `totp_secret_encrypted IS NOT NULL`
- WebAuthn credential response is valid and verified server-side
- Challenge from challenge_store matches (WebAuthn anti-CSRF)

**Reads:**
- `User` by `user_id`
- Verify TOTP is enrolled
- Challenge from `challenge_store` (session or database)

**Writes:**
- Create `PasskeyCredential` row:
  - `user_id = teacher_user_id`
  - `credential_id = extracted_from_response`
  - `authenticator_name = user_provided_name`
  - `created_at = NOW()`

**Postconditions:**
- `PasskeyCredential` record created
- Teacher can now use passkey for optional additional auth factor

**Failure Cases:**
- User not found → `USER_NOT_FOUND`
- TOTP not enrolled → `TOTP_REQUIRED_FIRST`
- WebAuthn response invalid → `INVALID_CREDENTIAL`
- Challenge mismatch → `INVALID_CHALLENGE`
- Database error → `INTERNAL_ERROR`

**Atomicity:** Single transaction. On failure, rollback.

**Audit:** Emits `PASSKEY_ENROLLED` with authenticator_name

---

### T-004: Initiate Teacher Recovery (Create RecoveryRequest)

**Owning FEAT:** FEAT-IDEN-103 (TO BE CREATED)

**Type:** Command (write + authorization)

**Purpose:** Teacher initiates account recovery via student-verified codes (5-day window)

**Required Context:**
- `teacher_user_id` (locked-out teacher account)
- `class_id` (teacher's class)

**Inputs:**
- `idempotency_key` (replay detection)

**Preconditions:**
- Teacher User exists with `user_role = 'teacher'`
- Teacher is credentialed (has TOTP secret set)
- No active recovery request exists for this teacher (per 5-day TTL)
- Teacher has at least one admin Seat in target class

**Reads:**
- `User` by `user_id`
- `Seat` query to verify teacher is admin in class
- Check for existing active `RecoveryRequest` (not yet expired)

**Writes:**
- Create `RecoveryRequest` row:
  - `user_id = teacher_user_id`
  - `class_id = class_id` (class context for this recovery)
  - `status = 'pending'`
  - `created_at = NOW()`
  - `expires_at = NOW() + 5 days`
  - `completed_at = NULL`
  - `partial_codes = []` (JSON array)
  - `eligible_seat_ids = [list of claimed student seat IDs in class_id at creation time]` (immutable snapshot; stored as JSON array)
  - `eligible_seat_count = COUNT(claimed student seats in class_id)` (integer; guard against empty class)

**Precondition Enforcement:** Reject with `NO_ELIGIBLE_STUDENTS` if `eligible_seat_count = 0`.

**Postconditions:**
- `RecoveryRequest` exists in `pending` state
- Recovery window open for 5 days
- Teacher notifies students to provide codes

**Failure Cases:**
- User not found → `USER_NOT_FOUND`
- Active recovery already exists → `RECOVERY_IN_PROGRESS`
- User is not credentialed → `USER_NOT_CREDENTIALED`
- Teacher not admin in class → `UNAUTHORIZED`
- No eligible students (claimed seats) in class → `NO_ELIGIBLE_STUDENTS`
- Database error → `INTERNAL_ERROR`

**Atomicity:** Single transaction. On failure, rollback.

**Audit:** Emits `RECOVERY_INITIATED` with recovery_request_id

**Note:** Teacher does not provide recovery codes; students do (T-005)

---

### T-005: Generate Student Recovery Code (Student Action During Teacher Recovery)

**Owning FEAT:** FEAT-IDEN-104 (TO BE CREATED)

**Type:** Command (write + authorization)

**Purpose:** Student generates and provides recovery code to help teacher reclaim account

**Required Context:**
- `student_seat_id` (student in teacher's class)
- `teacher_recovery_request_id` (active recovery request)
- `class_id` (shared class context)

**Inputs:**
- `recovery_request_id` (teacher's active recovery request ID)
- `idempotency_key` (replay detection)

**Preconditions:**
- Student Seat exists and is claimed: `claimed_at IS NOT NULL`
- Student is in same class as teacher recovery request
- Active `RecoveryRequest` exists: `status = 'pending'` AND `NOW() < expires_at`
- Student has not already provided code for this recovery (idempotency)

**Reads:**
- `RecoveryRequest` by `recovery_request_id`
- `Seat` by `student_seat_id`
- Verify both are in same `class_id`
- Check existing `StudentRecoveryCode` for this recovery + student

**Writes:**
- Create `StudentRecoveryCode` row:
  - `recovery_request_id = teacher_recovery_request_id`
  - `seat_id = student_seat_id`
  - `class_id = class_id`
  - `code_hash = hash_password(generated_code)` (bcrypt hashed)
  - `verified_at = NULL` (not yet verified by student)
  - `notified_at = NOW()`
  - `dismissed = FALSE`

**Postconditions:**
- Code generated and hashed (plaintext never stored)
- Code displayed to student once (student must save/share)
- Recovery request notified of new code

**Failure Cases:**
- Recovery request not found → `RECOVERY_REQUEST_NOT_FOUND`
- Recovery expired → `RECOVERY_EXPIRED`
- Student seat not found → `SEAT_NOT_FOUND`
- Wrong class context → `CONTEXT_MISMATCH`
- Database error → `INTERNAL_ERROR`

**Atomicity:** Single transaction. On failure, rollback.

**Audit:** Emits `RECOVERY_CODE_GENERATED` with recovery_request_id, student_seat_id

**Code Format:** 8-digit alphanumeric (A-Z, 0-9), unique per recovery request per student

---

### T-006: Validate Teacher Recovery Codes (Submit All Codes)

**Owning FEAT:** FEAT-IDEN-105 (TO BE CREATED)

**Type:** Command (write + validation)

**Purpose:** Teacher submits all collected student recovery codes to validate and restore access

**Required Context:**
- `teacher_user_id` (account being recovered)
- `recovery_request_id` (active recovery)
- `class_id` (class context)

**Inputs:**
- `recovery_request_id`
- `recovery_codes` (list of codes collected from all students, plaintext)
- `idempotency_key` (replay detection)

**Preconditions:**
- Active `RecoveryRequest` exists: `status = 'pending'` AND `NOW() < expires_at`
- `RecoveryRequest.eligible_seat_ids` is non-empty (guaranteed at creation by T-004)
- Exactly one `StudentRecoveryCode` row exists per seat in `eligible_seat_ids` (one code per snapshotted student)
- Each code hashes correctly against stored `code_hash`
- Submitted code count equals `RecoveryRequest.eligible_seat_count` (all-or-nothing)

**Reads:**
- `RecoveryRequest` by `recovery_request_id`
- Read `RecoveryRequest.eligible_seat_ids` (immutable snapshot from T-004)
- All `StudentRecoveryCode` rows for recovery request
- Verify submitted code set covers every seat in `eligible_seat_ids`
- Verify each code against hashed values

**Writes:**
- For each code: verify `code_hash` matches via `verify_password(plaintext_code, stored_hash)`
- Update `StudentRecoveryCode.verified_at = NOW()` for each matching code
- If all codes validate:
  - Update `RecoveryRequest.status = 'verified'`
  - Update `RecoveryRequest.completed_at = NOW()`
  - Prepare session for credential re-setup (M-002)

**Postconditions:**
- Recovery request marked verified
- Teacher can proceed to credential re-enrollment (new TOTP, new passkey, etc.)
- All student codes marked verified

**Failure Cases:**
- Recovery request not found → `RECOVERY_REQUEST_NOT_FOUND`
- Recovery expired → `RECOVERY_EXPIRED`
- Code count mismatch (not all students provided) → `INCOMPLETE_CODES`
- Code validation fails (hash mismatch) → `INVALID_CODE` (generic)
- Already completed → `ALREADY_VERIFIED`
- Database error → `INTERNAL_ERROR`

**Atomicity:** All-or-nothing: if any code invalid, no writes proceed. On success, all codes verified at once.

**Audit:** Emits `RECOVERY_VERIFIED` with recovery_request_id

**Security:** Generic error messages; never reveal which students did/didn't provide valid codes

---

### T-007: Update TOTP Secret (Credential Change)

**Owning FEAT:** FEAT-IDEN-106 (TO BE CREATED)

**Type:** Command (write + validation)

**Purpose:** Teacher changes TOTP secret (e.g., new authenticator, suspected compromise)

**Required Context:**
- `teacher_user_id` (authenticated teacher)
- `class_id` (teacher's class)

**Type:** Command (write + validation) — two-step: **Prepare** then **Confirm**

---

#### T-007a: Prepare TOTP Rotation

**Inputs:**
- `idempotency_key` (replay detection)

**Preconditions:**
- Teacher is authenticated (already passed TOTP challenge)
- Teacher User exists with `user_role = 'teacher'`
- Existing TOTP secret is set: `totp_secret_encrypted IS NOT NULL`
- No unexpired pending rotation already active

**Reads:**
- `User` by `user_id`
- Verify existing TOTP is set
- Verify no unexpired `totp_pending_secret_encrypted`

**Writes:**
- Generate new TOTP secret: `new_secret = pyotp.random_base32()`
- Store short-lived pending rotation: `User.totp_pending_secret_encrypted = encrypt(new_secret)`, `User.totp_pending_expires_at = NOW() + 10 minutes`

**Returns:** QR code artifact (data URI) and manual entry secret for display to teacher

**Failure Cases:**
- User not found → `USER_NOT_FOUND`
- TOTP not enrolled → `TOTP_NOT_ENROLLED`
- Encryption failed → `INTERNAL_ERROR`

**Atomicity:** Single transaction. On failure, rollback (existing secret unchanged).

---

#### T-007b: Confirm TOTP Rotation

**Inputs:**
- `new_totp_code` (6-digit code from new authenticator)
- `idempotency_key` (replay detection)

**Preconditions:**
- Pending rotation exists: `totp_pending_secret_encrypted IS NOT NULL` AND `totp_pending_expires_at > NOW()`
- Provided code is valid against the pending secret

**Reads:**
- `User` by `user_id`
- Decrypt `totp_pending_secret_encrypted` → `new_secret`
- Verify new code against `new_secret`

**Writes:**
- Encrypt and commit: `User.totp_secret_encrypted = encrypt(normalize_totp_for_storage(new_secret))`
- Clear pending rotation: `User.totp_pending_secret_encrypted = NULL`, `User.totp_pending_expires_at = NULL`
- Invalidate all passkey credentials (optional: require re-enrollment after TOTP change)

**Postconditions:**
- Old TOTP secret replaced with new one
- Pending rotation fields cleared
- Old authenticator apps will no longer work
- New backup codes generated and displayed

**Failure Cases:**
- User not found → `USER_NOT_FOUND`
- TOTP not enrolled → `TOTP_NOT_ENROLLED`
- No pending rotation or rotation expired → `NO_PENDING_ROTATION`
- New code invalid → `INVALID_CODE`
- Encryption failed → `INTERNAL_ERROR`

**Atomicity:** Single transaction. On failure, rollback (old secret unchanged).

**Audit:** Emits `TOTP_UPDATED` with count of passkeys invalidated

**Backup Codes:** Generate and display 10 new backup codes (old ones become invalid)

---

### T-008: Revoke Passkey Credential (Remove Optional Auth)

**Owning FEAT:** FEAT-IDEN-107 (TO BE CREATED)

**Type:** Command (write + authorization)

**Purpose:** Teacher removes a passkey credential (security key, face ID, etc.)

**Required Context:**
- `teacher_user_id` (authenticated teacher)
- `passkey_credential_id` (credential to revoke)

**Inputs:**
- `passkey_credential_id`
- `idempotency_key` (replay detection)

**Preconditions:**
- Teacher is authenticated (TOTP verified)
- Passkey credential exists and belongs to teacher
- Teacher has at least one passkey enrolled (don't remove last one without backup)

**Reads:**
- `User` by `user_id`
- `PasskeyCredential` by `credential_id`
- Verify `user_id` matches

**Writes:**
- Delete `PasskeyCredential` row (hard delete)

**Postconditions:**
- Credential no longer usable for authentication
- Teacher reverts to TOTP-only 2FA

**Failure Cases:**
- Passkey not found → `CREDENTIAL_NOT_FOUND`
- Wrong owner → `UNAUTHORIZED`
- Cannot delete (last credential) → `LAST_CREDENTIAL`
- Database error → `INTERNAL_ERROR`

**Atomicity:** Single transaction. On failure, rollback.

**Audit:** Emits `PASSKEY_REVOKED` with authenticator_name

---

## IV. Read Primitives (Queries)

### R-001: Resolve Canonical Context

**Type:** Query (pure read)

**Purpose:** Resolve authenticated User to their current Seat, Class, and role in one authoritative call

**Inputs:**
- `user_id` (from session)
- `class_id` or `join_code` (optional, if class-scoped; if absent, uses last active class)

**Reads:**
- `User` by `user_id`
- `Seat` by `(user_id, class_id)` or by `(user_id, last_active_class_id)` if class not specified
- `ClassEconomy` by `class_id`
- `IdentityProfile` by `seat_id` (for display name)

**Returns:** `CanonicalContext` frozen dataclass:
```python
{
    'user_id': user.id,
    'seat_id': seat.id,
    'class_id': class.id,
    'actor_role': seat.role,  # 'student' or 'admin'
}
```

**Preconditions:**
- User exists
- If class_id specified, Seat must exist in that class
- If class_id not specified, User must have `last_active_class_id` set

**Postconditions:**
- Context is frozen (immutable)
- Cannot access `join_code`, `teacher_id`, `student_id`, or `block` on context (raises `AttributeError`)

**Failure Cases:**
- User not found → return `None` (not authenticated)
- Seat not found in class → raise `ContextResolutionError`
- Multiple seats in class (should not happen) → raise `ContextResolutionError`

**Authority:** Per DOM-IDEN-006 (Canonical Context Resolution)

---

### R-002: Get User by ID

**Type:** Query (pure read)

**Purpose:** Fetch User record (identity principal)

**Inputs:**
- `user_id`

**Reads:**
- `User` by `user_id`

**Returns:** User object with all fields (credentials hashed, not decrypted)

**Preconditions:**
- User exists

**Postconditions:**
- No modifications

**Failure Cases:**
- User not found → return `None`

---

### R-003: Get Seat by ID

**Type:** Query (pure read)

**Purpose:** Fetch Seat record (class-local actor)

**Inputs:**
- `seat_id`

**Reads:**
- `Seat` by `seat_id`

**Returns:** Seat object

**Preconditions:**
- Seat exists

**Postconditions:**
- No modifications

**Failure Cases:**
- Seat not found → return `None`

---

### R-004: Get User's Seat in Class

**Type:** Query (pure read)

**Purpose:** Find the Seat binding a User to a specific Class

**Inputs:**
- `user_id`
- `class_id`

**Reads:**
- `Seat` by `(user_id, class_id)`

**Returns:** Seat object or `None`

**Preconditions:**
- User and Class exist

**Postconditions:**
- No modifications

**Failure Cases:**
- No seat found → return `None`
- Multiple seats (data corruption) → raise error

---

### R-005: Get IdentityProfile for Seat

**Type:** Query (pure read)

**Purpose:** Fetch display-only identity profile (encrypted name, etc.)

**Inputs:**
- `seat_id`

**Reads:**
- `IdentityProfile` by `seat_id`

**Returns:** IdentityProfile with encrypted first_name (decrypt on display)

**Preconditions:**
- Seat exists
- IdentityProfile exists for seat

**Postconditions:**
- No modifications

**Failure Cases:**
- IdentityProfile not found → return `None`

---

### R-006: Check if Seat is Claimed

**Type:** Query (pure read)

**Purpose:** Boolean check: is this Seat already bound to a User?

**Inputs:**
- `seat_id`

**Reads:**
- `Seat` by `seat_id`

**Returns:** Boolean (true if `claimed_at IS NOT NULL`)

**Preconditions:**
- Seat exists

**Postconditions:**
- No modifications

**Failure Cases:**
- Seat not found → return `False` or raise error

---

### R-007: Validate Reset Code (Time, Existence, Usage)

**Type:** Query (pure read)

**Purpose:** Check if reset code is valid (exists, not expired, not already used)

**Inputs:**
- `reset_code` (plaintext)

**Reads:**
- `User` by `reset_code` lookup
- Verify `reset_code IS NOT NULL`
- Verify `reset_code_expires_at > NOW()`

**Returns:** `(is_valid: bool, user_id: int | None, error_code: str | None)`

**Preconditions:**
- Code string provided

**Postconditions:**
- No modifications

**Failure Cases:**
- Code not found → `(False, None, 'CODE_NOT_FOUND')`
- Code expired → `(False, None, 'CODE_EXPIRED')`
- Code already used (would be NULL) → `(False, None, 'CODE_ALREADY_USED')`

**Security:** Never reveal in error message whether code was found vs. expired vs. used

---

### R-008: Check Teacher Authorization (Admin in Class)

**Type:** Query (pure read)

**Purpose:** Verify teacher has administrative authority in a specific class

**Inputs:**
- `teacher_user_id`
- `class_id`

**Reads:**
- `Seat` where `user_id = teacher_user_id` AND `class_id = class_id` AND `role = 'admin'`

**Returns:** Boolean (true if matching Seat exists)

**Preconditions:**
- Teacher User exists
- Class exists

**Postconditions:**
- No modifications

**Failure Cases:**
- No matching Seat → return `False`

---

### R-009: Authenticate User (Verify Credentials)

**Type:** Query (pure read + cryptographic validation)

**Purpose:** Verify username/PIN/passphrase match stored hashes

**Inputs:**
- `username` (plaintext)
- `pin` (plaintext, 4 digits)
- `passphrase` (plaintext)
- `class_id` (for username lookup scope)

**Reads:**
- `User` by `username_lookup_hash = hash_hmac(username, class_id)`
- Verify `pin_hash` matches provided PIN via `verify_password(pin, stored_hash)`
- Verify `passphrase_hash` matches provided passphrase via `verify_password(passphrase, stored_hash)`

**Returns:** `(authenticated: bool, user_id: int | None)`

**Preconditions:**
- Username, PIN, and passphrase provided
- Class exists (for username scope)

**Postconditions:**
- No modifications

**Failure Cases:**
- User not found → `(False, None)`
- PIN mismatch → `(False, None)`
- Passphrase mismatch → `(False, None)`

**Security:** Do NOT reveal which field (username, PIN, passphrase) was wrong; generic "Invalid credentials" message

---

### R-010: Get User's Active Reset Code (if Exists)

**Type:** Query (pure read)

**Purpose:** Return a student's active (non-expired) reset code to an authorized teacher in the same class

**Inputs:**
- `student_user_id`
- `requesting_teacher_id`
- `class_id`

**Reads:**
- `User` (teacher) by `requesting_teacher_id` — verify `user_role = 'teacher'`
- `Seat` by `(requesting_teacher_id, class_id)` — verify teacher holds an administrative seat in the class
- `User` (student) by `student_user_id`
- Verify student has a claimed seat in `class_id`
- Check `reset_code IS NOT NULL` AND `reset_code_expires_at > NOW()`

**Returns:** `reset_code` (plaintext string) or `None`

**Preconditions:**
- Requesting teacher exists with `user_role = 'teacher'`
- Teacher holds an administrative seat in `class_id`
- Student exists with a claimed seat in the same `class_id`

**Postconditions:**
- No modifications

**Failure Cases:**
- Teacher not found or not a teacher → return `None`
- Teacher does not hold an administrative seat in `class_id` → return `None` (or raise `UNAUTHORIZED`)
- Student not found or not in class → return `None`
- No active code → return `None`

**Note:** Used by teacher to display code to student; only accessible to teacher in recovery flow

---

### R-011: Check if Username is Taken (in Class Scope)

**Type:** Query (pure read)

**Purpose:** Verify username uniqueness within a class

**Inputs:**
- `username` (plaintext)
- `class_id`

**Reads:**
- Query for `User` where `username_lookup_hash = hash_hmac(username, class_id)`

**Returns:** Boolean (true if username already exists)

**Preconditions:**
- Username provided
- Class exists

**Postconditions:**
- No modifications

**Failure Cases:**
- None (always returns boolean)

---

### R-012: Get Seat by Roster Fingerprint + Dedupe Code

**Type:** Query (pure read)

**Purpose:** Look up unclaimed Seat for identity matching (used in claim flow)

**Inputs:**
- `class_id`
- `roster_fingerprint` (computed from first_name + last_initial per DOM-IDEN-002 §VIII.II)
- `dedupe_code` (8-char alphanumeric, student-provided)

**Reads:**
- `Seat` by `(class_id, roster_fingerprint, dedupe_code)`
- Verify `claimed_at IS NULL` (unclaimed)

**Returns:** Seat object or `None`

**Preconditions:**
- Class exists
- Fingerprint and dedupe code provided

**Postconditions:**
- No modifications

**Failure Cases:**
- Seat not found → return `None`
- Seat already claimed → return `None` (or raise error)

---

## IV.B. Teacher Read Primitives (Queries)

### T-R-001: Get Teacher User

**Type:** Query (pure read)

**Purpose:** Fetch teacher User record with TOTP credentials

**Inputs:**
- `user_id`

**Reads:**
- `User` by `user_id`
- Verify `user_role = 'teacher'`

**Returns:** User object with `totp_secret_encrypted` (encrypted, not decrypted)

**Preconditions:**
- User exists and is a teacher

**Postconditions:**
- No modifications

**Failure Cases:**
- User not found → return `None`
- User is not teacher → raise error or return `None`

---

### T-R-002: Get Teacher Seat in Class

**Type:** Query (pure read)

**Purpose:** Find admin Seat binding a teacher to a specific Class

**Inputs:**
- `teacher_user_id`
- `class_id`

**Reads:**
- `Seat` by `(user_id = teacher_user_id, class_id, role = 'admin')`

**Returns:** Seat object or `None`

**Preconditions:**
- Teacher User and Class exist

**Postconditions:**
- No modifications

**Failure Cases:**
- No matching Seat → return `None`
- Multiple seats (data corruption) → raise error

---

### T-R-003: Validate TOTP Secret (Check Encryption)

**Type:** Query (pure read)

**Purpose:** Verify teacher has TOTP secret enrolled (for authorization checks)

**Inputs:**
- `user_id`

**Reads:**
- `User` by `user_id`
- Check `totp_secret_encrypted IS NOT NULL`

**Returns:** Boolean (true if TOTP enrolled)

**Preconditions:**
- User exists

**Postconditions:**
- No modifications

**Failure Cases:**
- User not found → return `False`

---

### T-R-004: Validate Passkey Enrollment (Check Count)

**Type:** Query (pure read)

**Purpose:** Check if teacher has passkey credentials enrolled (optional secondary factor)

**Inputs:**
- `user_id`

**Reads:**
- Count `PasskeyCredential` rows where `user_id = user_id`

**Returns:** Integer count (0 or more)

**Preconditions:**
- User exists

**Postconditions:**
- No modifications

**Failure Cases:**
- User not found → return `None`

---

### T-R-005: Get Active Recovery Request

**Type:** Query (pure read)

**Purpose:** Check if teacher has an active (non-expired) recovery request

**Inputs:**
- `user_id`

**Reads:**
- `RecoveryRequest` by `user_id`
- Filter: `status = 'pending'` AND `NOW() < expires_at`

**Returns:** RecoveryRequest object or `None`

**Preconditions:**
- User exists

**Postconditions:**
- No modifications

**Failure Cases:**
- No active recovery → return `None`
- User not found → return `None`

---

### T-R-006: Get Student Recovery Codes (For Active Recovery)

**Type:** Query (pure read)

**Purpose:** Fetch all student recovery codes collected for a teacher's active recovery

**Inputs:**
- `recovery_request_id`

**Reads:**
- `StudentRecoveryCode` by `recovery_request_id`
- Ordered by `created_at`

**Returns:** List of StudentRecoveryCode objects (code_hash only, not plaintext)

**Preconditions:**
- Recovery request exists

**Postconditions:**
- No modifications

**Failure Cases:**
- Recovery request not found → return empty list or `None`

---

### T-R-007: Validate Recovery Code Submission (Check All Codes)

**Type:** Query (pure read)

**Purpose:** Verify all required student codes are present and valid for recovery completion

**Inputs:**
- `recovery_request_id`
- `all_submitted_codes` (list of plaintext codes teacher collected)

**Reads:**
- `RecoveryRequest` by `recovery_request_id`
- All `StudentRecoveryCode` rows for recovery request
- For each code: verify plaintext against stored `code_hash`

**Returns:** `(all_valid: bool, valid_count: int, required_count: int, error_code: str | None)`

**Preconditions:**
- Recovery request exists
- Codes provided

**Postconditions:**
- No modifications

**Failure Cases:**
- Recovery request not found → `(False, 0, 0, 'RECOVERY_NOT_FOUND')`
- Code count mismatch → `(False, valid_count, required_count, 'INCOMPLETE')`
- Code validation fails → `(False, valid_count, required_count, 'INVALID_CODE')`

**Security:** Return counts but not which specific codes are invalid

---

## V. Summary by Operation Type

### Student Mutations (Atomic, Audited, Logged)
- M-001: Claim Seat (FEAT-IDEN-001)
- M-002: Setup Credentials (FEAT-IDEN-002)
- M-003: Generate Reset Code (FEAT-IDEN-003)
- M-004: Clear Credentials (FEAT-IDEN-004)
- M-005: Bind New Class Seat (FEAT-IDEN-005 - TBD)

### Teacher Mutations (Atomic, Audited, Logged)
- T-001: Teacher Authenticate (FEAT-IDEN-101 - TBD)
- T-002: Enroll TOTP Secret (FEAT-IDEN-101 - TBD)
- T-003: Enroll Passkey Credential (FEAT-IDEN-102 - TBD)
- T-004: Initiate Teacher Recovery (FEAT-IDEN-103 - TBD)
- T-005: Generate Student Recovery Code (FEAT-IDEN-104 - TBD)
- T-006: Validate Teacher Recovery Codes (FEAT-IDEN-105 - TBD)
- T-007: Update TOTP Secret (FEAT-IDEN-106 - TBD)
- T-008: Revoke Passkey Credential (FEAT-IDEN-107 - TBD)

### Generic Reads (Pure, No Side Effects)
- R-001: Resolve Canonical Context
- R-002–012: Various identity lookups and validations (student-focused)

### Teacher Reads (Pure, No Side Effects)
- T-R-001: Get Teacher User
- T-R-002: Get Teacher Seat in Class
- T-R-003: Validate TOTP Secret
- T-R-004: Validate Passkey Enrollment
- T-R-005: Get Active Recovery Request
- T-R-006: Get Student Recovery Codes
- T-R-007: Validate Recovery Code Submission

---

## VI. Cross-Domain Reads (Identity Domain Consumes)

The identity domain may reference but does not own:

- **Class Configuration:** `ClassEconomy` for `class_id`, `join_code`, economy policy
- **Temporal Resolver:** For NOW(), time comparisons, session TTL
- **Ledger Domain:** Will read `Seat` references in transaction/attendance records (identity does not own ledger)

---

## VII. Amendment

Revisions to this document must:

1. Increment version number
2. Update effective date
3. Maintain consistency with DOM-IDEN-001, DOM-IDEN-002, DOM-IDEN-003, DOM-IDEN-005
4. Document any new primitives with full contract details
5. Ensure all FEATs reference correct primitives

**Version History:**
- **v1.0 — 2026-08-09:** Initial creation as Phase 3 deliverable (student primitives only)
- **v2.0 — 2026-08-09:** Expansion to include teacher identity primitives (T-001 through T-008, T-R-001 through T-R-007) per unified domain model (DOM-IDEN covers both student and teacher)
