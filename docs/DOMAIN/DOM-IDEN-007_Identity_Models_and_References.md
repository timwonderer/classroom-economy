
# DOM-IDEN-007: Identity Models and References

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-007 | 1.0 | 2026-07-01 | None | Constitutional |

---

## I. Purpose

This document defines the canonical reference models used throughout Classroom Token Hub and establishes how identity SHALL be stored, referenced, and resolved across the application.

The purpose of this document is to:

- Establish a single authoritative owner for every identity concept.
- Eliminate duplicate identity representations.
- Standardize canonical lookup patterns.
- Prevent non-authoritative identifiers from becoming independent sources of truth.

---

## II. Scope

This document governs:

- Canonical reference models
- Identity ownership
- Identity references
- Canonical foreign key usage
- Identity query requirements
- Identity anti-patterns

This document does **not** govern:

- Identity lifecycle
- Authentication implementation
- Identity creation
- Canonical Context Resolution
- Authorization
- Capability enforcement

---

## III. Authority

This document is **Tier 1 – Constitutional**.

All schemas, ORM models, services, APIs, queries, and future architectural decisions SHALL conform to this document.

This document is subordinate to:

- INV-CORE-000
- INV-CORE-001
- INV-ARC-008
- INV-ARC-019
- DOM-CORE-000

---

## IV. Core Principles

### 1. One Concept, One Owner

Every identity concept SHALL have exactly one canonical owner.

Only the owning model may define or modify that concept.

Other models SHALL reference the owner rather than duplicate the information.

### 2. References Over Duplication

Relationships SHALL be represented through canonical foreign keys.

If information can be obtained from a canonical reference model, it SHALL NOT be duplicated elsewhere.

### 3. Operational Identity is Separate from Display Identity

Operational identity SHALL NOT be coupled to display metadata.

Presentation labels, human-readable names, classroom labels, schedules, and other display-oriented information SHALL NOT participate in canonical identity resolution unless explicitly designated by constitutional documentation.

### 4. Canonical Resolution

Identity SHALL always be resolved from canonical reference models.

Derived values SHALL NOT become independent sources of truth.

---

## V. Canonical Reference Models

Each canonical reference model exists to answer one identity question.

No two canonical reference models SHALL answer the same identity question.

### `Users`
*(table name: `users`)*

#### Question Answered

**Can this entity authenticate and participate within Classroom Token Hub?**

#### Purpose

`Users` represents authenticated application principals.

It establishes authentication identity and serves as the canonical reference for authentication, session ownership, and application ownership.

#### Canonical Authority

`Users` owns:

- Authentication
- Account identity
- Application principal
- Session ownership
- Account lifecycle

#### Canonical Identifier

Database primary key:

```python
Users.id
```

Canonical foreign key:

```python
user_id
```

#### Must Not Own

`Users` SHALL NOT own:

- Classroom membership
- Classroom placement
- User-facing display identity
- Classroom configuration
- Attendance
- Economy state

---

### `ClassEconomy`
*(table name: `classes`)*

#### Question Answered

**Which classroom are we referring to?**

#### Purpose

`ClassEconomy` establishes the canonical classroom reference.

It owns every identifier used to uniquely identify a classroom.

#### Canonical Authority

`ClassEconomy` owns:

- Class identity
- Join code
- Public reference token
- Class display metadata
- Class timezone
- Teacher ownership (`user_id`)
- Lifecycle metadata

#### Canonical Identifier

Database primary key:

```python
ClassEconomy.id
```

Canonical identifier:

```python
class_id
```

#### Must Not Own

`ClassEconomy` SHALL NOT own:

- Classroom membership
- User display identity
- Classroom configuration
- Feature configuration

---

### `Seat`
*(table name: `seats`)*

#### Question Answered

**Who are you within this classroom?**

#### Purpose

`Seat` establishes classroom-local operational identity.

It represents classroom membership and serves as the canonical operational identity within a classroom economy.

#### Canonical Authority

`Seat` owns:

- User ↔ classroom binding
- Classroom membership
- Seat assignment
- Seat claim state
- Participation within the classroom economy
- Membership existence

#### Canonical Identifier

Database primary key:

```python
Seat.id
```

Canonical foreign key:

```python
seat_id
```

#### Must Not Own

`Seat` SHALL NOT own:

- Authentication
- User-facing display metadata
- Classroom configuration

---

### `IdentityProfile`
*(table name: `identity_profile`)*

#### Question Answered

**What should we refer to this seat as?**

#### Purpose

`IdentityProfile` stores the canonical user-facing display profile associated with a seat.

It centralizes mutable display information so that updates occur in one location and are immediately reflected throughout the application.

#### Canonical Authority

`IdentityProfile` owns:

- First name
- Last name
- Teacher notes
- Display badges
- Other user-facing display metadata

#### Query Requirements

`IdentityProfile` SHALL be resolved using the canonical operational identity:

```python
class_id
seat_id
```

Services requiring display information SHALL query `IdentityProfile` using the canonical operational identity rather than persisting duplicate display values.

#### Reference Rules

Database primary key:

```python
IdentityProfile.id
```

`IdentityProfile.id` exists solely as an internal relational identifier.

It SHALL NOT be used as a canonical application identifier.

Operational services SHALL NOT establish application context using `IdentityProfile`.

---

## VI. Canonical Reference Requirements

### `Users`

Application identity SHALL reference:

```python
user_id
```

### `ClassEconomy`

Classroom identity SHALL reference:

```python
class_id
```

`ClassEconomy` SHALL serve as the canonical classroom boundary.

Every classroom-scoped resource SHALL ultimately resolve through `class_id`.

Identifiers owned by `ClassEconomy` SHALL NOT be duplicated elsewhere.

### `Seat`

Operational classroom identity SHALL reference:

```python
seat_id
```

Operational queries SHALL establish classroom context using:

```python
class_id
seat_id
```

### `IdentityProfile`

Display identity SHALL NOT be referenced through:

```python
identity_profile_id
```

Instead, services SHALL resolve display information using:

```python
class_id
seat_id
```

This ensures display metadata remains centralized while operational identity continues to be established through `Seat`.

---

## VII. Prohibited Identity Patterns

### Constitutionally Extinct Identifiers

The following identifiers are constitutionally extinct.

They SHALL NOT appear in:

- Database schemas
- ORM models
- Business logic
- Services
- APIs
- Queries
- Tests
- Documentation

```text
teacher_id
student_id
admin_id
created_by_teacher_id
teacher.id
student.id
```

### Duplicate Display Metadata

The following patterns are prohibited when the information is canonically owned by `IdentityProfile`.

```text
Attendance.first_name
Attendance.last_name
Attendance.teacher_notes
Transaction.student_name
HallPass.student_name
```

### Identity by Metadata

Identity SHALL NOT be established using:

- First name
- Last name
- Period
- Block
- Classroom title
- Human-readable labels

These values are presentation metadata and SHALL NOT participate in canonical identity resolution.

---

## VIII. Identity Ownership Rule

Before introducing a new identity or display column, reviewers SHALL answer the following questions.

1. What domain concept does this represent?
2. Which canonical reference model owns that concept?
3. Can this information already be obtained through a canonical reference?

If the answer to Question (3) is **Yes**, the information SHALL remain in its canonical owner and SHALL NOT be duplicated elsewhere.

---

## IX. Canonical Reference Rule

The following canonical reference models define the identity architecture of Classroom Token Hub:

- `Users`
- `ClassEconomy`
- `Seat`
- `IdentityProfile`

These four models collectively answer the following identity questions:

| Model | Identity Question |
|--------|-------------------|
| `Users` | Can this entity authenticate and participate within Classroom Token Hub? |
| `ClassEconomy` | Which classroom are we referring to? |
| `Seat` | Who are you within this classroom? |
| `IdentityProfile` | What should we refer to this seat as? |

If a piece of information can be obtained through one of these canonical reference models, it SHALL NOT be duplicated elsewhere.

Models SHALL reference the canonical owner using its designated foreign key rather than persisting duplicate values.

This principle upholds the **Don't Repeat Yourself (DRY)** invariant and ensures every identity concept has exactly one authoritative source throughout the application.
