# SPEC-TEST-002: Canonical Test Identities

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-TEST-002    | 2.0     | 2026-07-17     | 1.0        | Constitutional  |

---

## I. Purpose

This document defines the canonical fictional identities used throughout the Classroom Token Hub test suite and the rules governing how those identities are constructed.

The purpose of canonical test identities is to:

- eliminate ad hoc test data;
- provide deterministic, reusable identity scenarios;
- ensure all tests construct identities using production workflows rather than direct database mutation;
- guarantee that a test with invalid identity, scope, or context never runs.

These fixtures represent canonical **input data** — the information a teacher would supply at roster upload time. They do not represent database state. All database artifacts are produced by production code.

---

## II. Scope

This document governs all tests that require teacher identity, student identity, or class scope. It defines:

- what canonical input data is permitted;
- which scenarios exist and what each is for;
- how the test initializer enforces constitutional invariants before any test runs;
- what prior helpers are superseded.

It does not define implementation details (property references, code examples, migration patterns). Those are in `SPEC-TEST-001`.

---

## III. Authority Level

Constitutional within the test namespace. The canonical identity data file (`tests/helpers/canonical_identities.py`) implements this specification. The helper must not invent data outside this document.

### Dependencies

- `DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md`
- `DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE.md`
- `DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`

---

## IV. Design Principles

### Roster data is canonical input

The canonical fixtures represent the information supplied during roster upload.

They intentionally do not represent:

- Users
- Seats
- Identity Profiles
- Claims
- Sessions
- Authentication state

Those artifacts must always be created through production code paths. The fixture is the input; production FEATs produce the output.

---

### Identity is not predetermined

Two roster rows containing identical names are not assumed to represent the same authenticated person.

| Class | Name |
|---|---|
| Chemistry | Ava Chen |
| AP CSP | Ava Chen |

These may later become two independent users, or two seats bound to one user. The fixture makes no assumption. Identity is established only through `FEAT-IDEN`.

---

### Teacher notes are roster input

Teacher notes originate from roster upload. Although they ultimately reside on the seat-scoped `IdentityProfile`, the canonical fixtures store them as upload data because that is the production input.

Different roster rows with identical student names may contain different teacher notes. This is valid and intentional — it represents the disambiguation signal a teacher provides.

---

## V. Canonical Teachers

Four teachers are defined. Each owns one or more canonical classrooms.

| Identifier | Username |
|---|---|
| `teacher_alice` | `teacher.alice` |
| `teacher_brian` | `teacher.brian` |
| `teacher_carmen` | `teacher.carmen` |
| `teacher_daniel` | `teacher.daniel` |

Teachers are provisioned with hashed credentials by the initializer. Tests must never manually create teacher credentials.

---

## VI. Canonical Classrooms

Each classroom represents a complete roster upload. A classroom definition contains:

- a reference to a canonical teacher
- a display name and section
- a roster of student rows

Each roster row contains `first_name`, `last_name`, `teacher_note`, `chosen_word`, `pin`, and `passphrase`. The `chosen_word` is the word a student would supply during username creation; all other per-student credentials are preset.

---

## VII. Canonical Scenarios

### Scenario A — Standard Classroom

**Keys:** `chemistry_p1`, `ap_csp_p3`
**Teacher:** `teacher_alice`

Normal classrooms with unique student names within each class. The default choice for tests that need class scope.

**Use for:** attendance, payroll, ledger, store, obligations, feature flags, and any test that needs "some teacher and students" without edge-case constraints.

---

### Scenario B — Shared Names Across Classes

**Keys:** `chemistry_p1` and `ap_csp_p3` together
**Teacher:** `teacher_alice` (same teacher, two classes)

Two classrooms owned by the same teacher contain matching roster names. No identity relationship is implied between matching names across these classes.

**Use for:** multi-class identity binding, claim workflow, user ↔ seat relationship testing.

---

### Scenario C — Duplicate Names

**Key:** `duplicate_names`
**Teacher:** `teacher_carmen`

One classroom contains multiple students with identical full names. Teacher notes serve as the disambiguation signal.

| Name | Teacher Note |
|---|---|
| Alex Lee | Basketball |
| Alex Lee | Glasses |

**Use for:** claim ambiguity, identity resolution, teacher-note disambiguation.

---

### Scenario D — Cross-Teacher Names

**Keys:** `chemistry_p1` (teacher.alice) and `biology_block_a` (teacher.brian)

Different teachers upload rosters containing matching student names. No identity relationship is implied across teacher boundaries.

**Use for:** cross-teacher isolation, ownership boundaries, identity claim testing.

---

### Scenario E — Unicode

**Key:** `unicode`
**Teacher:** `teacher_daniel`

Roster containing apostrophes, hyphens, accented characters, and international names.

**Use for:** encoding correctness, hashing correctness, rendering correctness.

---

## VIII. Enforcement — Canonical Test Initializer

All tests that require class scope, teacher identity, or student identity **must** enter through `tests/helpers/classroom_initializer.py`. No other path is permitted.

```python
from tests.helpers.classroom_initializer import (
    initialize,             # DB state only; no session
    initialize_as_teacher,  # teacher session + context verified
    initialize_as_student,  # student session + context verified
)
```

### Initialization order

1. `provision_classroom()` — calls production code to build teacher + class + students
2. **DB self-test** — re-queries every entity from the DB and verifies all constitutional invariants hold
3. *(optional)* **Session** — `login_teacher()` or `login_student()` sets Flask session
4. **Context self-test** — `resolve_canonical_context()` is called inside a real request context and its output is verified against the provisioned state

### Self-test contract

If any self-test assertion fails, the test is aborted immediately via `pytest.fail()`. A test with invalid identity, scope, or context must never run.

| Layer | Checks |
|---|---|
| DB — ClassEconomy | `class_id` and `join_code` set; correct `user_id` |
| DB — Teacher User | `user_role == TEACHER`; `username_hash` set; `last_active_class_id` and `last_active_seat_id` correct |
| DB — Teacher Seat | `role == "teacher"`; `user_id` and `class_id` correct |
| DB — Student User | `user_role == STUDENT`; `username_hash`, `pin_hash`, `passphrase_hash` set; `last_active_class_id` and `last_active_seat_id` correct |
| DB — Student Seat | `role == "student"`; `user_id` and `class_id` correct; `claimed_at` set; claim hashes and `roster_fingerprint` set |
| DB — IdentityProfile | `class_id`, `first_name`, `last_name` match fixture |
| Session | `current_session_nonce` in session matches `user.current_session_nonce` in DB |
| Context | `resolve_canonical_context()` returns `CanonicalContext`; `user_id`, `class_id`, `seat_id`, `actor_role` all match provisioned state |

---

## IX. Fixture Authority

These fixtures define only the canonical input supplied by teachers at roster upload time.

The following artifacts **must always** be created through production code paths:

- `ClassEconomy`
- `Seat`
- `IdentityProfile`
- `User`
- Claim
- Session
- Authentication state

Tests must never construct these objects directly unless the test is explicitly validating the lower-level component responsible for creating them.

One legitimate exception: tests that require custom identity relationships beyond any single canonical scenario (e.g. a student enrolled in multiple classes simultaneously) may add extra `Seat` rows after calling `initialize`, but the base classroom identity must still come from the initializer.

---

## X. Superseded Helpers

The following helpers are superseded for any test that requires canonical identity. New tests must not use these paths. Existing tests should be migrated.

| Superseded helper | Reason |
|---|---|
| `tests/helpers/v2_fixtures.py` — `seed_canonical_admin`, `make_admin` | No self-test; credentials constructed ad hoc |
| `tests/helpers/class_scope.py` — `create_class_scope`, `make_student_identity`, `make_student_with_seat` | No self-test; DB state assembled manually |
| `tests/helpers/admin_context.py` | Session set without DB or context verification |
| `tests/helpers/canonical_session.py` — `set_canonical_context` | Session-only; no DB or context self-test |

See `SPEC-TEST-001` for migration patterns.
