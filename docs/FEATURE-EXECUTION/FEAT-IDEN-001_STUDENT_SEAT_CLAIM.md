# FEAT-IDEN-001: Student Seat Claim

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-IDEN-001 | 1.0 | 2026-04-23 | N/A | Normative |

---

## I. Purpose

This FEAT orchestrates the binding of a Global User to a Class-Local Seat. It is the primary entry point for a student to join a class, either as a new user or an existing user joining a new class.

---

## II. Execution Context

### 1. Required Inputs
* `join_code`: Valid join code for the target class.
* `credentials`:
    * `first_initial`
    * `last_name` (Fuzzy matched)
    * `dob_sum` (Hashed)
* `idempotency_key`: Client-provided unique request ID.
* `existing_user_id`: (Optional) If the student is already logged in and adding a second class.

### 2. Resolved Context (MANDATORY)
The FEAT MUST resolve the following before mutation:
* `class_id`: Resolved via `join_code`.
* `roster_seat_id`: The unclaimed seat in the teacher's roster matching the credentials.

---

## III. Orchestration Logic

### 1. Verification Phase (Read-Only)
1. **Resolve Class**: Look up `class_id` from `join_code`.
2. **Resolve Roster Seat**: Query `DOM-IDEN` (Roster) for an unclaimed seat matching the credential hashes.
    * **Failure**: If no seat matches, abort with `INVALID_CREDENTIALS`.
3. **Identity Resolution (Controlled Global)**:
    * **Objective**: Find a `User` record that belongs to this human while preventing accidental binding to a different person with similar initials/DOB.
    * **Lookup**: Search for an existing `User` matching the `identity_hash` (First Initial + DOB Sum).
    * **Validation**: If an `existing_user_id` was provided in the request (e.g., they are logged in), it MUST match the found user.
    * **Conflict Check**: If the found `User` is already bound to a different `seat_id` in the SAME `class_id`, abort with `ALREADY_CLAIMED`.

### 2. Mutation Phase (Atomic Transaction)
1. **User Provisioning**:
    * If `User` found: Use `user_id`.
    * If `User` not found: Create new `User` record in `DOM-IDEN`.
2. **Seat Binding**:
    * Create Authoritative `Seat`: Link `user_id` to `class_id` and the `roster_seat_id`.
3. **Roster Finalization (PII Scrubbing)**:
    * Update Roster Seat: Set `is_claimed = True`, `claimed_at = NOW`, `student_id = user_id`.
    * **Explicit Scrub**: MUST zero out `last_name_hash_part` and `dob_sum_hash` to prevent future collision or recovery leaks.
4. **Membership Initialization**:
    * Call `DOM-CLASS` to record `ClassMembership`.
5. **Context Restoration**:
    * Set `User.last_active_seat_id` to the newly bound `seat_id`.
6. **Audit Trace**:
    * Call `DOM-OPS` to record the `ACT-IDEN-001` event with `correlation_id` linked to the `roster_seat_id`.

---

## IV. Invariants & Constraints

1. **Atomic Binding**: The link between `User`, `Seat`, and `Class` must be created within the same transaction.
2. **PII Scrubbing**: Once a seat is claimed, the transient credential hashes (DOB Sum, Last Name Part) MUST be zeroed out in the roster record to prevent future collisions.
3. **Deduplication**: A `user_id` cannot be bound to two seats in the same `class_id`.

---

## V. Idempotency

* **Mechanism**: The combination of `user_id` (or identity hash) and `class_id` acts as a natural idempotency lock.
* **Behavior**: If a retry occurs with the same credentials for a seat already claimed by that user, the FEAT SHOULD return the existing `seat_id` with a `SUCCESS` status rather than failing.

---

## VI. Audit Requirements

The `DOM-OPS` audit log MUST contain:
* `user_id`
* `seat_id`
* `class_id`
* `roster_seat_id`
* `idempotency_key`
* `outcome`: (NEW_USER_CLAIMED | EXISTING_USER_LINKED | FAILED)

---

## VII. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-IDEN-001_IDENTITY_CLASS_BINDING_DOMAIN.md`
