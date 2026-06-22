# FEAT-OPS-001: Audit Protected Emission

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|:---|:---|:---|:---|:---|
| FEAT-OPS-001 | 1.0 | 2026-05-10 | N/A | Normative |

---

## I. Purpose

Define the required execution contract for `audit_protected()` — the canonical mechanism by which any FEAT attaches tamper-evident audit lineage to a protected row after writing it to the database, in compliance with `INV-ARC-016` and `DOM-OPS-002`.

---

## II. Scope

Applies to every FEAT that writes to a protected table. A protected table is any table listed in the `PROTECTED_FIELDS_BY_TABLE` registry defined in `DOM-OPS-002`. The current registry includes `transactions`; additional tables are added as Phase 3b migrations land.

---

## III. Authority Level

Normative. Subordinate to `INV-ARC-016`, `DOM-OPS-002`, and `FEAT-CORE-000`.

---

## IV. Dependencies

- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

---

## II. Execution Context

### 1. Required Inputs

- `table_name`: Name of the protected table being written (must appear in `PROTECTED_FIELDS_BY_TABLE`)
- `row`: The flushed SQLAlchemy model instance (must have a non-null primary key)
- `operation`: One of `INSERT` / `UPDATE` / `DELETE` / `TRANSITION`
- `fields`: List of field names to include in the payload digest (must match the registry entry for `table_name`)

### 2. Resolved Context (from Active FEAT)

- `class_id`: Resolved from `FEATContext.class_id`
- `feat_id`: Resolved from `FEATContext.active_feat`
- `correlation_id`: Resolved from `FEATContext.correlation_id`
- `idempotency_key`: Resolved from `FEATContext.idempotency_key`
- `actor_type`, `actor_id_hash`: Resolved from the actor bound to the FEAT context

---

## III. Orchestration Logic

### 1. Preconditions (verified before emit)

1. An active FEAT context must be present. `audit_protected()` shall raise `AuditContextError` if called outside a FEAT context or `SystemAuditAuthority`.
2. `db.session.flush()` must have been called prior to `audit_protected()`, ensuring `row.id` is assigned and non-null.
3. The owning FEAT transaction must not have committed. `audit_protected()` does not commit; it participates in the caller's transaction boundary.
4. `AUDIT_HMAC_KEY` must be present in the environment.

### 2. Mutation Sequence (Atomic Within Caller's Transaction)

1. Resolve `class_id`, `feat_id`, `correlation_id`, `idempotency_key`, `actor_type`, `actor_id_hash` from the active FEAT context.
2. Call `emit_audit_event(table_name, row_pk=str(row.id), operation, protected_fields, class_id=..., feat_id=..., ...)`.
3. Inside `emit_audit_event()`:
   a. Resolve chain scope: `"class:{class_id}"` or `"system"`.
   b. Acquire `ChainHead` with `SELECT FOR UPDATE`.
   c. Bootstrap `ChainHead` if absent (lazy per-class genesis).
   d. Compute `next_sequence = head.latest_sequence + 1`.
   e. Compute `payload_digest` from the canonical payload of the protected fields.
   f. Compute `context_digest` from actor/feat context fields.
   g. Compute `event_hash` (HMAC-SHA256) over pipe-delimited chain fields.
   h. Construct and flush the `AuditEvent` row.
   i. Update `ChainHead.latest_hash`, `latest_sequence`, `event_count`, `last_updated_utc`.
4. `emit_audit_event()` returns the flushed `AuditEvent` instance (`.id` is now assigned).
5. Set `row.lineage_event_id = event.id`.
6. Set `row.lineage_token = event.hmac_signature`.
7. Set `row.lineage_version = event.signature_version`.
8. Return. The caller's FEAT commits the entire transaction.

---

## IV. Invariants and Constraints

1. **Must be called after flush, before commit.** `audit_protected()` shall be called after `db.session.flush()` (so `row.id` is available) and before the owning FEAT's transaction commits.

2. **Must not commit internally.** `audit_protected()` and `emit_audit_event()` shall not call `db.session.commit()`. The caller's transaction boundary owns the commit.

3. **`AuditContextError` is not swallowable.** Any caller that catches `AuditContextError` and continues without re-raising violates `INV-ARC-016`. The error shall propagate and abort the transaction.

4. **`lineage_token` is a pointer, not proof.** Setting `row.lineage_token` is a fast provenance marker only. Canonical proof of lawful existence requires a full chain walk by the verifier (`verify_chain`) confirming both HMAC continuity and payload digest match.

5. **One emit per row per state change.** `audit_protected()` shall be called exactly once per protected row creation or update. Calling it multiple times for the same row without an intervening state change is prohibited.

6. **Fields must match the registry.** The `fields` argument must exactly match the entry in `PROTECTED_FIELDS_BY_TABLE` for `table_name`. Deviations produce false `INVALID` results on subsequent verification.

---

## V. Idempotency

`audit_protected()` is not idempotent by design — each call produces a new `AuditEvent` and increments the chain sequence. Idempotency for the business mutation is the responsibility of the owning FEAT (via `idempotency_key` check before the mutation phase). If the owning FEAT returns early due to an idempotency hit, `audit_protected()` must not be called.

---

## VI. Audit Requirements

`DOM-OPS-002` records the following for every `audit_protected()` call:

| Field | Source |
|---|---|
| `chain_scope` | Resolved from `class_id` |
| `sequence_number` | Assigned atomically from `ChainHead` |
| `event_hash` | HMAC-SHA256 over chain fields |
| `payload_digest` | SHA-256 of canonical protected field values |
| `context_digest` | SHA-256 of actor/feat context fields |
| `feat_id` | Active FEAT name |
| `correlation_id` | Propagated from FEAT context |
| `idempotency_key` | Propagated from FEAT context |
| `actor_type` / `actor_id_hash` | Actor bound to FEAT context |
| `class_id` / `seat_id` / `teacher_id` | From FEAT context |
| `table_name` / `row_pk` / `operation` | From caller inputs |
| `created_at_utc` | UTC timestamp at emit time |
| `signer_key_id` / `signature_version` | From current HMAC key configuration |
