# V2 Student Blocks Redesign Note

**Status:** Draft design note  
**Purpose:** Record how `student_blocks` should be re-evaluated under the v2 identity,
authority, and domain redesign

## Why This Exists

`student_blocks` currently survives as a mixed-purpose mutable state table.

That is risky because the v2 redesign is moving toward:

- one clear identity model
- domain-owned state
- explicit authority boundaries
- fewer accidental sources of truth

If `student_blocks` is left vague, it can become another long-lived catch-all table even
after `students`, `teacher_blocks`, and `student_teachers` are deprecated.

## What `student_blocks` Actually Stores Today

Current fields of interest:

- `tap_enabled`
- `done_for_day_date`
- `rent_hall_passes`

These are not identity fields.

They are mutable operational state attached to class/period behavior.

## Current Responsibility Split

Based on current usage:

- `tap_enabled` is attendance control state
- `done_for_day_date` is attendance or work-lock state
- `rent_hall_passes` is rent-to-hall-pass accounting state

So `student_blocks` is already mixing at least two domains:

1. attendance state
2. rent or hall-pass entitlement state

## Why This Is A Problem

Under the newer v2 authority work, state should live with the domain that interprets and
mutates it.

`student_blocks` is weak for that model because:

- attendance logic writes to it
- rent-related logic writes to it
- routes still create and mutate rows directly in several places
- it remains keyed by older student-centric concepts even though v2 is moving toward
  `seat_id`

This makes it a likely future source of drift and ambiguity.

## Recommended Direction

Do not preserve `student_blocks` as a single target-state table.

Instead, redistribute its fields by domain.

### Attendance-Owned State

Move these fields into an attendance-owned state model:

- `tap_enabled`
- `done_for_day_date`

Suggested target shape:

- table name: `seat_attendance_state`
- primary reference: `seat_id`

Why:

- both fields are interpreted entirely by attendance/tap workflows
- they are operational controls, not identity
- they fit naturally with attendance authority

### Rent / Entitlement-Owned State

Move this field into a rent-owned or entitlement-owned state model:

- `rent_hall_passes`

Suggested target shape:

- table name: `seat_hall_pass_grants` or `seat_entitlements`
- primary reference: `seat_id`

Why:

- this is not identity
- this is not attendance history
- this is grant/accounting state created by rent behavior

## What Not To Do

- do not move all `student_blocks` fields onto `seats`
- do not keep `student_blocks` as a generic "seat settings" dump
- do not let identity services continue owning rent/hall-pass accounting long-term

Those options would preserve the same ambiguity under different names.

## Practical Migration Principle

If a `student_blocks` field answers "who is this actor?", it belongs in identity.

If it answers "what can this actor do right now in attendance?", it belongs in an
attendance-owned state model.

If it answers "what grant or operational benefit currently exists because of rent or
hall-pass rules?", it belongs in a rent/entitlement-owned state model.

Current `student_blocks` fields fall into the second and third categories, not the first.

## Working Recommendation

Target-state direction:

1. retire `student_blocks` as an identity-adjacent concept
2. move attendance flags into seat-scoped attendance state
3. move rent hall-pass accounting into seat-scoped entitlement state
4. keep `seats` focused on actor identity, not feature-owned mutable state

## Relationship To Other Docs

- `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md` defines the target identity model
- `docs/SPECS/V2_AUTHORITY_EXTRACTION_PLAN.md` defines service and authority boundaries
- this note records how `student_blocks` should be redistributed to match both
