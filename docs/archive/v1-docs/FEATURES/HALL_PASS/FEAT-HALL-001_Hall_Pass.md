# FEAT-HALL-001: Hall Pass Feature Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| FEAT-ARC-001     | 1.1     | 2026-03-08     | 1.0        | Normative       |

## I. Purpose
Define the full hall pass feature contract across student, teacher, and public verification flows. This spec is the source of truth for lifecycle states, API behavior, data invariants, and deprecation policy.

## II. Scope
In scope:
- Student hall pass request, cancel, checkout, and checkin flows.
- Teacher approval/rejection and active pass management.
- Public office verification URL flow.
- Hall pass settings (enabled state, pass types, queue/simultaneous limits).
- Attendance side effects (tap-out/tap-in).

Out of scope:
- Broader attendance policy semantics unrelated to hall pass events.
- Store/rent economics except where hall pass balance is consumed.

## III. Authority Level
Normative (FEAT Tier). Subordinate to INV-CORE-000 and FEAT-CORE-000.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`
- `FEAT-CORE-000_Feature_Foundation.md`

## V. Canonical Data Model

Primary table: `hall_pass_logs`
- `student_id` (required)
- `reason` (destination/pass type)
- `status` in: `pending`, `approved`, `rejected`, `left`, `returned`
- `period` optional class period snapshot
- `join_code` class isolation key (authoritative scope)
- `request_time`, `decision_time`, `left_time`, `return_time`

Settings table: `hall_pass_settings`
- Teacher-scoped by `teacher_id`, with `block=None` as global default.
- `queue_enabled` boolean.
- `queue_limit` global numeric limit.
- `pass_types` JSON per destination (`name`, `enabled`, `queue_limit`, `simultaneous_limit`).

Teacher public verification token:
- Public verification flow is keyed by `teacher_public_token` / `Admin.public_id`.
- Exposed as `/verify/hallpass/<teacher_public_token>`.
- `hall_pass_verify_token` remains a legacy compatibility surface, not the primary documented public identifier.

## VI. Lifecycle State Machine

Allowed transitions:
1. `pending` -> `approved`
2. `pending` -> `rejected` (teacher reject or student cancel)
3. `approved` -> `left` (student checkout or teacher/manual action)
4. `left` -> `returned` (student checkin or auto-return on start-work)

Forbidden transitions:
- Any transition from `rejected` to active states.
- `pending` -> `left` without teacher approval.
- `approved` -> `returned` without `left`.

Related but separate state:
- `StudentBlock.done_for_day_date` is a per-class student lock/state and is **not** a `HallPassLog.status` value.

## VII. Primary User Flow

Primary flow:
1. Student initiates request (creates `pending` record).
2. Teacher approves or rejects.
3. Student checks out (`approved` -> `left`).
4. Student checks in (`left` -> `returned`).

Deprecated compatibility flow:
- Terminal and queue endpoints are removed from active use and must return `410 Gone`.

## VIII. Behavior Rules

### Request-time gating:
- Request must be scoped to current class context (`join_code`).
- Pass type must be enabled (or request denied).
- Queue limits and destination limits must be enforced when configured.
- Default pass types are `Bathroom`, `Water Fountain`, `Office`, `Nurse`, and `Counselor`.
- Balance exemptions, if any, are determined by the configured pass type and route logic; `done for the day` is not a hall-pass reason.

### Approval-time behavior:
- On approve, hall pass balance is decremented when deduction applies.
- `rent_hall_passes` consumption is prioritized before purchased passes.

### Checkout/checkin side effects:
- Checkout creates `TapEvent(status='inactive')`.
- Checkin creates `TapEvent(status='active')`.
- Start-work flow auto-returns any active (`left`) pass in the same class context.

## IX. Public Verification Contract
Endpoint: `GET/POST /verify/hallpass/<teacher_public_token>`

Requirements:
- Token must be non-enumerable and rotatable.
- No roster listing.
- No multi-day history exposure.
- Query scope must be limited to selected teacher class (`join_code`) and current school day window.

## X. Public Verification Portal — Claim-Based Model
Design principle: Only reveals information in response to a specific student claim.

Input: Class, Student first name, Student last initial.
Scope constraints: `teacher_public_token` must match, `join_code` must belong to teacher, Date scope must be current school date (school timezone).

Output rules:
- `0` matches: `No hall pass record found for today.`
- `1` match: display minimal operational details only.
- `>1` matches: `Unable to uniquely verify. Please contact the teacher.`

## XI. API Surface

Teacher actions (Approve, Reject, Leave, Return)
Student actions (Cancel, Checkout, Checkin)
Settings (Update, Read, Rotate tokens)

## XII. Security and Privacy Requirements
- All operations remain tenant-scoped by class context (`join_code`) and role auth.
- Public verify endpoint must use capability token, never teacher username or internal numeric IDs.
- Outputs must avoid exposing non-essential PII or roster-level data.

## XIII. Observability and Audit
Minimum events to log:
- Request create, approve, reject, checkout, checkin, cancel.
- Verify-token rotation.
- Rate-limit or policy denials.

All timestamps are UTC at rest and converted at read time for user display.

## XIV. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
