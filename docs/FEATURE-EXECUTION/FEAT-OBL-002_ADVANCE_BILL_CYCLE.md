# FEAT-OBL-002: Advance Bill Cycle

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-OBL-002 | 1.0 | 2026-07-24 | N/A | Normative |

---

## I. Purpose

This FEAT advances a recurring obligation source to its next lawful bill cycle.

The bill cycle is identity-blind temporal reminder state. It does not determine business meaning, amount, class, seat, or contract authority. It only records that a continuing internal reference must be reconsidered at a lawful boundary.

This FEAT is used for recurring rent and recurring insurance premium progression when the lawful upstream authority permits another cycle.

---

## II. Authority

Obligations owns:

- `bill_cycles`
- recurring progression legality for obligation sources

Class Configuration owns:

- rent policy terms
- insurance policy terms
- effective version lineage

Store and Entitlements owns:

- insurance entitlement / coverage lifecycle inputs

Ledger owns:

- monetary truth

This FEAT SHALL NOT decide business meaning from labels or mutate upstream contractual truth.

---

## III. Required Context

Required canonical context:

- `class_id`
- `internal_ref`
- `seat_id` when the source is seat-scoped
- `actor_seat_id`
- `current_cycle_number`
- `next_assessment_at`
- `idempotency_key`

The lawful caller SHALL provide the upstream authority reference and version snapshot needed to validate the successor cycle.

---

## IV. Orchestration Logic

### 1. Verification

1. Verify the recurring source still lawfully exists.
2. Verify the current cycle has reached the lawful advancement boundary.
3. Verify the successor cycle is permitted by the authoritative source.
4. Resolve the lawful version snapshot that governs the successor cycle.

### 2. Mutation

1. Create the successor `bill_cycles` row.
2. Record the next assessment boundary for the same `internal_ref`.
3. Emit any resulting lawful obligation assessment through the canonical obligations FEAT surface.

### 3. Terminal case

If the authoritative source has terminated, no successor cycle is created.

---

## V. Invariants

1. `bill_cycles` SHALL NOT store monetary amount.
2. `bill_cycles` SHALL NOT store business meaning for the source.
3. `bill_cycles` SHALL NOT store class/seat identity when that identity belongs upstream.
4. A terminated recurring relationship produces no successor cycle.
5. Bill cycle advancement MUST be idempotent for the same lawful lineage and boundary.

---

## VI. Dependencies

- `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
- `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-OBLI-001_ASSESS_OBLIGATION.md`
