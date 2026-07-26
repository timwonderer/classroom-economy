# DOM-OBL-001: Obligations Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-OBL-001 | 2.6 | 2026-07-25 | 2.5 | Constitutional |

---

## I. Purpose

This document defines the Obligations domain as the canonical authority over instantiated monetary liabilities and their lawful resolution.

Obligations owns:

- the existence of a liability after it has been lawfully assessed;
- the lifecycle of that liability through payment or waiver;
- recurring reminder state for liabilities that must be reconsidered at a later boundary.

Obligations does not own:

- the contractual terms that cause a liability to exist;
- the Ledger movement that records money;
- the insurance entitlement or coverage lifecycle;
- post hoc monetary correction after a ledger action;
- any mutable status flag that duplicates what can be derived from immutable facts.

---

## II. Scope

This domain governs:

- obligation event facts;
- recurring bill-cycle reminder state;
- derived obligation projections such as satisfied, outstanding, visible, and past due.

Obligations operates on class-scoped and seat-scoped truth. It never owns global money, global identity, or cross-class authority.

### A. Rent

Rent is a homegrown obligation lifecycle owned by Obligations. It is configured upstream by Class Configuration, but Obligations owns the assessment and recurring debt progression once the lawful rent contract exists.

### B. Insurance

Insurance is not owned by Obligations as a product lifecycle. Store and Entitlements owns the insurance entitlement / coverage lifecycle, and Class Configuration owns the insurance definition and version lineage. Obligations may service recurring insurance premiums as debt lifecycle, but only with lawful inputs supplied by the owning authority.

### C. Immediate Charges

Overdraft fees, NSF fees, and other immediately collected charges are still obligations when the system lawfully instantiates a liability before or alongside settlement. The fact that the liability is settled immediately does not remove it from this domain.

### D. Exclusions

Obligations does not own store purchases. Store purchases are immediate exchanges, not assessed liabilities.

---

## III. Authority Level

Tier 1 - Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants.

It is subordinate to:

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`

---

## IV. Canonical Business Authority

The Obligations domain is the sole business authority responsible for:

- lawful assessment of monetary liabilities;
- lawful satisfaction of assessed liabilities through payment or waiver;
- recurring bill-cycle progression;
- derived status over obligation facts;
- cross-domain debt lineage preserved by internal reference and correlation.

Consumers SHALL NOT:

- derive obligation status independently;
- derive payment completeness independently;
- mutate obligation persistence directly;
- reinterpret the meaning of an obligation using label-based or route-local logic;
- write mutable status columns that duplicate derived truth.

Consumers SHALL instead invoke the canonical business operations owned by this domain.

---

## V. Vocabulary

### 1. Obligation

An obligation is an instantiated monetary liability associated with a seat.

An obligation exists because a lawful upstream authority determined that a seat owes money under a specific relationship or enforcement action.

The obligation does not own the monetary amount itself. The authoritative amount comes from the upstream contract/configuration or from the lawful caller supplying the assessed terms.

### 2. Internal Reference

An internal reference identifies a continuing obligation-producing relationship.

It answers:

> Which continuing relationship are these assessments part of?

The internal reference is stable across recurring assessments for the same continuing relationship.

It does not encode the business meaning of that relationship inside Obligations.

### 3. Correlation ID

A correlation ID identifies one individual instantiated obligation.

It binds together the immutable events that belong to that single liability instance.

### 4. Assessment

An assessment is the immutable fact that a liability lawfully came into existence.

Every liability begins with exactly one assessment.

### 5. Payment

A payment is the immutable fact that Ledger-backed monetary movement was applied toward an assessment.

Multiple payments may exist for the same assessment.

### 6. Waiver

A waiver is the immutable fact that the remaining outstanding rent liability no longer requires payment.

Waiver is rent-only.

Waiver creates no Ledger movement.

### 7. Bill Cycle

A bill cycle is an identity-blind temporal reminder that a continuing internal reference is due to be considered for another assessment.

Bill cycle does not know whether the reference represents rent or insurance.

Bill cycle does not know the amount, actor, seat, class, product, tier, or renewal legality.

Bill cycle only remembers that the same internal reference is due again at a lawful boundary.

---

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `assessment_events`
- `bill_cycles`

`DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md` is authoritative for the exact target table set. This document defines the obligations-side meaning of those tables.

This domain does **not** own:

- any mutable paid/overdue/reversed scalar state
- insurance entitlement state
- Ledger transactions

---

## VII. Canonical Persistence

### 1. `assessment_events`

Records the historical fact of obligation events.

Key fields:

- `id`
- `timestamp` - time when the row is created, which represents the time when the assessment took place.
- `seat_id` - FK to `seats`
- `class_id` - FK to `classes`
- `internal_ref` - stable lineage key for the continuing obligation-producing relationship
- `correlation_id` - identifier for this individual liability instance
- `event_type` - `ASSESSMENT` | `PAYMENT` | `WAIVED`
- `obligation_type` - closed enum of lawful assessment categories
- `policy_version_id` - lawful version or source snapshot reference
- `bill_cycle_id` - nullable FK to `bill_cycles`
- `ledger_transaction_id` - nullable FK to `ledger_transaction`; required for `PAYMENT`


Rules:

- exactly one `ASSESSMENT` exists per individual liability instance;
- `PAYMENT` may occur multiple times for the same assessment;
- `WAIVED` is rent-only;
- no amount is persisted here;
- no paid/unpaid/overdue/satisfied/reversed flag is persisted here;
- an assessment is immutable once lawfully written.
- no `due_at` (on `bill_cycles`), `viewable_at` (Class Configuration), `assessed_at` (covered by `timestamp`), or `created_at` (on Class Configuration)

### 2. `bill_cycles`

Records recurring temporal progression for an internal reference.

Key fields:

- `id`
- `internal_ref` - for specific assessment_event referencing and advancement
- `cycle_number` - for advancement tracking
- `source_version_id` or equivalent lawful version snapshot reference
- `cycle_boundary_at` - for due date derivation
- `next_assessment_at` - for triggering the next assessment event
- 

Rules:

- bill cycles do not store class identity or seat identity;
- bill cycles do not store amount;
- bill cycles do not store business meaning for the reference;
- bill cycles are only lawful when they point to a currently continuing relationship;
- a terminated relationship produces no successor cycle.
- `created_at` isn't stored here, when an recurring assessment event is written, a corresponding `bill_cycles` row is written simultaneously. The timestamp stored on `assessment_event` serves as the `created_at` reference.

---

## VIII. Derived State

The following SHALL be derived and SHALL NOT be persisted as canonical obligation truth:

- satisfied;
- outstanding;
- past due;
- visible;
- partial payment;
- amount paid;
- amount outstanding;
- days late;
- overpayment handling;
- any mutable lifecycle flag that can be inferred from immutable events.

### Derived evaluation rules

For one assessment:

```text
paid_amount = sum(authoritative Ledger amounts referenced by PAYMENT events for the same correlation_id)
has_waiver = exists(WAIVED for the same correlation_id)

if paid_amount >= assessed_amount:
    status = SATISFIED
elif has_waiver:
    status = SATISFIED
else:
    status = OUTSTANDING
```

Past due is derived as:

```text
status == OUTSTANDING and canonical_now > due_at
```

---

## IX. Canonical Business Operations

The long-term implementation goal of this domain is to expose a canonical business surface rather than persistence-oriented behavior.

### 1. `create_obligation(...)`

Meaning:

> Establish that a lawful monetary liability occurred.

Result:

- creates exactly one `ASSESSMENT` event for the correlation;
- may be used for deferred liabilities or immediate charges;
- does not itself store the amount.

### 2. `satisfy_obligation(...)`

Meaning:

> Record lawful progress toward or closure of an existing liability.

Methods:

- `PAYMENT`
- `WAIVED`

Rules:

- `PAYMENT` requires a lawful Ledger transaction reference;
- `PAYMENT` may be repeated for partial payment;
- `WAIVED` is rent-only;
- `WAIVED` closes any outstanding remainder without a Ledger movement.

### 3. `advance_bill_cycle(...)`

Meaning:

> Record the next temporal reminder for the same continuing internal reference.

Rules:

- it does not determine what the reference represents;
- it does not decide whether the source is lawful;
- it does not mutate upstream contractual truth;
- it only creates the successor recurring reminder when lawful continuation exists.

---

## X. Canonical View Models (Read Projections)

Obligations exposes two canonical immutable view models for page rendering. These are not persistence entities; they are derived projections built from the immutable facts in `assessment_events`, `bill_cycles`, and Ledger.

### A. `StudentObligationView`

**Purpose:** Answer "What does this student owe right now, how much have they satisfied, when do they move to next cycle?"

**Construction:** `build_student_obligation_view(seat_id, class_id, obligation_type)` → `StudentObligationView | None`

**Fields:**
- `obligation_type` - The obligation category (RENT, INSURANCE_PREMIUM, FINE, FEE, etc.)
- `seat_id` - The seat being viewed
- `class_id` - The class context (multi-tenancy scoping)
- `current_period` - Dict with:
  - `amount_due` - Assessed amount for this cycle
  - `amount_paid` - Amount satisfied by PAYMENT events
  - `balance` - Remaining outstanding (can be negative for overpayment)
  - `is_paid` - Whether `amount_paid >= amount_due`
  - `is_waived` - Whether a WAIVED event exists
  - `days_until_due` - Days from now until due date
  - `days_overdue` - Days past due date (negative if not yet due)
- `prior_obligations` - List of prior-cycle obligation dicts (similar structure)
- `payment_history` - List of PAYMENT events with timestamps and amounts
- `totals` - Dict with aggregate statistics (`total_assessed`, `total_paid`, `total_outstanding`)
- `settings` - Configuration metadata (grace period, frequency, etc. from upstream sources)

**Properties:**
- Frozen (immutable, hashable)
- Fully scoped by `class_id` (multi-tenancy safe)
- Returns `None` if no assessments exist for seat/class/obligation_type

**Contract:** Routes receive this from the read service, templates consume it directly without further derivation.

### B. `ClassObligationSummary`

**Purpose:** Answer "Which students are current, which are outstanding, which are past-due?"

**Construction:** `build_class_obligation_summary(class_id, obligation_type)` → `ClassObligationSummary`

**Fields:**
- `class_id` - The class context
- `obligation_type` - The obligation category
- `summary_date` - When the projection was computed
- `status_breakdown` - Dict with counts:
  - `up_to_date` - Students with no past-due assessments
  - `outstanding` - Students with current-cycle unpaid but not yet due
  - `past_due_grace` - Students in grace period (days_overdue > 0 and < grace_days)
  - `past_due_overdue` - Students past grace period (days_overdue >= grace_days)
- `student_rows` - List of per-student dicts with:
  - `seat_id`, `student_name`, `status` (one of the four above)
  - `due_date`, `amount_due`, `amount_paid`, `balance`, `days_overdue`
  - `is_waived` - Whether any assessment is waived

**Properties:**
- Frozen (immutable, hashable)
- Multi-tenancy scoped (only one class's students)
- Always returns a valid structure; empty for classes with no seats or assessments

**Contract:** Routes pass this directly to templates; templates loop over `student_rows` to render rosters or use `status_breakdown` to render summaries.

### C. Read Service Primitives

Implementations must call these immutable read functions, never write directly from routes:

- `get_assessment_events_for_seat_class(seat_id, class_id, obligation_type=None)` - Returns all ASSESSMENT events for the seat
- `get_satisfaction_events(seat_id, correlation_id)` - Returns PAYMENT/WAIVED events for one obligation
- `get_bill_cycles_for_reference(internal_ref)` - Returns recurring cycle reminders
- All queries scoped by `class_id`, never by `teacher_id` alone

### D. View Model Construction Requirements

Every domain that follows the view model pattern must:

1. **Define immutable dataclasses** - Use `@dataclass(frozen=True)` to prevent accidental mutations
2. **Generic over obligation_type (or domain concept)** - Not rent-specific, not insurance-specific
3. **Scope by class_id** - All queries filtered by class_id during construction
4. **Hide persistence shape** - Templates see dicts with display-friendly keys, never SQLAlchemy objects
5. **Derive all status** - Do not store boolean flags like `is_past_due`; derive them at read time
6. **Build immutably** - Constructor functions are pure; they read state and build an immutable result object

---

## XI. Canonical Persistence

### 1. `assessment_events`

Records the historical fact of obligation events.

Key fields:

- `id`
- `timestamp` - time when the row is created, which represents the time when the assessment took place.
- `seat_id` - FK to `seats`
- `class_id` - FK to `classes`
- `internal_ref` - stable lineage key for the continuing obligation-producing relationship
- `correlation_id` - identifier for this individual liability instance
- `event_type` - `ASSESSMENT` | `PAYMENT` | `WAIVED`
- `obligation_type` - closed enum of lawful assessment categories
- `policy_version_id` - lawful version or source snapshot reference
- `bill_cycle_id` - nullable FK to `bill_cycles`
- `ledger_transaction_id` - nullable FK to `ledger_transaction`; required for `PAYMENT`


Rules:

- exactly one `ASSESSMENT` exists per individual liability instance;
- `PAYMENT` may occur multiple times for the same assessment;
- `WAIVED` is rent-only;
- no amount is persisted here;
- no paid/unpaid/overdue/satisfied/reversed flag is persisted here;
- an assessment is immutable once lawfully written.
- no `due_at` (on `bill_cycles`), `viewable_at` (Class Configuration), `assessed_at` (covered by `timestamp`), or `created_at` (on Class Configuration)

### 2. `bill_cycles`

Records recurring temporal progression for an internal reference.

Key fields:

- `id`
- `internal_ref` - for specific assessment_event referencing and advancement
- `cycle_number` - for advancement tracking
- `source_version_id` or equivalent lawful version snapshot reference
- `cycle_boundary_at` - for due date derivation
- `next_assessment_at` - for triggering the next assessment event


Rules:

- bill cycles do not store class identity or seat identity;
- bill cycles do not store amount;
- bill cycles do not store business meaning for the reference;
- bill cycles are only lawful when they point to a currently continuing relationship;
- a terminated relationship produces no successor cycle.
- `created_at` isn't stored here, when an recurring assessment event is written, a corresponding `bill_cycles` row is written simultaneously. The timestamp stored on `assessment_event` serves as the `created_at` reference.

---

## XII. Derived State

The following SHALL be derived and SHALL NOT be persisted as canonical obligation truth:

- satisfied;
- outstanding;
- past due;
- visible;
- partial payment;
- amount paid;
- amount outstanding;
- days late;
- overpayment handling;
- any mutable lifecycle flag that can be inferred from immutable events.

### Derived evaluation rules

For one assessment:

```text
paid_amount = sum(authoritative Ledger amounts referenced by PAYMENT events for the same correlation_id)
has_waiver = exists(WAIVED for the same correlation_id)

if paid_amount >= assessed_amount:
    status = SATISFIED
elif has_waiver:
    status = SATISFIED
else:
    status = OUTSTANDING
```

Past due is derived as:

```text
status == OUTSTANDING and canonical_now > due_at
```

---

## XIII. Operational Rules

1. All obligation mutation SHALL occur through the canonical business operations owned by this domain.
2. GET and read-time logic SHALL remain pure.
3. A bill cycle boundary does not itself mutate canonical truth; it only makes a lawful assessment opportunity eligible.
4. Assessment creation must remain idempotent for the same lawful lineage and correlation.
5. A lawful assessment SHALL NOT be deleted, reversed, or retroactively rewritten.
6. Monetary correction after settlement SHALL occur through Ledger, not by editing obligation history.
7. Insurance cancellation or termination prevents future recurring assessments; it does not rewrite prior obligation events.
8. Rent waiver is lawful only for rent assessments.

---

## XIV. Cross-Domain Coordination

Obligations may consume authoritative inputs from:

- Class Configuration, for rent and other class-defined liability terms;
- Store and Entitlements, for insurance coverage lifecycle inputs;
- Ledger, for monetary settlement truth.

Obligations does not own those upstream facts.

Where an upstream domain supplies the lawful inputs for an assessment, Obligations records the liability and its resolution while preserving the upstream lineage.

---

## XV. Amendment

Revisions to this document must:

1. increment the version number;
2. update the Effective Date;
3. maintain consistency with `INV-CORE-000`;
4. maintain consistency with `INV-ARC-015` and `INV-ARC-016`;
5. keep the obligations domain limited to liability existence, recurring progression, and lawful satisfaction.
