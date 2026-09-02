# FEAT-OBL-004: Insurance Policy Purchase / Enrollment

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-OBL-004 | 0.1 (DRAFT) | 2026-09-01 | N/A | Normative (proposed) |

## I. Purpose

Define the single lawful path by which a student enters into (purchases) an
insurance policy for the current class.

The user action is **creating and immediately satisfying the first premium
obligation**. The insurance entitlement grant is the *consequence* of successful
satisfaction, not the defining act — which is why this FEAT lives in the
Obligations family and not in Store and Entitlements. Placing it under STOR would
repeat, at a subtler level, the category error of treating insurance as a store
product.

The FEAT's logical unit of work is larger than "charge and grant": a successful
purchase also **establishes the recurring billing-cycle lineage** so that future
premiums have a lawful home. Selling coverage without establishing its billing
lineage is a partial, unlawful outcome.

## II. Authority

This FEAT is the **sole lawful orchestrator for insurance coverage acquisition**.

It coordinates, but does not own, the following domain state:

- **Policies** — owns the immutable `insurance_policies` definition (resolved, never mutated here);
- **Obligations** — owns the premium assessment, its satisfaction, and the bill-cycle lineage;
- **Ledger** — owns the monetary posting for the premium payment;
- **Store and Entitlements** — owns the `INSURANCE` entitlement grant.

Cross-domain composition is lawful only at this FEAT layer (INV-ARC-021). Each
mutation occurs through the owning domain's explicit command (INV-ARC-006); this
FEAT does not write another domain's tables directly.

This FEAT is **not** a branch of FEAT-STOR-001. FEAT-STOR-001 remains the lawful
purchase path for actual Store products (`store_products`) only; on adoption of
this spec, FEAT-STOR-001 §II is amended to drop its claim to be the sole writer
of *all* `PURCHASE` grants, and its INSURANCE branch and StoreProduct indirection
are removed.

## III. Dependencies

- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
- `DOM-POL-001_POLICIES_DOMAIN.md`
- `DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `DOM-LED-001_LEDGER_DOMAIN.md`
- `FEAT-OBLI-001_ASSESS_OBLIGATION.md` (premium assessment)
- `FEAT-OBL-003_SATISFY_OBLIGATION.md` (premium satisfaction via payment)
- `FEAT-OBL-002_ADVANCE_BILL_CYCLE.md` (bill-cycle lineage)
- `FEAT-LED-000_CANONICAL_MONETARY_RESOLUTION_WORKFLOW.md`, `FEAT-LED-001_POST_LEDGER_TRANSACTION.md`
- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`, `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`, `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`

## IV. Required Execution Context

The caller SHALL resolve canonical request context before entering this FEAT.

Required canonical context:

- `user_id`
- `class_id`
- `seat_id` — the purchasing student seat
- `actor_role = student`

This FEAT is **student self-purchase only**: `actor_seat_id == target_seat_id ==
seat_id`. It SHALL NOT expose an alternate actor mode (e.g. a teacher enrolling a
student on their behalf). Actor identity is class-local via `seat_id`, and
capability decisions are explicit and request-scoped (INV-ARC-003, INV-ARC-019);
teacher-directed enrollment, if ever wanted, is a materially different authority
path and SHALL be given its own contract, never smuggled in here as an alternate
actor.

The FEAT SHALL NOT reconstruct authority from route-local lookups, display
labels, join codes, or block names.

## V. Required Inputs

- canonical request context;
- `policy_uuid` — exact immutable insurance policy locator; **resolved only under the supplied `class_id`** (no global lookup establishes runtime truth — INV-ARC-002 / INV-CORE-000);
- `idempotency_key` — replay guard governing the **entire logical acquisition** (assessment + satisfaction + grant + bill-cycle establishment), not merely the Ledger posting.

The FEAT generates or resolves:

- `correlation_id` — one identifier binding the full purchase lifecycle across domains;
- `internal_ref` — the stable lineage key for this seat's continuing coverage relationship under this policy, reused by every future recurring premium;
- canonical transaction timestamp through the temporal model.

## VI. The Immutable Contract Reference (no snapshot)

`insurance_policies` rows are immutable: editing a policy produces a **new**
`policy_uuid`. Therefore `policy_uuid` **is** the frozen contract. Every fact this
FEAT writes — the premium assessment, the entitlement grant, and the bill-cycle
row — SHALL record the exact `policy_uuid` in force at purchase. Policy terms are
retrieved later by resolving that `policy_uuid`, never by copying terms forward.

This FEAT SHALL NOT snapshot policy economics (premium, payout_multiple,
reimbursement_percentage, claim_window_days, coverage period, etc.) into the
entitlement payload or anywhere else. Duplicating policy rules into the
entitlement payload is prohibited by DOM-STORE-001 §VII.A.

## VII. Read-Only Validation Phase

All validation SHALL complete before any mutation begins.

1. **Context** — the actor is a lawful student seat for `class_id`; `seat_id` exists within the class boundary.
2. **Feature enablement** — the insurance capability is enabled for `class_id` (Class Configuration).
3. **Policy resolution** — `policy_uuid` resolves to an `insurance_policies` row **in this class**, and its `availability_state == IN_USE`. A `HIDDEN` or `RETIRED` definition SHALL be rejected for new coverage (it is winding down or removed).
4. **Coverage eligibility.** Two distinct rules, evaluated from canonical entitlement history (never a mutable flag):
   - **Hard invariant (always enforced):** a seat MUST NOT acquire a second *concurrently effective* entitlement referencing the **same** `policy_uuid`. Purchasing the exact same immutable contract twice would create duplicate recurring assessments and a duplicate entitlement lineage for one policy, and SHALL fail deterministically (`POLICY_ALREADY_HELD`). A retry with the same `idempotency_key` is not a duplicate — it returns the original result (§X).
   - **Product-rule (not decided by this FEAT):** whether a seat may hold concurrently effective coverage across **different** `policy_uuid`s is governed by the Insurance policy contract, not this FEAT. FEAT-OBL-004 SHALL NOT invent a global "one insurance per seat" rule (a future replacement/upgrade model may intentionally let a new policy be established while the old terminates at a defined boundary).

Affordability is NOT pre-decided here as truth; the Ledger resolution phase
(§VIII.3) is the sole authority on whether the premium can be paid.

## VIII. Mutation Phase

All coordinated mutations SHALL occur within **one lawful transaction boundary**
and are governed by the single `idempotency_key`. The success contract is:

```
resolve policy
  → establish cycle-1 identity
  → assess premium #1 against cycle 1
  → satisfy premium #1
  → grant entitlement
  → record next assessment boundary
  → commit
```

A failure at any step before commit SHALL roll back **all** of the above; no
partial outcome (e.g. a paid premium with no coverage, or coverage with no
recurring billing lineage) may persist.

Premium #1 is **not** a pre-cycle enrollment fee — it is the assessment **for
bill cycle 1**. The cycle-1 identity therefore SHALL exist before the assessment
is written (so the assessment can carry its `bill_cycle_id`), even though all
steps remain in one atomic transaction.

### 1. Establish cycle-1 identity (genesis)

Establish the genesis bill-cycle row for this coverage lineage through the
Obligations **`establish_bill_cycle`** genesis command:

- bound to `internal_ref` (§V), carrying the insurance `policy_uuid`; the command produces `cycle_number = 1` (not caller-selected), with precondition that no prior cycle exists for the lineage.

Genesis is distinct from advancement: FEAT-OBL-002 (§I, §IV.2) *advances* an
existing cycle to its **successor** and requires a current cycle at an
advancement boundary; it does not define initial creation. This FEAT SHALL NOT
rely on "advance" semantics to mean "create the first cycle." (See §XIII.5 —
`establish_bill_cycle` is introduced and rent genesis migrated to it in this same
arc; FEAT-OBL-002 stays advancement-only.)

### 2. Assess the first premium obligation (against cycle 1)

Through the lawful Obligations assessment command (FEAT-OBLI-001), write the
single `ASSESSMENT` event for premium #1:

- `seat_id` = purchasing seat;
- `class_id` = canonical class;
- `internal_ref` = the coverage lineage key (§V);
- `obligation_type = INSURANCE_PREMIUM`;
- `policy_uuid` = the resolved insurance policy locator;
- `bill_cycle_id` = the cycle-1 identity established in §VIII.1;
- `due_at` = the contractual first-premium boundary, derived through the canonical temporal model.

### 3. Satisfy the premium obligation (Ledger payment)

Through the lawful Obligations satisfaction-by-payment command (FEAT-OBL-003),
which coordinates the Ledger posting (FEAT-LED-000 → FEAT-LED-001):

- the intended plan is a premium debit against the student's account;
- Ledger MAY accept, lawfully transform (e.g. configured overdraft/recovery), or **deny** the plan;
- a **denied** plan SHALL abort the entire purchase with no assessment, grant, or bill cycle persisted (`INSUFFICIENT_FUNDS`);
- the resulting `PAYMENT` event references the lawful `ledger_transaction_id`.

Insurance premiums are not waivable (`WAIVED` is rent-only, DOM-OBL-001 §VII.1).

### 4. Grant the INSURANCE entitlement

Write one `entitlement_events` row through the lawful Store-and-Entitlements grant
path for a user-initiated purchase:

- `class_id` = canonical class;
- `target_seat_id` = purchasing seat;
- `actor_seat_id` = purchasing seat;
- `product_id` / policy reference = the insurance `policy_uuid` (the immutable contract reference — §VI);
- `entitlement_type = INSURANCE`;
- `acquisition_type = PURCHASE`;
- `event_type = GRANTED`;
- `correlation_id` = purchase lifecycle correlation;
- `timestamp` = canonical transaction timestamp;
- `payload` = only the minimal type-specific facts required to interpret the grant; SHALL NOT duplicate monetary truth, policy rules, or derived balances.

This is `acquisition_type = PURCHASE`, so FEAT-STOR-004 (teacher direct grant,
`acquisition_type = GRANT`) is NOT the lawful writer.

### 5. Record the next assessment boundary

Record, on the cycle-1 lineage (§VIII.1), the boundary at which the next
recurring premium becomes due, so recurring premiums have a lawful home:

- `next_assessment_at` SHALL be derived from the **policy-defined canonical renewal/charge cadence**, read from the immutable `insurance_policies` definition through the governing Policies contract — authoritative cadence state belongs to the owning Policies domain and is consumed here, never recomputed from an entitlement field or a billing-cycle convention (INV-ARC-009).
- The date derivation SHALL go through canonical temporal evaluation, not raw date arithmetic (INV-ARC-015).
- This spec does NOT name a concrete policy field (e.g. `charge_frequency`) as the cadence authority; DOM-POL does not currently designate one. The concrete field is bound only once DOM-POL (or DOM-POL-001A) establishes it.

This lineage is what later recurring premiums advance (FEAT-OBL-002), and what a
lawful **insurance cancellation** later terminates by writing a terminal cycle
with `assessment_at = NULL` (DOM-OBL-001 §VII.2, §IX.7). This FEAT does not depend
on the cancellation contract; it only establishes the lineage cancellation acts
upon.

`bill_cycles` already serves "continuing obligation-producing relationships"
generally (DOM-POL-001A §94); this FEAT uses it for per-seat insurance premium
recurrence, distinguished by `internal_ref` and `obligation_type =
INSURANCE_PREMIUM`. Bill cycles remain seat/class-agnostic in their own columns;
the seat/class binding lives on the `assessment_events` they drive.

### 6. Commit

Commit the single transaction. On commit, all of §VIII.1–5 exist; before commit,
none do.

## IX. Lawful Postconditions

On success:

1. exactly one `INSURANCE_PREMIUM` `ASSESSMENT` exists for premium #1, carrying `policy_uuid`;
2. exactly one `PAYMENT` satisfies it, referencing the lawful Ledger transaction;
3. exactly one `INSURANCE` / `PURCHASE` / `GRANTED` entitlement event exists, referencing `policy_uuid`;
4. a `bill_cycles` lineage exists to drive recurring premiums;
5. every written fact carries the same `policy_uuid`; no policy terms are snapshotted anywhere.

## X. Idempotency

The single `idempotency_key` SHALL protect the entire acquisition. A replay of the
same lawful request SHALL NOT create a second assessment, a second Ledger payment,
a second entitlement grant, or a second bill-cycle lineage; it SHALL return or
reconstruct the original result. Idempotency applies to entitlement creation and
obligation transitions in addition to the Ledger entry (FEAT-CORE-000 §3).

## XI. Non-Refundability

Insurance coverage is contractually non-refundable after lawful purchase. Any
generic purchase-reversal path SHALL reject insurance (consistent with
FEAT-STOR-001 §VIII). Lawful *cancellation* — which stops future premiums and
resolves the entitlement to EXPIRED/REVOKED at cycle end, preserving benefits
until then — is a distinct action under a **lawful insurance cancellation
authority**, not a reversal of this one. This FEAT does not normatively depend on
that cancellation contract; it only establishes the recurring lineage cancellation
later acts upon.

## XII. Failure Contract

Representative failures (all leave zero mutations):

- `INSURANCE_FEATURE_DISABLED`
- `POLICY_NOT_FOUND` (not in class, or bad locator)
- `INSURANCE_NOT_AVAILABLE_FOR_NEW_COVERAGE` (definition not `IN_USE`)
- `POLICY_ALREADY_HELD` (seat already holds a concurrently effective grant for the **same** `policy_uuid` — hard invariant, §VII.4)
- `INSUFFICIENT_FUNDS` (Ledger denied the premium plan)
- `CROSS_DOMAIN_FAILURE`

## XIII. Consequential Amendments (same architectural arc)

Adopting this FEAT requires, in the same arc, to avoid leaving contradictory contracts:

1. **FEAT-STOR-001 §II** — narrow "sole writer of `PURCHASE` grants" to *Store products*; remove the INSURANCE branch and StoreProduct indirection from `execute_store_purchase`.
2. **FEAT-STOR-003 (claims)** — resolve policy terms through the immutable `policy_uuid` rather than reading a duplicated snapshot from the entitlement payload; retire the frozen-contract payload machinery (`build_frozen_contract` / `frozen_insurance_contract` / `insurance_contract_freeze`).
3. **DOM-OBL-001** — align the bill-cycle *vocabulary* (§V.7, §VII.2), which is still worded rent-only, with the already-general schema authority (`bill_cycles` serves "continuing obligation-producing relationships" per DOM-POL-001A §94) so per-seat insurance premium recurrence is explicitly in scope.
4. **MAP-CORE-001** — record the insurance-purchase capability under FEAT-OBL-004 (the map currently predates the numbering).
5. **Bill-cycle genesis is a distinct Obligations command.** Bill-cycle *genesis* and bill-cycle *advancement* are separate Obligations mutations — genesis establishes the first lawful cycle where none exists (`nothing → cycle 1`); advancement creates a successor from an existing lawful current cycle (`cycle N → cycle N+1`). These are different state transitions and SHALL NOT be conflated under one "advance" verb (INV-ARC-006, INV-ARC-009). Therefore:
   - a new Obligations-domain **genesis command** (`establish_bill_cycle`) SHALL be introduced. Precondition: no prior cycle exists for the lineage. Result: `cycle_number = 1`. `cycle_number` is **not** caller-selected — genesis inherently produces cycle 1.
   - **FEAT-OBL-002 remains advancement-only.** Its precondition is an existing lawful current cycle; it derives `next_cycle_number = current + 1` from authoritative Obligations state rather than accepting an arbitrary successor number.
   - existing rent genesis (`reconcile_rent_feat` calling `execute_advance_bill_cycle(cycle_number=1)`) SHALL migrate to `establish_bill_cycle` **in this same arc** — otherwise two genesis semantics for one domain object coexist. FEAT-OBL-004 §VIII.1 invokes `establish_bill_cycle`.
   - the genesis command does not require its own user-facing FEAT number: FEAT-OBL-004 orchestrates it, and rent invokes it through the existing FEAT that lawfully owns rent reconciliation. The new thing is the explicit domain command, not another FEAT wrapper.

## XIV. Amendment

Revisions must remain consistent with `DOM-OBL-001`, `DOM-POL-001`,
`DOM-STORE-001`, `DOM-LED-001`, `FEAT-CORE-000`, and the governing FEAT, temporal,
and cross-domain coordination invariants.
