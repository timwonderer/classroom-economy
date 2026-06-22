---
# ARC-OPS-005: API Reference

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-005      | 1.1     | 2026-03-08     | 1.0        | Constitutional  |

## I. Purpose

This document captures the current v2.0 API contract with emphasis on class scoping, public teacher identity, and join-code authority.

## II. Authentication Classes

- **Public**: No authenticated session required
- **Student**: Student session required
- **Admin**: Teacher/admin session required
- **System Admin**: System-admin session required

## III. Runtime Contract Rules

- `current_join_code` is the active class context for session-based teacher and student flows.
- Class-scoped admin and student APIs are membership-gated, not `teacher_id`-gated.
- Public teacher references must use `teacher_public_id` / `Admin.public_id`, not numeric teacher IDs.

## IV. Key Public Endpoints

### `GET /api/hall-pass/verification/active`

- **Auth**: Public
- **Purpose**: Return active/recent hall-pass records for a teacher identified by public teacher identity.
- **Required Query Param**: `teacher=<teacher_public_id>`
- **Behavior**:
  - resolves teacher by `teacher_public_id` / `public_id`
  - derives join-code scope from teacher-owned active `ClassMembership`
  - returns only passes within that scope

### `POST /api/set-timezone`

- **Auth**: Public
- **Purpose**: Set timezone in session for localized rendering

## V. Key Student Endpoints

### `POST /api/purchase-item`

- **Auth**: Student
- **Purpose**: Purchase a store item in the active class scope
- **v2 Contract**:
  - spending authorization is scoped by `join_code`
  - live v2 flows do not use `join_code IS NULL` fallback settings rows

### `POST /api/use-item`

- **Auth**: Student
- **Purpose**: Submit delayed redemptions for teacher approval

### `POST /api/tap`

- **Auth**: Student
- **Purpose**: Append attendance/tap events for the active class period

### `GET /api/student-status`

- **Auth**: Student
- **Purpose**: Return per-class attendance/work state and projected pay
- **v2 Contract**:
  - class-specific state is driven by the student’s `current_join_code` context and class membership

### `GET /api/hall-pass/available-types`

- **Auth**: Public or Student, depending on caller context
- **Purpose**: Resolve available hall-pass types for a class
- **v2 Contract**:
  - accepts `join_code` and `teacher_public_id`
  - no numeric teacher ID is required for the intended path
  - student sessions reject out-of-scope join codes

## VI. Key Admin Endpoints

### `POST /api/approve-redemption`

- **Auth**: Admin
- **Purpose**: Approve a student redemption request
- **v2 Contract**:
  - admin must have class scope for `student_item.join_code`
  - scope failures return `"You do not have access to this class."`
  - teacher ownership of the underlying item is still validated

### `POST /api/reject-redemption`

- **Auth**: Admin
- **Purpose**: Reject a student redemption request
- **v2 Contract**:
  - class access must match the redemption’s `join_code`

### `GET /api/attendance/history`

- **Auth**: Admin
- **Purpose**: Return attendance history for the selected class or owned class fan-out
- **v2 Contract**:
  - explicit class selection is scoped by authorized `join_code`
  - all-sections behavior must fan out over owned join codes only

### `GET /api/admin/tap-entries/<student_id>`
### `DELETE /api/admin/tap-entries/<event_id>`

- **Auth**: Admin
- **Purpose**: Review and mutate tap entries for the active class
- **v2 Contract**:
  - current admin session must have `current_join_code`
  - current class mismatch is rejected
  - cross-class event mutation is denied

### `GET|POST /api/admin/block-tap-settings`
### `GET|POST /api/admin/student-block-settings`

- **Auth**: Admin
- **Purpose**: Read or update tap/block settings for class members
- **v2 Contract**:
  - writes are constrained to admin-owned class scope
  - out-of-scope `StudentBlock` rows are ignored rather than mutated

## VII. Admin HTML Route Behaviors with API Significance

These are not pure JSON APIs but define important v2 class contracts:

- `/admin/current-class`
  - sets current class by `join_code`
  - requires active admin membership in that class
- `/admin/join-code/delete`
  - requires admin membership
  - destructive delete is guarded by confirmation flow
- `/admin/export-students`
  - selected-class export computes balances and earnings in exact join-code scope
- `/admin/help-support`
  - teacher support intake route for class-scoped issue submission
  - requires a valid teacher session and uses the current class context when present
- `/admin/issues`
  - teacher issue review queue
  - selected `current_join_code` narrows results to that authorized class; otherwise the queue fans out over the teacher's owned classes
- `/admin/economy-health`
  - teacher-facing diagnostics and economy analysis surface for the selected class
- `/admin/feature-settings`
  - class-scoped feature-flag management UI
- `/admin/bonuses`
  - teacher action that posts bonus adjustments in class scope
- `/admin/backfill-transactions`
  - teacher maintenance flow for ledger backfill/repair tasks

## VIII. Transitional Notes

- Some older capability-token surfaces still exist, including `hall_pass_verify_token`, but public teacher identity for current verification flows is centered on `teacher_public_id`.
- Compatibility aliases and legacy parameters may still exist in parts of the codebase, but they are not the intended v2 contract for new behavior or documentation.

## IX. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
