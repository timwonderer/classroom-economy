# V1 to V2 Invariant-Verifier Reconciliation

| Review date | Source | Target | Status |
|---|---|---|---|
| 2026-08-31 | `legacy_v1.10.0` and `main` `app/services/invariant_runner.py` plus six registered checks | V2 Operations correctness evidence | Reconciliation only; no implementation authorized |

## I. Purpose

Record which concepts from the v1 economic invariant checker remain candidates for v2 verification, which legacy assumptions must be discarded, and where each resulting operational signal may be consumed.

## II. Authority

This reconciliation is subordinate to `INV-CORE-000`, `INV-CORE-001`, `INV-ARC-004`, `INV-ARC-009`, `INV-ARC-016`, `DOM-LED-001`, `DOM-OPS-001`, and the applicable v2 FEAT specifications. V1 code is prior art only and has no authority over v2 tables, scope, or semantics.

## III. Common V2 Rules

- Checks must be read-only, deterministic, and independently failure-isolated.
- A completed check with a proven violation is `FAIL + KNOWN`.
- A check that cannot execute or establish a result is `FAIL + UNAVAILABLE` or `UNKNOWN + UNAVAILABLE`, according to the external observation contract; it is not proof of an invariant violation.
- `UNVERIFIED` audit lineage is not `INVALID` and is not an incident.
- `INVALID` audit lineage is consumed from the canonical audit verifier; it must not be reimplemented by this checker.
- No external result may contain `class_id`, `seat_id`, `user_id`, join codes, financial amounts, row IDs, raw diagnostics, or per-tenant counts.
- A system-level verifier requires explicit lawful authority to enumerate and evaluate class scopes. Global SQL aggregation is not a substitute for that authority.

## IV. Prior V2 Decisions Located in `docs/`

This reconciliation is not the first v2 discussion of invariant verification. Existing documentation establishes the following prior material:

1. `docs/TRACKING/V2_Full_compliance_migration_plan.md` assigns the invariant runner to Operations and describes scheduled invariant checks emitting `InvariantRunEvent`, with failures creating `IncidentEvent`.
2. `docs/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md` records violation detection as Operations identifying an unbalanced Ledger transaction.
3. `docs/DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md` defines correctness as distinct from liveness/readiness, prohibits auto-fixing, requires repeated failures to remain distinct events, and says status is derived from active incidents and health-check events.
4. `docs/TRACKING/V2_BUILD_SPEC/V2_BANKING_LEDGER_SETTLEMENT_PLAN.md` defines the deferred v2 Ledger reconciliation invariants:
   - `available_balance_cents = current_balance_cents + sum(pending non-void amount_cents)` within `(class_id, seat_id, account_type)`;
   - `current_balance_cents = sum(posted amount_cents)` through the settlement cutoff.
   It explicitly replaces `join_code`/`student_id` scope with `class_id` + `seat_id` and treats the balance table as a projection/cache.
5. `docs/ops/audits/PROD_AUDIT_2026-07-01.md` records that production monitoring already queries `/health`, `/health/deep`, and `/health/invariants`, but this is historical operational evidence, not proof that the current endpoint is v2-compliant.
6. Archived v1 material confirms the original checker was the six-check runner found on `legacy_v1.10.0` and `main`; archived security/audit documents discuss economic invariant risk but do not define a newer canonical checker contract.
7. `docs/FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md` explicitly preserves the class-scoped zero-sum transfer invariant and non-negative checking rule for the v2 posting flow.
8. `docs/TRACKING/V2_BUILD_SPEC/V2_STUDENT_IDENTITY_ARCHITECTURE.md` confirms that economic state attaches to `seat_id`; it does not define a verifier implementation.

These documents settle several v2 economic truths, especially class/seat scope, zero-sum transfers, posted-balance reconstruction, and Operations ownership. They do not provide a complete current v2 economic verifier contract. The compliance plan is also aspirational: the current active tree still contains the legacy `invariant_runner.py` schema and its scheduled task does not create `InvariantRunEvent` or `IncidentEvent` records as described there. Archived material adds useful concepts and risk history, but no hidden settled checker supersedes this reconciliation.

## V. Reconciliation Table

| V1 check / proposed v2 check | V1 concept | Legacy dependencies/risks | V2 exact contract and proof | Scope/execution gate | Cost/freshness | Destinations |
|---|---|---|---|---|---|---|
| `ledger_balance_consistency` → `posted_balance_reconciliation` | Stored balance agrees with ledger history | `balance_cache`, `student_id`, `join_code`, legacy transaction table; global/tenant assumptions | **Runtime verifier.** For each `(class_id, seat_id, account_type)`, compare `posted_balance_cents` with the `SUM(amount_cents)` of canonical posted transactions whose `posting_sequence` is within `reconciled_through_posting_sequence`, exactly as declared by `DOM-LED-001` | One class-bound execution; snapshot is a rebuildable projection and must be checked against canonical `ledger_transaction` history | Expensive; settlement/reconciliation cadence | Grafana; DOM-OPS correctness; external aggregate correctness state |
| `balance_rules` → `available_balance_constraint` | Posted plus pending balance arithmetic | `balance_cache`, `student_id`, `join_code`; legacy overdraft-policy coupling | **Runtime verifier for arithmetic only.** Compare available balance with `posted_balance_cents + pending non-void Ledger delta` per `(class_id, seat_id, account_type)`. Do not evaluate whether the result is economically acceptable; solvency/overdraft policy belongs elsewhere | One class-bound execution; exact available-balance read contract must use the canonical Ledger projection and history | Moderate; post-settlement or policy-change cadence | Grafana; DOM-OPS correctness; external bounded aggregate if launch-critical |
| `money_supply_integrity` → `internal_transfer_zero_sum` | Internal transfer legs conserve value | Global sums; per-class `join_code`; description matching; reversal linkage | **Runtime verifier.** For each class-scoped internal-transfer `correlation_id`, consume a Ledger-owned read-only verification result and verify exactly two same-seat legs, one debit and one credit across permitted accounts, equal absolute `amount_cents`, signed total zero, and atomic/posting consistency. `correlation_id` is the canonical transfer-operation identity; it MUST NOT be reused for another transfer pair. No description matching, `id`, or `original_transaction_id` grouping. | One class-bound execution; Ledger-owned `verify_transfer(class_id, correlation_id)` surface | Moderate; after transfer batches or scheduled reconciliation | Grafana; DOM-OPS correctness; external aggregate state |
| `money_supply_integrity` → `class_posted_conservation` | Aggregate monetary conservation | Global supply totals and per-class legacy metrics; undefined money-supply assumptions | **Retired — settled.** Canonical Ledger semantics permit lawful value creation and destruction through domain-authorized credits and debits. No class-wide conserved monetary quantity or opening-balance issuance equation is defined. Internal transfer conservation is verified separately by `internal_transfer_zero_sum`. | No periodic verifier; no class-wide monetary conservation claim | No runtime scan; doctrine/migration evidence only | Not external; transfer-specific correctness remains separately observable |
| `transaction_state_validity` | Every transaction has a lawful lifecycle state | Legacy stored-status assumptions; current runtime still reads and mutates `status` | **Retired — settled.** Do not port the v1 stored-status scan into the v2 runner. `DOM-LED-001` defines posting as reconciliation semantics and corrections as append-only Ledger events. The current `status` field and its runtime transitions are Ledger migration debt, not an Operations verifier contract. | Ledger migration/runtime slice must replace stored lifecycle state with immutable events, `posting_sequence`, and reconciliation semantics | No periodic verifier; migration/conformance evidence only | Grafana/schema audit; not external by default |
| `temporal_integrity` → `ledger_temporal_order` | Posted time is not before creation time | Legacy transaction columns and timestamp semantics | **Retired — settled.** Posting order is canonically represented by immutable `posting_sequence`. Existing timestamps retain occurrence, business, settlement, and provenance meanings, but no authoritative cross-field ordering inequality is defined. UTC storage, canonical temporal evaluation, and timestamp assignment remain Ledger write-path/schema/migration responsibilities. | No periodic verifier; preserve `posting_sequence` as the only posted-ledger ordering boundary | No runtime scan; migration/conformance evidence only | Grafana/schema audit; not external by default |
| `idempotency_key_uniqueness` | Replay keys do not duplicate transaction effects | Global transaction table and legacy uniqueness assumptions | **Structural proof — settled contract.** Ledger command reservation identity is `(class_id, feat_code, idempotency_key)`. Replay fingerprints are compared separately; `type`, target, actor, account, and amount do not create a new reservation. Reservations are permanent across VOID/reversal, and one reservation may produce multiple atomic Ledger effects. Verify the structural enforcement and replay behavior; do not run a periodic duplicate scan. | Physical enforcement remains deferred to schema design; all canonical Ledger command paths, including transfers, require reservations unless an explicit Ledger exception is authorized | Low structural/conformance check; event-driven breach evidence | Grafana/DOM-OPS if the structural guarantee is breached; external bounded aggregate only |
| audit lineage verifier | HMAC chain continuity and protected-row lawful existence | Not part of v1 economic checker; current v2 implementation already exists | Consume the canonical verifier result; do not duplicate the HMAC walk | Independent system authority already defined by `DOM-OPS-002`; preserve four lineage states | Existing verifier cadence | Grafana; DOM-OPS health; external bounded correctness state |

## VI. Runner Pattern Disposition

The v1 runner's reusable mechanics are:

1. register independent checks;
2. execute each check read-only;
3. isolate exceptions;
4. return structured aggregate results;
5. keep diagnostic detail out of external responses.

The v1 runner's semantic behavior is not portable: it converts every exception to `FAIL`, assumes legacy schemas, performs global aggregates, and exposes `per_class_supply` in a result path. A v2 runner must preserve the mechanics while deriving every check from current v2 authority and the observation-state contract.

## VII. Proposed V2 Result Boundary

Internal result:

```json
{
  "check": "ledger_integrity",
  "status": "PASS",
  "failure_count": 0,
  "checked_at": "...",
  "duration_ms": 0
}
```

External adapter result:

```json
{
  "verification": "KNOWN",
  "checked_at": "...",
  "checks": {
    "ledger_integrity": "PASS",
  }
}
```

The external adapter must omit tenant dimensions, monetary values, row identities, raw failure details, and class-level breakdowns. Missing or stale verifier output must not be treated as `PASS`.

## VIII. Conceptual Reconciliation Closure and Remaining Implementation Decisions

The v1-to-v2 semantic reconciliation is closed. The system-verifier
coordination authority and one-class-per-execution rule were settled by
`DOM-OPS-001` version 2.3. Ledger proof-interface boundaries are defined by
`SPEC-LED-001`, and command-level idempotency enforcement is defined by
`SPEC-LED-002`.

The remaining decisions are implementation-facing:

1. Implement and test the Ledger proof surfaces defined by `SPEC-LED-001`.
2. Implement the physical command-reservation structure defined by `SPEC-LED-002`.
3. Define freshness classes and thresholds for each proof and canonical verifier result.
4. Define the DOM-OPS aggregate mapping for `PASS`, proven `FAIL`, `UNAVAILABLE`, stale evidence, dispatch failure, and conflicting evidence.
5. Define the closed capability-to-evidence-source registry used by external status observation and publication.

Items 3–5 require Operations owner policy where thresholds, public capability
semantics, or publication eligibility are not already defined by the governing
documents. No v2 invariant-checker implementation, external adapter, or GCP
persistence should begin until those implementation contracts are resolved.

## IX. Amendment

Revisions require updating the review date and disposition table, preserving v2 authority over all check semantics, and recording the governing document for each adopted verifier.
