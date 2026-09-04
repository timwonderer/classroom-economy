# Ledger Service and FEAT Consolidation Map

| Reference | Status | Date |
|---|---|---|
| TRACKING-LED-004 | Working inventory | 2026-09-04 |

## Purpose

This inventory separates Ledger-owned domain services from FEAT orchestration.
It is an implementation map, not a new Ledger authority. `DOM-LED-001`,
`FEAT-LED-*`, `SPEC-LED-001`, and `SPEC-LED-002` remain governing.

## Target Ledger service set

### 1. `ledger_command_service`

Owns command reservation creation, replay fingerprint comparison, effect
linkage, and atomic one-to-many command outcomes.

### 2. `ledger_posting_service`

Owns immutable transaction-effect creation and canonical class-scoped
`posting_sequence` assignment. It is the only mutation path for Ledger effects.

### 3. `ledger_settlement_service`

Owns seat-scoped settlement, deterministic account-row locking, normalized
snapshot updates, and atomic reconciliation cursors.

### 4. `ledger_balance_query_service`

Owns normal posted/available balance reads and the read-only reconstruction
surfaces required by `SPEC-LED-001`. Normal reads may use projections;
reconstruction reads may not.

### 5. `ledger_correction_service`

Owns append-only void/reversal creation and correction linkage. It never mutates
the original financial fact as a substitute for a correction.

### 6. `ledger_transfer_service`

Owns one-reservation/two-effect internal checking-savings transfers and the
Ledger-owned `verify_transfer(class_id, correlation_id)` proof surface.

### 7. `ledger_provenance_query_service`

Owns bounded, read-only Ledger projections consumed by Interpretation and other
domains. These adapters must not become mutation or verification authorities.

### 8. `ledger_interest_service` and `ledger_fee_service`

Own Ledger economic commands whose policy resolution is already defined by the
Ledger/economic contracts. They delegate plan resolution and posting to the
canonical Ledger boundaries and do not define new policy.

## Target Ledger FEAT set

| FEAT | Responsibility | Target service dependencies |
|---|---|---|
| `FEAT-LED-000` | Resolve an intended monetary plan under canonical policy | balance query, posting/transfer |
| `FEAT-LED-001` | Commit a resolved Ledger command atomically | command, posting |
| `FEAT-LED-002` | Create an append-only correction/reversal | command, correction, posting |
| `FEAT-LED-003` | Execute one class/seat settlement boundary | settlement |
| `FEAT-LED-004` | Execute authorized payroll Ledger effects | command, posting, settlement |

`transfer_feat.py` should remain a FEAT entrypoint only; transfer mechanics
belong in `ledger_transfer_service`. Payroll cycle orchestration remains in its
own FEAT/domain boundary and calls Ledger services for monetary effects.

## Current transitional locations

- `app/services/identity_service.py`: scheduled/system class transitions now use
  the Identity-owned canonical teacher-seat resolution operation. The former
  Ledger façade no longer owns identity lookup. Economic interest and fee
  commands have been moved to their own Ledger services.
- `app/utils/banking.py`: deprecated import surface only; no settlement
  implementation remains here.
- `app/utils/transaction_idempotency.py`: low-level fingerprint/storage helper;
  command-service callers own the Ledger command boundary.
- `app/services/balance_service.py`: non-Ledger batch adapter consuming the
  canonical balance-query service.

## Consolidation progress

- `app/services/ledger_transfer_service.py`: canonical transfer service
  implementation and entrypoint; transfer creation and proof are physically
  owned here.
- `app/services/ledger_settlement_service.py`: canonical settlement service
  implementation and entrypoint; posting-sequence allocation and normalized
  snapshot advancement are physically owned here.
- `app/services/ledger_balance_query_service.py`: canonical balance/proof query
  implementation and service boundary; normal and reconstruction reads are
  physically owned here.
- `app/services/ledger_command_service.py`: canonical command reservation and
  replay entrypoint; persistence details remain isolated during extraction.
- `app/services/ledger_posting_service.py`: canonical effect-creation
  implementation and entrypoint; ordinary and command-reserved effects are
  physically owned here.
- `app/services/ledger_correction_service.py`: canonical append-only correction
  entrypoint.
- `app/services/ledger_provenance_query_service.py`: canonical bounded,
  read-only Interpretation provenance projections.

Interpretation consumers have been migrated to the provenance service, and the
former mixed-module provenance implementation has been removed.

Migrated FEAT callers now use the balance, posting, transfer, settlement, and
correction boundaries directly where their dependencies are unambiguous.
- `app/feats/transfer_feat.py`: now consumes the canonical transfer service
  entrypoint and contains only FEAT result shaping.

## Consolidation rules

1. FEATs orchestrate one command boundary; they do not contain Ledger SQL.
2. Ledger services own Ledger reads and mutations according to `DOM-LED-001`.
3. Operations consumes proof results and never reconstructs Ledger state.
4. Cross-domain provenance projections remain read-only and bounded.
5. No service may retain a legacy split-snapshot or mutable-status authority
   after the canonical settlement cutover.
6. Refactoring is mechanical only unless a move changes authority, economic
   behavior, privacy, or security; those cases require review.

## Next implementation tranche

1. Add service-contract tests for the extracted command, posting, correction,
   transfer, settlement, balance, and provenance surfaces.
2. Implemented the one-to-many command-reservation API required by bulk Ledger
   commands (including admin adjustments): one command fingerprint, one
   permanent reservation, multiple structurally linked effects, and atomic
   replay reconstruction. Do not emulate this with repeated single-effect
   reservations.
3. Re-run the migration and focused FEAT/Interpretation guardrails before
   considering the consolidation complete.

This map does not authorize new economic rules or additional FEAT codes.
