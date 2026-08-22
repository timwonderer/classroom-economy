# SPEC-OPS-001: Reversal, Void, and Transaction Finality Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-OPS-001 | 1.0 | 2026-08-22 | None | Normative |

---
## I. Purpose
T
his specification defines the canonical cross-domain meaning of:
- REVERSAL
- VOID
- transaction and grant finality
- obligation-derived finality
- monetary remediation

These concepts MUST NOT be treated as interchangeable forms of “undo.”

CTH preserves historical economic facts. Corrective actions occur through new, explicitly authorized operations. They MUST NOT rewrite, delete, or retroactively reinterpret completed history.

The canonical distinction is:
Money is reversed. Grants are voided. Obligation-related facts permit neither.

## II. Foundational Model

CTH distinguishes between two fundamentally different kinds of economic artifacts.

### 2.1 Monetary Transactions
A monetary transaction records movement of economic value through the Ledger.

Where explicitly authorized, its monetary effect MAY be counteracted through a REVERSAL. A monetary transaction MUST NOT be voided.

### 2.2 Grants
A grant confers an entitlement, privilege, permission, or other exercisable capability. 

Where explicitly authorized, a grant MAY be invalidated through a VOID. A grant MUST NOT be reversed.

### 2.3 No Generic Undo
CTH SHALL NOT implement a generic “undo” operation spanning these concepts.

REVERSAL and VOID:
- act on different artifacts;
- have different semantics;
- require independent authorization;
- and MUST NOT be substituted for one another.

## III. Reversal

### 3.1 Definition

A **REVERSAL** is an atomic append-only corrective operation originating from an eligible prior monetary transaction.

A lawful reversal:

1. creates a compensating monetary transaction that counteracts the monetary effect of the original transaction; and
2. invalidates eligible downstream grants whose authority derives from the reversed transaction.

The original monetary transaction and all downstream grant history remain historical fact.

Example:

```text
Purchase                 -$20
  └─ Hall Pass           ACTIVE

REVERSAL                 +$20
  └─ Hall Pass           INVALIDATED_BY_REVERSAL
```

The resulting monetary effect is zero, and the grant can no longer be exercised.

### 3.2 Historical Preservation

Reversal MUST NOT:

- delete the original transaction;
- mutate the original monetary amount;
- delete a downstream grant;
- represent the original transaction as never having occurred;
- or erase the historical period during which a downstream grant was valid.

Canonical history records both the original action and its later reversal.

### 3.3 Reversal Propagates Through Transaction-Derived Authority

When a grant derives its authority from the monetary transaction being reversed, reversal MUST invalidate that grant.

This invalidation is a consequence of reversal provenance.

It is NOT a VOID.

The resulting grant state SHOULD therefore preserve the distinction between:

- `VOID` — direct exercise of grant-void authority; and
- `INVALIDATED_BY_REVERSAL` — loss of grant authority because its originating monetary transaction was reversed.

Both states are non-exercisable, but they represent different historical causes.

### 3.4 Downstream Eligibility Gate

Before reversing a monetary transaction, CTH MUST resolve all downstream grants whose authority derives from that transaction.

Reversal is permitted only if every affected grant:

1. is **not obligation-related**;
2. has **not been USED**;
3. has **not EXPIRED**;
4. has **not been VOIDED**; and
5. is otherwise eligible for invalidation by reversal under its governing domain.

If any downstream grant fails these conditions, the originating monetary transaction MUST NOT be reversed.

### 3.5 Atomicity

Monetary compensation and downstream grant invalidation MUST occur atomically.

CTH MUST NOT permit an intermediate durable state in which:

- money has been restored while a transaction-derived grant remains exercisable; or
- a transaction-derived grant has been invalidated while the monetary reversal failed to occur.

The complete reversal either succeeds or fails as one authorized operation.

### 3.6 Reversal Is Terminal

A REVERSAL transaction MUST NOT itself be reversed.

The following chain is illegal:

```text
Original
  └─ Reversal
       └─ Reversal of reversal   ← PROHIBITED
```

Once an original transaction has been lawfully reversed, no further reversal operation may target either the original transaction or its reversal.

### 3.7 Explicit Eligibility

Reversal is not universally available to monetary transactions.

A monetary transaction MAY be reversed only when:

1. the governing domain explicitly permits reversal;
2. the transaction has not already been reversed;
3. the transaction is not itself a reversal;
4. the transaction has no obligation-related provenance;
5. every downstream transaction-derived grant passes §3.4;
6. no governing invariant otherwise prohibits reversal.

Absence of prohibition MUST NOT be interpreted as authorization.

---

## IV. Void

### 4.1 Definition

A **VOID** is an append-only invalidation of an eligible grant.

VOID acts directly on the grant.

It does not act on the monetary transaction that may have caused the grant to exist.

Example:

```text
Purchase                 -$20
  └─ Hall Pass           ACTIVE
       └─ VOID           VOID
```

The Hall Pass becomes non-exercisable.

The purchase remains monetarily effective.

### 4.2 Void Is Not Reversal

VOID MUST NOT:

- credit money;
- debit money;
- reverse a purchase;
- restore a prior balance;
- create a monetary refund;
- or mutate the originating monetary transaction.

The teacher's decision to invalidate a grant does not imply that the economic transaction through which the grant was acquired was invalid.

### 4.3 Void Is Terminal

A voided grant:

- MUST remain historical;
- MUST NOT be exercised;
- MUST NOT be unvoided;
- and MUST NOT permit subsequent reversal of its associated monetary acquisition transaction.

If the same capability is later granted again, that action requires a new independently authorized grant.

### 4.4 Obligation Exception

A grant with obligation-related provenance MUST NOT be voided.

Section VII overrides all ordinary grant-void authority.

---

## V. Canonical Operation Matrix

The relationship between monetary reversal and grant void is:

| Starting artifact/state | Requested operation | Money returned? | Grant remains exercisable? | Legal? |
|---|---|---:|---:|---:|
| Active purchased grant | **REVERSAL** | **Yes** | **No — invalidated by reversal** | **Yes, if otherwise authorized** |
| Active purchased grant | **VOID** | No | **No — voided** | **Yes, if otherwise authorized** |
| USED purchased grant | REVERSAL | No| No | **NO** |
| EXPIRED purchased grant | REVERSAL | No | No | **NO** |
| VOID purchased grant | REVERSAL | No | No | **NO** |
| Obligation-derived grant | REVERSAL | No| No| **NO** |
| Obligation-derived grant | VOID | No| No | **NO** |
| Obligation-related monetary transaction | REVERSAL | No | No | **NO** |
| REVERSAL transaction | REVERSAL | No |No | **NO** |

The canonical summary is:

> **Reverse money and invalidate still-eligible grants deriving authority from that money.**

> **Void an eligible grant without touching money.**

> **If obligation-related: neither reversal nor void is legal.**

---

## VI. Grant Lifecycle and Reversal Eligibility

### 6.1 Active Grant

An active, unused, unexpired, non-void, non-obligation-derived grant MAY permit reversal of its originating monetary transaction where the governing domain authorizes reversal.

A successful reversal invalidates the grant as part of the same atomic operation.

### 6.2 Used Grant

Once a grant is USED, the originating monetary transaction MUST NOT be reversed.

The purchased capability has already been exercised.

```text
Purchase → Grant → USED
                    ↓
              reversal prohibited
```

### 6.3 Expired Grant

Once a grant is EXPIRED, the originating monetary transaction MUST NOT be reversed.

Expiration represents completion of the grant's lawful availability period.

Failure to use a grant before expiration does not create reversal eligibility.

### 6.4 Voided Grant

Once a grant is VOID, the originating monetary transaction MUST NOT be reversed.

VOID is an independently authorized terminal disposition of the grant.

A later reversal MUST NOT be used to construct an undeclared second corrective operation.

### 6.5 Obligation-Derived Grant

A grant whose authority derives from fulfillment of an obligation MUST NOT be:

- voided;
- invalidated through reversal;
- or used as the basis for reversing an obligation-related monetary transaction.

Obligation provenance is terminal and overrides ordinary Store/Entitlement correction mechanisms.

---

## VII. Obligation Provenance — Absolute Finality

# OBLIGATION-RELATED = NO REVERSAL, NO VOID

This rule is absolute.

If a monetary transaction or grant is obligation-related:

> **It MUST NOT be reversed.**

> **It MUST NOT be voided.**

> **It MUST NOT be invalidated through reversal propagation.**

“Obligation-related” is determined by provenance, not representation.

An entitlement does not become voidable merely because it resides in the Entitlements domain.

A monetary transaction does not become reversible merely because it resides in Ledger.

If its semantic authority derives from an obligation, obligation finality follows it.

Teacher monetary remediation, where authorized, MUST occur through a new independent adjustment transaction and MUST NOT carry machine semantics asserting reversal of the obligation.

---

## VIII. Refund Semantics

### 8.1 Refund Is a Business Meaning, Not a Third Primitive

CTH does not require a generic REFUND ledger primitive.

For an eligible Store purchase with an active downstream grant, ordinary REVERSAL already provides the canonical refund-like behavior:

```text
Purchase                 -$20
  └─ Hall Pass           ACTIVE

REVERSAL                 +$20
  └─ Hall Pass           INVALIDATED_BY_REVERSAL
```

The participant receives the money back and the purchased grant loses its authority atomically.

### 8.2 Refund Terminology

A domain or user interface MAY describe an eligible reversal as a **refund** where that language is appropriate for users.

Such terminology MUST NOT alter the canonical semantics.

The underlying operation remains REVERSAL.

### 8.3 Void Is Not Refund

Voiding a grant does not return money.

```text
Purchase                 -$20
  └─ Hall Pass           ACTIVE
       └─ VOID

Monetary result:         -$20 remains
Grant result:            non-exercisable
```

A teacher choosing VOID is explicitly invalidating the grant without reversing its originating monetary transaction.

---

## IX. Canonical Examples

### Example A — Reversing an Unused Hall Pass Purchase

```text
Purchase                 -$20
Hall Pass                ACTIVE

Reversal                 +$20
Hall Pass                INVALIDATED_BY_REVERSAL
```

Result:

- net monetary effect is $0;
- grant remains historical;
- grant is no longer exercisable;
- no VOID occurred.

### Example B — Voiding an Unused Hall Pass

```text
Purchase                 -$20
Hall Pass                ACTIVE

Void Hall Pass
```

Result:

- purchase remains -$20;
- grant remains historical;
- grant becomes VOID;
- purchase becomes permanently ineligible for reversal.

### Example C — Used Hall Pass

```text
Purchase                 -$20
Hall Pass                USED
```

Result:

- grant cannot be voided;
- purchase cannot be reversed.

### Example D — Expired Hall Pass

```text
Purchase                 -$20
Hall Pass                EXPIRED
```

Result:

- grant cannot be voided;
- purchase cannot be reversed.

### Example E — Obligation-Derived Hall Pass

```text
Obligation fulfilled
       │
       └─► Hall Pass ACTIVE
```

Result:

- Hall Pass cannot be voided;
- obligation-related monetary history cannot be reversed;
- generic Store/Ledger corrective mechanisms have no authority over the obligation-derived grant.

### Example F — Obligation Monetary Remediation

```text
Cycle 1:
Rent paid                historical obligation fact

Cycle 3:
Teacher adjustment       +$500
```

Result:

- rent remains historically paid;
- no reversal occurred;
- no void occurred;
- the adjustment is an independent Cycle 3 economic event.

---

## X. Cross-Domain Invariants

### INV-OPS-001 — Artifact-Specific Correction

Monetary transactions MAY be reversed where explicitly authorized.

Grants MAY be voided where explicitly authorized.

Monetary transactions MUST NOT be voided.

Grants MUST NOT be reversed.

### INV-OPS-002 — Reversal Propagation

A lawful reversal MUST atomically:

1. counteract the monetary effect of the eligible originating transaction; and
2. invalidate all eligible downstream grants whose authority derives from that transaction.

Downstream invalidation caused by reversal MUST remain semantically distinguishable from VOID.

### INV-OPS-003 — Reversal Eligibility Gate

A monetary transaction MUST NOT be reversed if any transaction-derived downstream grant is:

- obligation-related;
- USED;
- EXPIRED;
- VOID;
- or otherwise ineligible for invalidation.

### INV-OPS-004 — Reversal Atomicity

Monetary compensation and required downstream grant invalidation MUST succeed or fail atomically.

### INV-OPS-005 — Reversal Terminality

A REVERSAL MUST NOT itself be reversed.

An already reversed original transaction MUST NOT be reversed again.

### INV-OPS-006 — Void Semantics

VOID acts on an eligible grant without altering the monetary effect of its originating transaction.

A VOID grant MUST NOT be unvoided.

### INV-OPS-007 — Terminal Grant Finality

USED, EXPIRED, and VOID grants MUST NOT permit reversal of their associated monetary acquisition transaction.

### INV-OPS-008 — Obligation Absolute Finality

**If obligation-related: NO REVERSAL. NO VOID.**

This prohibition follows provenance across domain and representation boundaries.

### INV-OPS-009 — Obligation Remediation Independence

Monetary remediation associated with an obligation MUST occur through a new independently authorized transaction.

Such remediation MUST NOT reverse, void, reopen, unsatisfy, or reinterpret the obligation.

### INV-OPS-010 — Historical Finality

Corrective operations MUST preserve historical facts and MUST NOT cause completed economic cycles or persisted Interpretation observations to be retrospectively reinterpreted.

### INV-OPS-011 — Explicit Authority

Reversal and void require explicit governing-domain authorization.

Absence of prohibition is not authorization.

### INV-OPS-012 — No Compatibility Resurrection

Removed legacy correction mechanisms MUST NOT be recreated, relocated, aliased, wrapped, or otherwise resurrected merely to satisfy stale callers.

Stale callers MUST be migrated to canonical semantics or removed where the former capability is no longer lawful.