# FEAT-OBL-003: Satisfy Obligation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-OBL-003 | 1.0 | 2026-07-24 | N/A | Normative |

---

## I. Purpose

This FEAT records lawful satisfaction of an assessed obligation.

The satisfaction may occur through:

- payment, with a Ledger transaction reference; or
- rent waiver, with no Ledger movement.

This FEAT does not create the liability. It closes or partially closes an existing liability through canonical obligation history.

---

## II. Authority

Obligations owns:

- `assessment_events` obligation event rows for `PAYMENT` and `WAIVED`
- satisfaction legality
- rent waiver legality

Ledger owns:

- monetary movement truth for `PAYMENT`

Class Configuration owns:

- source terms that make the satisfaction lawful

---

## III. Required Context

Required canonical context:

- `class_id`
- `seat_id`
- `assessment_id`
- `correlation_id`
- `method` = `PAYMENT` or `WAIVED`
- `actor_seat_id`
- `idempotency_key`

For `PAYMENT`, the caller SHALL also provide the lawful `ledger_transaction_id`.

---

## IV. Orchestration Logic

### 1. Verification

1. Verify the assessment exists.
2. Verify the supplied `correlation_id` matches the assessment lineage.
3. Verify the requested satisfaction method is lawful for the assessment type.
4. For `PAYMENT`, verify the Ledger transaction is lawful and belongs to the same class/seat boundary.
5. For `WAIVED`, verify the assessment is rent and the caller has waiver authority.

### 2. Mutation

1. Create the immutable obligation event row with `event_type = PAYMENT` or `event_type = WAIVED`.
2. For `PAYMENT`, reference the Ledger transaction.
3. For `WAIVED`, record no Ledger movement.

### 3. Derived state

The FEAT SHALL NOT persist:

- paid/unpaid
- satisfied/outstanding
- past due
- remaining amount

Those states are projections over immutable assessment and satisfaction history.

---

## V. Invariants

1. An assessment MAY have multiple `PAYMENT` events.
2. `WAIVED` is rent-only.
3. `WAIVED` SHALL NOT create a Ledger transaction.
4. Satisfaction events MUST be immutable.
5. Monetary correction after settlement belongs to Ledger, not to obligation history.

---

## VI. Dependencies

- `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md`
