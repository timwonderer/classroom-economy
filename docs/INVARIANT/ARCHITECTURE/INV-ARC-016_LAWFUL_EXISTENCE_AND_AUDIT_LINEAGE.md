# INV-ARC-016: Lawful Existence and Audit Lineage

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-016      | 2.0     | 2026-05-20     | N/A        | Foundational    |

## I. Purpose

Define the principle of lawful existence: physical database persistence alone does not constitute a valid application entity. A protected row is lawful only if it was created through an authorized CTH execution path and carries verifiable audit lineage.

## II. Scope

Applies to all state mutation paths for protected tables.

A protected table is any table whose row-level mutations must produce an `AuditEvent` chain entry, as declared in `DOM-OPS-002`.

Protected tables include:
- monetary truth lineage,
- operational lineage,
- constitutional economic policy lineage,
- and other constitutionally protected mutation surfaces.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.3, `Deterministic and Traceable Financial Logic`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `INV-ARC-007_GET_MUST_BE_PURE.md`
- `DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `DOM-CLASS-003_ECONOMIC_POLICY.md`

## V. Core Rule

A row in a protected table that was written outside a lawful CTH execution path (an active FEAT context or `SystemAuditAuthority`) is not a valid application entity, regardless of its physical presence in the database.

This invariant applies equally to:
- monetary truth,
- operational truth,
- constitutional economic policy truth,
- policy transition lineage,
- and future economic law objects.

The auditor of a protected row's lawfulness is the HMAC-SHA256 chain maintained by `DOM-OPS-002`. A row is lawful if and only if:

1. Its `lineage_event_id` references an `AuditEvent` whose `payload_digest` matches the row's current protected field values, and
2. That `AuditEvent` sits within a continuous, unbroken chain for its scope.

Constitutional economic policy objects include:
- `policy_versions`
- `policy_transitions`

Future economic law that lacks lawful lineage is constitutionally invalid regardless of physical persistence.

## VI. Lineage State Taxonomy

Every protected row has exactly one of four lineage states. All code that reads, reports, or acts on lineage MUST use this taxonomy exclusively.

| State | Meaning | Operational Response |
|---|---|---|
| `VERIFIED` | `lineage_event_id` set; current payload digest matches the linked `AuditEvent`; chain is continuous | Treat as lawful |
| `UNVERIFIED` | `lineage_event_id` is NULL — row predates lineage rollout or sits in a table not yet covered by Phase 3b | Do not treat as `INVALID`. Log as coverage gap. Operators shall track toward zero over time. |
| `INVALID` | Lineage present but payload mismatch, chain broken, or HMAC invalid | Reject in strict read paths. Trigger `IntegrityStatus` degraded. Treat as an incident. |
| `DEGRADED` | Verifier infrastructure unhealthy (e.g., `ChainHead` missing, `AUDIT_HMAC_KEY` absent, DB error during chain walk) | Mark `IntegrityStatus` degraded with reason. Produce neither false `VERIFIED` nor false `INVALID` results. |

`UNVERIFIED` is a transitional state expected for pre-rollout rows. `INVALID` is an incident. These states must never be conflated in code, logs, or operator-facing output.

## VII. HMAC Key Requirement

The `AUDIT_HMAC_KEY` environment variable is required at application startup. The application shall refuse to start if this variable is absent. It is separate from `PEPPER_KEY` and must never be shared between environments.

## VIII. AuditEvent Immutability

`AuditEvent` rows are append-only. No code path outside `emit_audit_event()` in `app/services/audit_service.py` may write to the `audit_events` table. `UPDATE` and `DELETE` on `audit_events` are prohibited in all environments.

## IX. Lawful Write Paths

Two write paths are lawful for producing `AuditEvent` chain entries:

1. **Active FEAT context** — the business mutation path. `emit_audit_event()` is called inside an active FEAT via `audit_protected()` after `db.session.flush()`, before the FEAT's owning transaction commits.
2. **`SystemAuditAuthority`** — the narrow system path for genesis bootstrap, verifier writes, and `IntegrityStatus` updates. `SystemAuditAuthority` carries no business actor fields; `actor_type` is always `"system"`. It is prohibited inside any business mutation path.

### Economic Policy Governance Clarification

Economic policy evolution MUST occur through lawful append-only policy transition lineage.

The following are prohibited:
- direct mutation of immutable historical policy versions,
- hidden delayed economic mutation,
- orphaned future economic state,
- policy activation without lawful lineage.

Immediate economic policy changes and delayed economic policy changes are equally subject to lawful lineage requirements.

## X. Rebuild Intent

This invariant exists to make unauthorized, hidden, or convenience-based database mutations visible and operationally embarrassing. Its goal is not to prevent all possible privileged compromise, but to ensure that any mutation outside the canonical execution path is detectable during the nightly chain walk and surfaces in `/health/deep` as a degraded state.

This includes hidden future economic law, delayed policy mutation outside lawful transition lineage, and constitutional economic state that bypasses canonical policy governance.

## XI. Downstream Consequence

`DOM-OPS-002` owns the schema, emission protocol, and verification logic that operationalizes this invariant.

`FEAT` execution contracts must call `audit_protected()` for every write to a protected table.

Protected constitutional economic policy objects include:
- `policy_versions`
- `policy_transitions`

CI guardrails in `scripts/policy_guardrails.py` enforce this structurally.

## XII. Amendment

Revisions must preserve the distinction between `UNVERIFIED` and `INVALID`, the two-path lawful write model, and the HMAC key startup requirement.

