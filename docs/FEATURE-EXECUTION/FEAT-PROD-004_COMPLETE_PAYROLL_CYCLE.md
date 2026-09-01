# FEAT-PROD-004: Complete Payroll Cycle

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-004 | 1.0 | 2026-08-30 | N/A | Normative |

---

## I. Purpose

This FEAT is the **canonical class-level payroll-run orchestrator** and the sole coordination point for the economic-cycle boundary defined in `DOM-PROD-001` §XV.

It exists so that a completed payroll run — the moment the class's open economic cycle closes — produces its lawful downstream side effects through a single declared, auditable, idempotent orchestration, rather than through direct domain-to-domain calls (`INV-ARC-021` §V.1–§V.2).

Both payroll execution paths converge on this FEAT:

- manual payroll initiated by the teacher, and
- automatic payroll initiated by a scheduled run.

This FEAT does not itself write `payroll_event` rows; it owns the run identity and the cross-domain choreography. Per-seat settlement writes remain owned by `FEAT-PROD-003`.

---

## II. Execution Context

### 1. Required Inputs

- `ctx`: `CanonicalContext` — carries the class boundary and lawful actor seat
- `run_mechanism`: `TEACHER` | `SYSTEM` — records which path initiated the run
- `idempotency_key`: replay guard for the class-level completion command
- `reference_time_utc`: optional explicit timestamp for deterministic evaluation

### 2. Generated Identity

- `payroll_cycle_id`: a fresh UUID **allocated only for a genuinely new run**. It is the durable economic-period identity for the run and is stamped, unchanged, onto every `payroll` event written during the run.

**Replay resolves before allocation.** The persistent completion anchor (`DOM-PROD-001` §XV; `payroll_cycle_completion`) is consulted first: if this class-level `idempotency_key` already resolves to a completed run, the FEAT returns that run's original `payroll_cycle_id` and performs no downstream work. Only when no completed run resolves does the FEAT allocate a new `payroll_cycle_id`. A replay therefore never allocates a second cycle identity, never re-reads or recaptures the (possibly since-advanced) governing configuration, and never re-invokes settlement, interpretation, or activation.

`payroll_cycle_id` MUST NOT be derived from `idempotency_key`, `correlation_id`, or any per-command replay nonce. See `DOM-PROD-001` §XV.2.

### 3. Canonical Authority

- `ctx.class_id` provides the class isolation boundary.
- `ctx.seat_id` / `ctx.actor_role` establish lawful authority for the run.
- The FEAT MUST fail closed if the initiating actor is not lawful for the class.

---

## III. Orchestration Contract

This FEAT coordinates three domains in a fixed, lawful order. Each cross-domain effect is a declared side effect of this contract, auditable via `request_id` and the originating FEAT code, and idempotent on replay (`INV-ARC-021` §V.8).

### Execution steps

0. **Resolve replay (FIRST).** Consult the persistent completion anchor for `(class_id, idempotency_key)`. If a completed run resolves, return its original `payroll_cycle_id` immediately — before any configuration read, cycle-id allocation, timestamp resolution, eligible-seat query, `reference_configuration` capture, or ITR/CLASS invocation. This step is the sole protection of the historical-configuration seam and MUST precede every other operation.
1. **Open the cycle (new run only).** Confirm the actor is lawful for the class. Allocate a fresh `payroll_cycle_id` (UUID). Consume the caller-supplied lawful closed-cycle window / evaluation time (this FEAT does not derive boundary legality).
2. **Settle the closing cycle (PROD).** For each eligible seat, invoke `FEAT-PROD-003` `record_payroll_event(...)` with `payroll_event_type = payroll`, supplying the run's `payroll_cycle_id`. PROD settles each seat against authoritative productivity facts under the configuration currently governing the closing cycle. The governing configuration is NOT re-read or re-interpreted after this step.
3. **Materialize interpretation (ITR).** Invoke the Interpretation compute + materialize path (`FEAT-ITR-001` and its materialization contract) for the just-closed cycle, passing `class_id` and `payroll_cycle_id`. Interpretation produces one durable, immutable `interpretation_cycle_record` bound permanently to this `payroll_cycle_id` and the economic reference values in effect for the closed cycle (`DOM-ITR-001` §VIII–§IX). Interpretation is read-only over economic truth and MUST NOT mutate PROD, Ledger, or Policy state.
4. **Activate pending next-cycle policy (CLASS).** If the teacher staged an economic-configuration change during the open cycle, invoke the lawful Class-domain transition command (`DOM-CLASS-003`) to activate the pending next-cycle policy transition. Activation is a lawful append-only policy transition (`INV-ARC-016`); it is NEVER performed by a scheduler noticing `effective_at <= now`. If no change is pending, this step is a no-op.
5. **Record completion (LAST before commit).** Write the persistent completion anchor for `(class_id, idempotency_key)` binding it to this run's `payroll_cycle_id`. This is the final step before commit: the anchor means "this entire economic-cycle transition completed", so it MUST NOT be written early as an in-progress marker. Because it is last and shares the one transaction, a completed-run identity survives **iff** settlement, interpretation, and activation all committed.
6. **Commit.** The owning FEAT transaction commits exactly once. On any step failure, the whole run fails closed and no partial cross-domain state — including the completion anchor — is committed, so a retry is a genuinely fresh attempt under the still-current closing-cycle configuration.

### Ordering guarantees

- Interpretation is materialized against the configuration that governed the **closing** cycle, and only after PROD settlement completes.
- The pending policy is activated **after** the closing cycle is settled and interpreted, so the next cycle — not the closing one — is the first to be governed by the new configuration (`INV-ARC-015` §VI.7).

---

## IV. Temporal Rules

- The class-level run uses a single class-local evaluation time resolved once at step 1 and reused for all seats in the run.
- This FEAT does not reinterpret prior payroll boundaries; it consumes PROD's boundary derivation as-is.
- The materialized interpretation record is bound to the closed cycle and is never recomputed by any later run (`DOM-ITR-001` §VII).

---

## V. Invariants

1. `payroll_cycle_id` is generated exactly once per class-level run and stamped identically on every `payroll` event in the run.
2. The FEAT is the sole cross-domain orchestrator for payroll completion; no domain calls Interpretation or Class Configuration directly.
3. Interpretation materialization and pending-policy activation are declared, auditable, idempotent side effects of this FEAT.
4. Configuration governing the closing cycle is never mutated mid-run; the pending policy activates only for the next cycle.
5. The run fails closed; partial cross-domain effects are never committed.
6. Replay under the same `idempotency_key` produces no duplicate settlement, no duplicate interpretation record, and no duplicate policy activation.

---

## VI. Dependencies

- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md`
- `docs/DOMAIN/DOM-ITR-001_INTERPRETATION_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-CLASS-003_ECONOMIC_POLICY.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `docs/SPEC/SPEC-ECON-002_ECONOMIC_POLICY_VISIBILITY_AND_DISCLOSURE.md`
- `app/services/context_resolver.py`
- `docs/SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md`
- `app/utils/canonical_temporal_resolver.py`
