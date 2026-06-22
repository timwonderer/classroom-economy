# DOM-OPS-002: Audit Lineage Integrity

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|:---|:---|:---|:---|:---|
| DOM-OPS-002 | 1.0 | 2026-05-10 | N/A | Constitutional |

---

## I. Purpose

Define the Operations domain's authority over the tamper-evident audit lineage system: the schema, emission protocol, chain verification logic, integrity status reporting, and execution evidence model that operationalize `INV-ARC-016`.

---

## II. Scope

Governs the `audit_events`, `chain_heads`, and `integrity_status` tables and all code paths that read from or write to them.

Applies to every protected table whose mutations must produce an `AuditEvent` chain entry, including constitutional economic policy lineage objects.

---

## III. Authority Level

Constitutional. Subordinate to `INV-ARC-016` and `DOM-OPS-001`. Supersedes any prior informal convention regarding audit logging for protected tables.

---

## IV. Dependencies

- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

---

## 1. Domain Authority Declaration

### DOM-OPS-002 OWNS Authority Over

- **AuditEvent chain schema** — the structure of `audit_events` and `chain_heads`
- **Emission protocol** — the rules governing when and how `emit_audit_event()` is called
- **Chain verification logic** — the algorithm for walking a chain scope and detecting tampering
- **IntegrityStatus** — the singleton operational status record consumed by `/health/deep`
- **Protected fields registry** — the declaration of which fields per table are included in `payload_digest`
- **Lawful write path enumeration** — what constitutes a valid execution context for chain emission

### DOM-OPS-002 Explicitly DOES NOT Own

- Business domain truth (balances, attendance, purchases)
- Constitutional economic policy truth (owned by DOM-CLASS / DOM-ECON governance)
- Feature enablement policy
- General operational telemetry and structured logs (owned by `DOM-OPS-001`)
- Incident lifecycle management (owned by `DOM-OPS-001`)

---

## 2. Schema Authority

### 2.1 `audit_events` (Append-Only)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | Integer | No | Primary key |
| `chain_scope` | String(64) | No | `"class:{uuid}"` or `"system"` |
| `sequence_number` | Integer | No | Monotonically increasing per scope |
| `previous_hash` | String(64) | No | `"genesis"` for first entry |
| `event_hash` | String(64) | No | HMAC-SHA256; unique across all events |
| `table_name` | String(64) | No | Protected table name |
| `row_pk` | String(64) | No | String-cast primary key of the protected row |
| `operation` | String(16) | No | `INSERT` / `UPDATE` / `DELETE` / `TRANSITION` |
| `actor_type` | String(32) | Yes | `"teacher"` / `"student"` / `"system"` |
| `actor_id_hash` | String(64) | Yes | Hashed actor identifier |
| `class_id` | String(36) | Yes | UUID of the owning class |
| `seat_id` | Integer | Yes | Seat anchor if applicable |
| `teacher_id` | Integer | Yes | Teacher anchor if applicable |
| `feat_id` | String(32) | Yes | Active FEAT name at emit time |
| `idempotency_key` | String(128) | Yes | Caller-provided idempotency key |
| `correlation_id` | String(64) | Yes | Propagated from the active FEAT context |
| `request_id` | String(64) | Yes | HTTP request identifier |
| `payload_digest` | String(64) | No | SHA-256 of canonical protected field values |
| `context_digest` | String(64) | No | SHA-256 of actor context fields |
| `created_at_utc` | DateTime(tz) | No | UTC timestamp of emission |
| `signer_key_id` | String(16) | No | Key rotation label (e.g., `"v1"`) |
| `signature_version` | Integer | No | HMAC schema version |
| `hmac_signature` | String(64) | No | Copy of `event_hash` for fast provenance checks |

Unique constraints: `event_hash`; `(chain_scope, sequence_number)`.

### 2.2 `chain_heads`

One row per chain scope. Locked with `SELECT FOR UPDATE` on every emit to provide atomic sequence management.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `chain_scope` | String(64) | No | Primary key |
| `latest_hash` | String(64) | No | `event_hash` of the most recent event |
| `latest_sequence` | Integer | No | Most recent sequence number |
| `event_count` | Integer | No | Total events in this scope |
| `last_updated_utc` | DateTime(tz) | No | UTC timestamp of last update |

### 2.3 `integrity_status` (Single-Row Singleton)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | Integer | No | Primary key (always 1) |
| `passing` | Boolean | No | `True` only when all chains are `VERIFIED` |
| `last_checked_utc` | DateTime(tz) | Yes | UTC timestamp of last invariant check |
| `failure_detail` | Text | Yes | JSON array of failing scopes; operator-only |
| `degraded_since` | DateTime(tz) | Yes | When chain first entered failing state |

### 2.4 Allowlisted Write Paths

Only the following code paths may write to tables owned by this domain:

| Table | Allowlisted Path |
|---|---|
| `audit_events` | `app/services/audit_service.py` → `emit_audit_event()` |
| `chain_heads` | `app/services/audit_service.py` → `emit_audit_event()` |
| `integrity_status` | `app/utils/audit_verifier.py` → `update_integrity_status()` under `SystemAuditAuthority` |

Protected constitutional economic policy objects (`policy_versions`, `policy_transitions`) SHALL emit lineage exclusively through lawful FEAT-orchestrated execution paths.

---

## 3. State Classification

### `audit_events`

| Field | Classification |
|---|---|
| `event_hash` | Authoritative immutable identifier |
| `payload_digest` | Authoritative integrity witness |
| `sequence_number` | Authoritative chain position |
| `previous_hash` | Authoritative chain link |
| All actor / context fields | Authoritative provenance record |

### `chain_heads`

| Field | Classification |
|---|---|
| `latest_hash` | Authoritative current chain tip |
| `latest_sequence` | Authoritative current position |
| `event_count` | Derived count |

### `integrity_status`

| Field | Classification |
|---|---|
| `passing` | Derived aggregate from nightly chain walk |
| `degraded_since` | Authoritative incident onset timestamp |
| `failure_detail` | Derived diagnostic snapshot |

---

## 4. Invariants

### INV-OPS-013: Append-Only Audit Chain

`AuditEvent` rows shall never be updated or deleted. Any `UPDATE` or `DELETE` on `audit_events` is prohibited in all environments. Detection of such a modification is an incident.

### INV-OPS-014: Single Legal Emit Path

`emit_audit_event()` in `app/services/audit_service.py` is the only legal write path for `audit_events`. No other code may produce `AuditEvent` rows directly.

### INV-OPS-015: FEAT Context Requirement

`emit_audit_event()` shall raise `AuditContextError` if called outside an active FEAT context or `SystemAuditAuthority`. Direct calls without a context are prohibited.

### INV-OPS-016: HMAC Key Availability

The `AUDIT_HMAC_KEY` environment variable shall be present at application startup. The application shall refuse to start if absent. The key shall be separate from `PEPPER_KEY` and shall never be shared between environments.

### INV-OPS-017: Chain Scope Isolation

Events for class-scoped protected tables shall use chain scope `"class:{class_id}"`. System-level events shall use chain scope `"system"`. Cross-scope chain references are prohibited.

Class-scoped protected tables include, and are not limited to:
- `transactions` — scoped by `class_id`
- `policy_versions` — scoped by `class_id`; chain scope MUST be `"class:{class_id}"` for all policy version events
- `policy_transitions` — scoped by `class_id`; chain scope MUST be `"class:{class_id}"` for all transition events

Any audit event for `policy_versions` or `policy_transitions` that does not carry a valid `class_id` is a chain integrity violation.

### INV-OPS-018: UTC Normalization Requirement

All datetime values used in HMAC computation shall be normalized to UTC (`+00:00`) before `isoformat()` is called. The verifier shall apply the same normalization when recomputing event hashes. Mismatched timezone representations are an `INVALID` chain condition.

### INV-OPS-019: Payload Digest Field Parity

The `PROTECTED_FIELDS_BY_TABLE` registry in `app/utils/audit_verifier.py` shall exactly match the fields passed to `audit_protected()` at write time. Missing a field produces a false `INVALID`; an extra field produces a false `INVALID`. Both are prohibited.

### INV-OPS-020: UNVERIFIED Is Not INVALID

A row with `lineage_event_id IS NULL` shall return state `UNVERIFIED`, not `INVALID`. `UNVERIFIED` rows shall not cause `IntegrityStatus.passing` to be set to `False`. Code, logs, and operator-facing output shall never conflate these two states.

---

## 5. Schema Contract

### 5.1 Canonical Payload

The payload digest is computed over a deterministic JSON string with the following structure:

```
{
  "__table__": <table_name>,
  "__pk__": <str(row_pk)>,
  "__op__": <operation>,
  "__class_id__": <class_id or null>,
  <field_1>: <normalized_value>,
  <field_2>: <normalized_value>,
  ...
}
```

Rules:
- Business fields sorted by key.
- `datetime` values converted to UTC ISO-8601 before serialization.
- `Decimal` values converted to `str`.
- `None` values serialized as JSON `null`.
- JSON produced with `sort_keys=True`, no whitespace (`separators=(",", ":")`).

The digest is `SHA-256(canonical_json_utf8)` expressed as a 64-character hex string.

### 5.2 Context Digest

The context digest is `SHA-256` of the sorted JSON of:
`{feat_id, class_id, actor_type, actor_id_hash, correlation_id, idempotency_key}`

### 5.3 Event Hash (HMAC)

The event hash is `HMAC-SHA256(AUDIT_HMAC_KEY, message)` where `message` is pipe-delimited:

```
{previous_hash}|{chain_scope}|{sequence_number}|{table_name}|{row_pk}|{operation}|{actor_context_json}|{payload_digest}|{created_at_utc_isoformat}
```

`actor_context_json` is the sorted JSON of `{actor_type, actor_id_hash, feat_id, correlation_id}`.

### 5.4 Protected Fields Registry

| Table | Protected Fields |
|---|---|
| `transactions` | `amount`, `account_type`, `type`, `status`, `class_id`, `seat_id`, `description`, `correlation_id` |
| `policy_versions` | `class_id`, `domain`, `version_number`, `policy_payload_json`, `activated_at`, `is_active` |
| `policy_transitions` | `class_id`, `domain`, `source_policy_version_id`, `target_policy_version_id`, `activation_mode`, `status`, `correlation_id` |

Additional tables shall be added to this registry in coordination with each Phase 3b migration.

### 5.5 Chain Scope Resolution

```
class_id present  →  "class:{class_id}"
class_id absent   →  "system"
```

Per-class `ChainHead` rows are bootstrapped lazily on first emit for that class.

**Constitutional economic policy objects** (`policy_versions`, `policy_transitions`) are class-scoped. Their audit chain scope is always `"class:{class_id}"`. There is no system-scoped chain for policy lineage objects. If a `policy_versions` or `policy_transitions` row is emitted without a `class_id`, it is an `INVALID` chain condition and MUST be surfaced in `IntegrityStatus`.

---

## 6. State Transitions

### 6.1 Chain Emit Flow

```
caller enters FEAT context
  → domain mutation executes
  → db.session.flush() (row.id assigned)
  → audit_protected() called
      → emit_audit_event() called
          → ChainHead acquired with SELECT FOR UPDATE
          → AuditEvent constructed (sequence, hashes computed)
          → AuditEvent flushed
          → ChainHead updated atomically
          → row.lineage_event_id, lineage_token, lineage_version set
          → policy transition lineage activation recorded if applicable
  → FEAT transaction commits
```

### 6.2 Nightly Verification Flow

```
scheduler triggers run_audit_invariant_check_job() at 03:00 UTC
  → run_full_invariant_check()
      → load all chain scopes from chain_heads
      → for each scope: verify_chain(scope, limit=1000)
          → walk AuditEvent rows ordered by sequence_number
          → check previous_hash continuity
          → check sequence gaps
          → recompute event_hash (with UTC normalization)
          → compare to stored event_hash
          → return VerificationResult(state, failure_type, ...)
  → update_integrity_status(results) under SystemAuditAuthority
      → write IntegrityStatus row
      → set degraded_since on first-failure transition
      → clear degraded_since on recovery
```

---

## 7. Lineage State Taxonomy (Operational Semantics)

This taxonomy is defined as canonical in `INV-ARC-016`. The operational semantics for this domain are:

| State | Detection Condition | `IntegrityStatus` Effect |
|---|---|---|
| `VERIFIED` | Chain continuous; HMAC valid; payload digest matches | `passing=True` |
| `UNVERIFIED` | `lineage_event_id IS NULL` | No effect (coverage gap, not a failure) |
| `INVALID` | Chain broken, HMAC mismatch, or payload mismatch | `passing=False`; `degraded_since` set |
| `DEGRADED` | Verifier infrastructure error | `passing=False`; `degraded_since` set; `failure_type=VERIFIER_ERROR` |

---

## 8. Edge Case Decisions

1. **`lineage_token` is a pointer, not proof.** `lineage_token` (copy of `AuditEvent.hmac_signature`) enables a fast "row was touched by the audit system" pre-check only. Canonical proof of lawfulness requires both payload digest match and a continuous chain walk.

2. **`UNVERIFIED` is not `INVALID`.** Rows with `lineage_event_id IS NULL` predate lineage rollout. Operators shall track coverage toward zero; the verifier shall not treat them as incidents.

3. **Per-class lazy genesis.** A `ChainHead` for `class:{class_id}` is created on first emit for that class. The `ChainHead` for `"system"` may be seeded at bootstrap.

4. **`SystemAuditAuthority` is not a FEAT.** It carries no business actor fields and shall not be used inside business mutation paths. Its sole permitted uses are genesis bootstrap, nightly verifier writes, and `IntegrityStatus` updates.

5. **`SystemAuditAuthority` thread-local ownership.** The `_system_audit_ctx` thread-local lives in `app/feats/base.py` to avoid circular imports. `app/services/audit_service.py` accesses it via late import.

6. **Sequence gaps are detectable deletions.** If an `AuditEvent` row is deleted from a chain, the verifier detects a `SEQUENCE_GAP` at the missing sequence number. This is an `INVALID` condition.

7. **Payload digest mismatch is a tampered row.** If a protected row's current field values do not hash to the `payload_digest` on its linked `AuditEvent`, the row was mutated outside the canonical write path.

8. Constitutional economic policy lineage is protected state. `policy_versions` and `policy_transitions` are protected constitutional objects and are subject to the same lawful-lineage verification requirements as monetary truth.

9. **UTC normalization is mandatory for HMAC recomputation.** `emit_audit_event()` computes the event hash using `datetime.now(timezone.utc).isoformat()` which yields `+00:00`. PostgreSQL/SQLAlchemy may return stored `TIMESTAMPTZ` values in the local session timezone. The verifier shall normalize all retrieved datetimes to UTC before recomputation.

10. **No HMAC reuse across scopes.** The chain scope is a field in the HMAC message, ensuring that an event from one class chain cannot be replayed into another.

11. **One emit per row creation.** `audit_protected()` shall be called exactly once per protected row creation, immediately after `flush()` and before the owning transaction commits. Re-invocations for the same row without a state change are prohibited.

12. **`lineage_version` tracks schema evolution.** When the HMAC schema or canonical payload format changes, `signature_version` and `signer_key_id` enable the verifier to apply the correct recomputation logic per event.

13. **`IntegrityStatus.degraded_since` is set on first failure.** If a new `IntegrityStatus` row is created in a failing state, `degraded_since` shall be set to the current UTC time. If an existing passing row transitions to failing, `degraded_since` shall be set. If the row recovers, `degraded_since` shall be cleared to `None`.

---

## 9. Amendment

Revisions must preserve the append-only guarantee for `audit_events`, the HMAC chain integrity algorithm, the `UNVERIFIED ≠ INVALID` distinction, and the two-path lawful write model. Any change to the canonical payload format or HMAC message structure shall increment `signature_version`.
