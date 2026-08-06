# FEAT-CLASS-001: Creating New Class Boundary

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---| --- | --- | --- |
| FEAT-CLASS-001 | 0.1 | 2026-07-12 | N/A | Normative |

---

## I. Purpose

This FEAT defines the canonical workflow for establishing a new Class Boundary.

A new Class Boundary consists of:

- one Class;
- one Teacher Seat;
- required class configuration;
- optionally, an initial set of unclaimed Student Seats.

This workflow SHALL be used for:

- initial class creation immediately following teacher account registration; and
- creation of additional classes by an existing authenticated teacher.

This FEAT owns orchestration only.

Persistence remains delegated to the owning domains.

---

## II. Constitutional Authority

### Primary Authority

**DOM-CLASS-001**

Authorizes:

- creation of a new Class;
- initialization of class configuration;
- establishment of a new Class Boundary.

### Supporting Authority

**DOM-IDEN-007**

Authorizes:

- Teacher Seat provisioning;
- Student Seat provisioning;
- IdentityProfile provisioning;
- initialization of student claim artifacts.

---

## III. Execution Context

This workflow SHALL execute within a Teacher Provisioning Context.

Required:

- authenticated `user_id`

Derived:

- `actor_role = teacher`

Absent:

- `class_id`
- `seat_id`

This workflow SHALL NOT execute within CanonicalContext because the target Class Boundary does not yet exist.

---

## IV. Workflow

The workflow SHALL execute in the following order.

1. Create the Class.
2. Provision the Teacher Seat.
3. Initialize required class configuration.
4. Optionally provision the initial student roster.
5. Update:
   - `last_active_class_id`
   - `last_active_seat_id`
6. Transition immediately into the newly created Class Boundary.

Successful completion SHALL always leave the teacher operating within the newly created Class Boundary.

---

## V. Initial Student Provisioning

Provisioning an initial roster is optional.

Each accepted student SHALL provision:

- one Student Seat;
- one IdentityProfile;
- required claim artifacts.

Student Users SHALL NOT be provisioned by this workflow.

Student account creation remains owned by FEAT-IDEN-001.

---

## VI. Initial Roster Interpretation

If an initial roster template is supplied, this FEAT SHALL interpret fields as follows.

| Field | Interpretation |
|--------|----------------|
| First Name | Read. Used to initialize IdentityProfile. |
| Last Name | Read. Used to initialize IdentityProfile. |
| Additional Notes | Read. Used to initialize IdentityProfile. |
| Class Name | Read only to initialize the newly created Class display value. |
| Section | Read only to initialize the newly created Class display value. |
| actor_public_id | Ignored. |
| Unknown columns | Ignored. |

Class Name and Section SHALL:

- initialize display configuration only;
- never determine class identity;
- never determine class membership;
- never partition uploaded students;
- never create additional Classes.

If multiple display values are detected, explicit teacher resolution SHALL be required before provisioning continues.

Regardless of uploaded metadata, this workflow SHALL create exactly one Class Boundary.

---

## VII. Cancellation

### Initial Teacher Registration

If cancelled before successful completion:

- the provisioning transaction SHALL roll back;
- no User, Class, Seat, or IdentityProfile created by this workflow shall persist.

### Existing Teacher

If cancelled before successful completion:

- the authenticated User SHALL remain unchanged;
- the teacher SHALL return to:
  - `last_active_class_id`
  - `last_active_seat_id`

---

## VIII. Failure

Provisioning SHALL execute atomically.

The workflow SHALL either:

- complete successfully; or
- roll back completely.

No partial Class Boundary SHALL persist.

---

## IX. Delegation

This FEAT delegates to:

- DOM-CLASS-001
- DOM-IDEN-007
- FEAT-IDEN-001
- FEAT-CORE-000

---

## X. Guarantees

This FEAT guarantees:

- exactly one Class Boundary is established;
- exactly one Teacher Seat is provisioned;
- every initial Student Seat belongs to the newly created Class;
- Student Users are never provisioned by this workflow;
- successful completion always transitions the teacher into the newly created Class Boundary.