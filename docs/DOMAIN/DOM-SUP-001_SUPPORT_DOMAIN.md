# DOM-SUP-001: Support Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-SUP-001 | 1.1 | 2026-06-02 | 1.0 | Normative |

## I. Purpose

Define the Support domain as the authority over issue lifecycle state, resolution action
history, correlation artifacts, user-submitted feedback, and teacher-to-class
communication records.

The Support domain records what actors reported and what corrective actions were taken.
It does not execute those corrective actions itself.

## II. Scope

This domain owns:

- support issue taxonomy
- student-submitted issue records and their lifecycle
- issue status audit trail
- resolution action records (what action was declared, not the effect)
- correlation packs (immutable diagnostic snapshot at submission time)
- user-submitted bug reports and suggestions
- teacher- and sysadmin-authored announcements

This domain does not own:

- ledger mutations (resolution actions that affect money go through FEAT → Ledger)
- identity records
- attendance facts
- configuration policy
- analytics snapshots

## III. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-LED-001_LEDGER_DOMAIN.md` (resolution actions may reference transactions; Ledger owns those rows)
- `DOM-ITR-001_INTERPRETATION_DOMAIN.md` (correlation packs read from observability tables at submission time)

## IV. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `issue_categories`
- `issues`
- `issue_status_history`
- `issue_resolution_actions`
- `ticket_correlation_packs`
- `user_reports`
- `announcements`

No other domain may define fields, impose lifecycle rules, or mutate these tables directly.

## V. Owned Tables

### `issue_categories`

Taxonomy of support issue types. Defines the vocabulary used to classify student issues.

### `issues`

Student-submitted support tickets. Core lifecycle record for a class-scoped issue.
Carries immutable submission content, mutable review and resolution state, and cached
display-safe identity fields.

### `issue_status_history`

Complete audit trail of every status transition on an issue. Append-only.

### `issue_resolution_actions`

Log of corrective actions declared by teachers or sysadmins against an issue. Records
the declared action and outcome but does not own the economic side-effects.

### `ticket_correlation_packs`

Immutable diagnostic snapshot captured at issue-submission time. Links the issue to
the actor's recent request traces and error events at the moment of filing.

### `user_reports`

Anonymous or attributed bug reports, suggestions, and comments submitted by any user
type. Separate from the issue ticket system; lighter-weight free-form channel.

### `announcements`

Teacher-authored or sysadmin-authored communications displayed to class or system-wide
audiences.

## VI. Schema Contract

### `issue_categories`

Key fields:

- `id`
- `name` — unique; the canonical category label
- `description`
- `category_type` — `transaction` | `general`
- `is_active`
- `display_order`

Rules:

- Categories are system-managed. Students select from this list at submission time;
  they do not create categories.
- `is_active = false` categories may not be selected for new issues but must be
  retained for display on historical issues.

### `issues`

Key fields:

- `id`
- `seat_id` — FK to seats (the student seat that filed the issue)
- `class_id` — FK to `classes`
- `sysadmin_id` — nullable; FK to `system_admins`; set if issue is escalated
- `category_id` — FK to issue_categories
- `join_code` — class isolation anchor; every issue belongs to exactly one class
- `status` — `OPEN` | `TEACHER_REVIEW` | `ESCALATED_TO_DEV` | `DEV_RESOLVED` | `TEACHER_FINAL_REVIEW` | `CLOSED`
- `issue_type` — `transaction` | `general`
- Immutable submission fields:
  - `student_explanation`
  - `student_expected_outcome`
  - `submitted_at`
- Display-safe cached identity fields (written at submission; never updated):
  - `student_first_name` — encrypted
  - `student_last_initial`
  - `actor_public_id` — UUID-encoded `seat.public_id`, used in sysadmin views instead
    of the raw seat FK
- Class context cache:
  - `class_label` — frozen display name at submission time
- Related record context:
  - `related_transaction_id` — nullable FK to transaction
  - `related_record_type` — `transaction` | `tap_event` | `rent_payment`
  - `related_record_id` — opaque ID of the related record
  - `context_snapshot` — JSON; frozen state of the related record at submission time
  - `page_url`
  - `system_metadata` — JSON
- Teacher review fields:
  - `reviewed_at`
  - `reviewer_notes`
  - `resolution`
  - `resolved_at`
  - `share_class_name_with_sysadmin` — explicit teacher consent for escalation context
  - `eligible_for_reward`
  - `escalated_at`
  - `escalation_reason`
  - `diagnostic_note`
- Sysadmin fields:
  - `sysadmin_reviewed_at`
  - `sysadmin_notes`
  - `sysadmin_resolved_at`
- Closure:
  - `closed_at`
  - `closed_by_type` — `teacher` | `sysadmin` | `system`

Rules:

- Submission fields (`student_explanation`, `student_expected_outcome`, `submitted_at`,
  `context_snapshot`) are immutable after creation.
- `actor_public_id` is the seat's UUID public ID and the only participant identity
  value visible to sysadmin; the raw `seat_id` FK is not surfaced in sysadmin views.
- `class_label` is cached at submission time; it must not be re-fetched live from
  ClassEconomy after submission.
- `share_class_name_with_sysadmin` defaults to false; it is set only by explicit
  teacher action during escalation. Class name must not be included in escalation
  payload without this flag being true.
- Status transitions follow a defined state machine (see §VIII).
- An issue is locked to student mutation once it reaches `TEACHER_REVIEW`.

### `issue_status_history`

Key fields:

- `id`
- `issue_id` — FK to issues (CASCADE)
- `join_code`
- `previous_status`
- `new_status`
- `changed_at`
- `changed_by_type` — `student` | `teacher` | `sysadmin` | `system`
- `changed_by_id`
- `notes`

Rules:

- Every status transition on an issue MUST produce a history row atomically with the
  status change on the `issues` row.
- History rows are append-only. No row is edited or deleted after creation.

### `issue_resolution_actions`

Key fields:

- `id`
- `issue_id` — FK to issues (CASCADE)
- `join_code`
- `action_type` — `reverse_transaction` | `correct_amount` | `waive_fee` | or other enumerated types
- `action_description`
- `performed_by_user_id` — FK to `users`; the teacher or sysadmin who took the action
- `related_transaction_id` — nullable FK to transaction (cross-domain reference)
- `amount_changed`
- `before_value` / `after_value`
- `created_at`

Rules:

- Resolution actions are a declaration log, not an execution mechanism. The Support
  domain records that an action was taken; it does not own the ledger rows created
  or reversed as a result.
- `related_transaction_id` is a cross-domain reference to the Ledger domain. It does
  not transfer ledger ownership to the Support domain.
- Resolution action rows are append-only. Actions declared in error must be addressed
  by subsequent actions, not by editing history.

### `ticket_correlation_packs`

Key fields:

- `issue_id` — PK and FK to issues (CASCADE); one-to-one
- `correlation_version` — identifies the correlation schema used
- `actor_type`
- `actor_public_id` — UUID-encoded `seats.public_id`; matches the actor reference used
  in `actor_request_trace` and `error_events`
- `class_id`
- `request_trace_json` — frozen list of relevant request trace entries at submission time
- `error_refs_json` — frozen list of relevant error event references at submission time
- `created_at`

Rules:

- Correlation packs are created once at issue-submission time and are never mutated.
- `request_trace_json` and `error_refs_json` are frozen snapshots; they are not live
  references. Even if the source rows in `actor_request_trace` or `error_events` are
  purged, the pack retains its captured data.
- `actor_public_id` is the canonical deidentified seat actor reference. It resolves
  through Identity under the ticket's `class_id`; it does not grant authority by itself.

### `user_reports`

Key fields:

- `id`
- `anonymous_code` — HMAC-derived opaque reference; indexed; used for sysadmin display
  instead of raw identity
- `user_type` — `student` | `teacher` | `anonymous`
- `join_code` — nullable; present for class-contextual reports
- `report_type` — `bug` | `suggestion` | `comment`
- `error_code` — nullable HTTP status code associated with the report
- `title`
- `description`
- `steps_to_reproduce` — nullable
- `expected_behavior` — nullable
- `page_url`
- `submitted_at`
- `ip_address` / `user_agent`
- `status` — `new` | `reviewed` | `rewarded` | `closed` | `spam`
- `admin_notes`
- `reviewed_at`
- `reward_amount` / `reward_sent_at`
- Internal FK (hidden from sysadmin): `student_id` — for reverse-routing a reward; never
  surfaced in sysadmin views

Rules:

- `anonymous_code` and `user_type` are the only actor identifiers surfaced in sysadmin
  views. `student_id` is for internal reward routing only and must not appear in any
  sysadmin display.
- Sysadmin reward delivery uses `student_id` to route the reward through FEAT → Ledger;
  that cross-domain effect does not transfer ledger ownership.
- Report submission content (`title`, `description`, `steps_to_reproduce`,
  `expected_behavior`) is immutable after creation.

### `announcements`

Key fields:

- `id`
- `created_by_user_id` — nullable FK to `users`; the teacher or sysadmin who authored
  the announcement
- `target_user_id` — nullable FK to `users`; set for announcements directed at a
  specific teacher
- `audience_type` — `class` | `system_wide` | `all_teachers` | `all_students` | `teacher_all_classes` | `specific_class`
- `join_code` — nullable; present when `audience_type` is class-scoped
- `title`
- `message`
- `is_active`
- `priority` — `low` | `normal` | `high` | `urgent`
- `created_at` / `updated_at`
- `expires_at` — nullable; announcement becomes inert after this timestamp

Rules:

- Announcements are informational only. They do not grant permissions, alter capability
  state, change configuration, or affect any other domain's tables.
- Class-scoped announcements (`audience_type = 'class'` or `'specific_class'`) must
  carry a `join_code`. System-wide announcements must not carry a `join_code`.
- `expires_at` is a display hint. The announcement row is not deleted when it expires;
  display logic uses `expires_at` to suppress rendering.
- A teacher may only create announcements for classes they hold a teacher seat in
  (`join_code` must resolve to a class where `created_by_user_id` holds a teacher seat).
  FEAT enforces this; the domain stores the result.

## VII. Constraints

- Issue submission content is immutable after creation.
- Correlation packs are immutable after creation.
- Resolution actions are append-only; correction of an erroneous action requires a
  subsequent action row, not in-place editing.
- Issue status transitions must atomically produce a history row.
- The Support domain reads ledger, attendance, and identity data for context but does
  not mutate those domains directly.
- Corrective money effects (e.g., transaction reversals) must be executed via FEAT,
  which invokes Ledger. The resolution action row records the declaration; Ledger owns
  the resulting transaction row.
- Sysadmin-accessible actor references use UUID-encoded `seats.public_id`, carried as
  `actor_public_id` where a support-specific column name is needed.
- Sysadmins must not be exposed to raw `student_id` or `teacher_id` values via the
  support system. All sysadmin-accessible actor references must use UUID-encoded
  `seats.public_id`.

## VIII. Issue Status Machine

States: `OPEN` → `TEACHER_REVIEW` → `ESCALATED_TO_DEV` → `DEV_RESOLVED` →
`TEACHER_FINAL_REVIEW` → `CLOSED`

Allowed transitions:

| From | To | Actor |
|------|----|-------|
| `OPEN` | `TEACHER_REVIEW` | Teacher or system |
| `TEACHER_REVIEW` | `ESCALATED_TO_DEV` | Teacher |
| `TEACHER_REVIEW` | `CLOSED` | Teacher |
| `ESCALATED_TO_DEV` | `DEV_RESOLVED` | Sysadmin |
| `DEV_RESOLVED` | `TEACHER_FINAL_REVIEW` | System or sysadmin |
| `TEACHER_FINAL_REVIEW` | `CLOSED` | Teacher |
| Any | `CLOSED` | System (e.g., TTL expiry) |

Constraints:

- An issue is locked to student mutation once it leaves `OPEN`.
- Every transition MUST atomically produce an `issue_status_history` row.
- No transition may skip states (e.g., `OPEN` → `CLOSED` is only allowed via system
  cleanup or explicit short-circuit; it must still produce a history row).

## IX. Derived / Cross-Domain Rules

- When a resolution action involves a transaction reversal, FEAT coordinates the
  Ledger reversal and the Support resolution action row in a single operation. Ledger
  owns the resulting transaction rows; Support owns the resolution action row.
- `related_transaction_id` on `issue_resolution_actions` is a read-only reference to
  the Ledger domain for audit traceability. It does not transfer ledger write authority.
- Sysadmin reward delivery for `user_reports` is initiated via FEAT; the resulting
  ledger credit is owned by Ledger, not Support.
- `ticket_correlation_packs` read from `actor_request_trace` and `error_events` at
  issue-submission time. After pack creation, the Support domain is self-contained;
  it does not re-query observability tables for existing packs.

## X. Amendment

Revisions require version increment, effective-date update, and continued consistency
with higher-order invariants.
