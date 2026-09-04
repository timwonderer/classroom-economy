# SPEC-LED-002: Command Idempotency Reservation and Structural Enforcement

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-LED-002 | 1.0 | 2026-09-01 | New | Normative |

## I. Purpose

Define the physical enforcement contract for command-scoped Ledger idempotency
established by `DOM-LED-001`. This specification defines reservation identity,
replay comparison, reservation-to-effect ownership, concurrency, and historical
classification. It does not authorize a migration or runtime implementation.

## II. Authority and Scope

This specification is subordinate to `DOM-LED-001` and applies to canonical
Ledger command paths that create one or more monetary effects. It does not make
Operations responsible for duplicate detection or Ledger invariant
reconstruction.

## III. Reservation Model

### 3.1 Reservation identity

The unique command reservation identity is:

```text
(class_id, feat_code, idempotency_key)
```

`class_id` is the authority boundary. `feat_code` identifies the originating
command family. `idempotency_key` identifies the caller's command within that
family. Effect attributes—including target, actor, account, amount, and
transaction `type`—MUST NOT expand the reservation namespace.

### 3.2 Reservation record

The Ledger-owned reservation structure MUST provide, at minimum:

- stable reservation primary key;
- `class_id`, required;
- `feat_code`, required;
- `idempotency_key`, required;
- canonical replay fingerprint, required;
- `fingerprint_version`, required;
- acceptance timestamp in UTC, required.

The reservation identity MUST be structurally unique. A reservation represents
an accepted command and has no mutable accepted/rejected lifecycle. A failed
command does not leave a committed reservation.

## IV. Replay Fingerprint

### 4.1 Canonicalization

The fingerprint MUST be computed from a Ledger-defined canonical command
representation. The representation MAY include command-family-specific
immutable inputs, including target, actor where semantically relevant, account
intent, amount/effect plan, and other values required to establish replay
equivalence.

It MUST exclude presentation-only descriptions, generated transaction IDs,
execution timestamps, request-local nonces, and other values that legitimately
change across retries.

The canonical representation MUST have deterministic field ordering, explicit
null/absence rules, normalized scalar encodings, and a specified digest
algorithm. Callers MUST NOT supply an arbitrary serialized payload as the
fingerprint source.

### 4.2 Versioning

Every fingerprint MUST carry `fingerprint_version`. The version identifies the
complete canonicalization and digest contract used when the reservation was
accepted. A later serializer change MUST create a new version for new
reservations and MUST NOT reinterpret or recompute historical fingerprints.

## V. Reservation and Ledger Effects

One reservation MAY own one or more `ledger_transaction` effect rows. Every new
canonical effect MUST reference its command reservation through a structural
foreign key. Historical exceptions are governed by §VII.

Creation of a new reservation and every Ledger effect produced by that command
MUST occur in one database transaction. A reservation MUST NOT commit without
all required effects, and an effect MUST NOT commit without its reservation.

Transfers are one reservation with two effects: one debit and one credit. A
reversal is a new command with a new reservation; its effect may reference the
original transaction through the canonical correction linkage, while the
original reservation remains unchanged.

## VI. Replay and Concurrency

### 6.1 New command

The Ledger attempts to create the reservation under the unique reservation
identity. If creation succeeds, the command and all effects proceed atomically.

### 6.2 Exact replay

If reservation creation encounters a uniqueness conflict, Ledger MUST retrieve
the existing reservation for the exact `(class_id, feat_code, idempotency_key)`
identity and compare the supplied fingerprint and version.

If they match, Ledger returns or reconstructs the original command outcome from
the reservation and its associated effects. The original reservation and
effects are not mutated.

### 6.3 Fingerprint mismatch

If the fingerprint or version does not match the existing reservation, Ledger
MUST fail closed with a replay-mismatch result. It MUST NOT create another
reservation, append effects, or mutate the existing reservation.

A uniqueness conflict MUST NOT be reported as a generic duplicate transaction
failure before this reservation lookup and fingerprint comparison occur.

## VII. Historical Classification

Historical effects MUST be classified semantically; nullable reservation links
alone do not establish their classification.

- **`CANONICAL_LINKED`** — a new canonical effect with a required reservation.
- **`HISTORICAL_LINKED`** — a pre-reservation effect whose command identity and
  fingerprint were lawfully established during an explicitly governed
  migration and linked to a reservation.
- **`HISTORICAL_UNLINKED`** — a historical effect whose command identity cannot
  be proven. No reservation or command lineage may be fabricated for it.

The physical representation of these classifications is deferred to migration
and schema design. Historical unlinked effects MUST NOT be treated as evidence
that a reservation existed.

## VIII. Coverage and Constraints

Every canonical Ledger command path MUST require a reservation. Any exception
requires an explicit Ledger contract and MUST NOT be inferred from legacy
omissions. The reservation identity remains occupied permanently, including
after VOID, reversal, or other correction.

The eventual schema MUST structurally enforce:

- uniqueness of `(class_id, feat_code, idempotency_key)`;
- required reservation linkage for new canonical effects;
- immutable reservation identity, fingerprint, version, and acceptance time;
- reservation/effect referential integrity;
- atomic reservation and effect creation.

The existing transaction-level partial unique index is transitional evidence. It
MUST NOT be treated as the final command-idempotency mechanism without proving
that it satisfies this command-level, permanent, one-to-many contract.

## IX. Deferred Decisions

This specification does not select the migration sequence, database-specific
index implementation, fingerprint digest algorithm beyond requiring that it be
specified by the versioned fingerprint contract, or runtime API shape. Those
decisions MUST implement this contract without weakening its semantics.

## X. Dependencies

- `DOM-LED-001_LEDGER_DOMAIN.md`
- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `FEAT-LED-001_POST_LEDGER_TRANSACTION.md`
