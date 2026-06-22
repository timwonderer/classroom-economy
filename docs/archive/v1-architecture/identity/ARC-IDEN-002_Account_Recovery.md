# ARC-IDEN-002: Account Recovery & Reclaim Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-IDEN-002     | 1.1     | 2026-03-08     | 1.0        | Normative       |

> [!CAUTION]
> **SUPERSEDED.** This document describes the v1 account recovery model.
> **Critical conflict:** Step 3 requires Date of Birth re-entry, which is explicitly
> prohibited in the v2 identity model. No DOB is stored or used in any form for
> either students or teachers in v2.
> For the v2 target model, see:
> - `docs/DOMAIN/DOM-IDEN-002_STUDENT_ACCOUNT_RECOVERY.md`
> - `docs/DOMAIN/DOM-IDEN-004_TEACHER_ACCOUNT_RECOVERY.md`
> This document is retained for historical reference only. Do not implement from it.

## I. Purpose

This document defines the architecture, constraints, and invariants for the Account Recovery & Reclaim feature.

The goal is to allow students to safely recover access to their existing classroom economy account without:
- Deleting student records
- Recreating accounts
- Manually transferring balances
- Modifying historical transactions
- Altering economic history

This feature must preserve all existing economic data and adhere strictly to ledger immutability principles.

## II. Scope
Applies to student credential recovery and identity management within a specific class economy boundary (`join_code`).

## III. Authority Level
Normative (ARC Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Core Invariant (Non-Negotiable)

Account recovery must never modify, delete, merge, or rewrite historical economic records.

Specifically:
- No transaction records may be altered.
- No balances may be edited manually.
- No items, insurance policies, or ownership records may be recreated.
- No historical logs may be rewritten.
- No migration files may be modified.

Account recovery is an identity rebinding operation only.

## VI. Conceptual Model

Recovery is not a password reset. Recovery is the process of re-binding a human student to an existing participant record within a specific `join_code` economy.

The economic record remains unchanged. Only credential access is restored. There is a single recovery flow. All resets are teacher-initiated and time-bounded.

## VII. Data Model Changes

### Student Table Tracking

The following columns exist on the student table to manage recovery:
- `reset_code` (string, nullable)
- `reset_code_expires_at` (datetime, nullable)
- `recovery_status` (string/enum):
  - `active`
  - `to_be_claimed`

### Constraints:
- Only one active `reset_code` per student.
- `reset_code` must be unique within `join_code` scope.
- `reset_code` must be one-time use.
- `reset_code` must expire (hard TTL: 10 minutes).
- `reset_code` must be cleared upon successful claim or expiration.

## VIII. Single Recovery Flow

### Step 1 — Teacher Initiates Reset
Teacher clicks "Reset Student Account" in Student Details.
System must:
- Set student `recovery_status` → `to_be_claimed`
- Invalidate any existing `reset_code`
- Generate new 8-character mixed alphanumeric `reset_code`
- Set `reset_code_expires_at` = now + 10 minutes
- Log reset event

Teacher provides `reset_code` to student immediately (in real-time).

### Step 2 — Student Enters Join Code + Reset Code
Student navigates to Log in page and clicks on "I can't log into my account".
Student submits:
- `join_code`
- `reset_code`

Backend must validate:
- `reset_code` exists
- `reset_code` unused
- `reset_code` unexpired
- `student.recovery_status` == `to_be_claimed`
- `join_code` matches the student record

If validation fails:
- Show generic failure message
- Do not reveal student identity
- Do not change economic or credential state

### Step 3 — Identity Re-Registration
If `reset_code` validation succeeds:
Student must re-enter:
- First name
- Full last name
- Date of birth

Rules:
- These fields replace existing identity metadata on the same student row.
- `student_id` must remain unchanged.
- No new student record may be created.
- Operation must be atomic.

### Step 4 — Credential Re-Establishment
Student proceeds through normal credential setup flow:
- Username
- PIN
- Passphrase

Rules:
- All credentials are fully replaced.
- Old credentials become invalid immediately.
- No partial credential updates allowed.
- If interrupted mid-flow, `reset_code` remains valid until expiration.

### Step 5 — Completion
Upon successful credential setup:
- Clear `reset_code`
- Clear `reset_code_expires_at`
- Set `recovery_status` → `active`
- Log successful reclaim event

## IX. State Machine (Formal Definition)

### States (`recovery_status`)
- `active`
- `to_be_claimed`

### Allowed Transitions
1. `active` → `to_be_claimed`
   - Trigger: Teacher initiates reset
2. `to_be_claimed` → `active`
   - Trigger: Successful reclaim
3. `to_be_claimed` → `active`
   - Trigger: `reset_code` expiration
   - Action: Clear `reset_code` and expiration
4. `active` → `archived` (System state, separate from recovery_status)
   - Trigger: Teacher deletes class or student.

### Forbidden Transitions
- `archived` → `active` (unless future explicit restore feature)
- `to_be_claimed` → `archived` without logging
- Any transition that creates a new student record automatically

## X. Security Constraints
- Reset codes must be random, 8-character alphanumeric.
- Reset codes must expire after 10 minutes.
- Reset codes must be single-use.
- Rate limit reset code attempts.
- Lock reclaim flow after repeated failed attempts.
- Never reveal whether a specific student exists outside a valid reset flow.

## XI. Hard Boundaries (Must Not Do)

The recovery system must NOT:
- Create a new student record during recovery.
- Merge two student records automatically.
- Transfer balances between accounts.
- Copy or recreate items.
- Issue refunds during recovery.
- Modify transaction history.
- Adjust economic balances.
- Alter migration history.

Recovery restores access. It does not alter economic reality.

## XII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.