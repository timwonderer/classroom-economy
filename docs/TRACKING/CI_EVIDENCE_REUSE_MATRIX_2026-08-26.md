# CI Evidence-Reuse Matrix

| Field | Value |
| --- | --- |
| Status | Frozen audit/design input |
| Date | 2026-08-26 |
| Branch | `codex/constitutional-ci-reconstruction` |
| Baseline | `740989fa` |
| Governing specification | `SPEC-INV-001` |
| Scope | Existing architectural CI evidence only; no new tests or workflow changes |

## Purpose

This matrix records what the repository already executes and what each mechanism
can honestly establish. It does not promote a workflow name, test marker, or
historical result into constitutional evidence.

`READY` means the existing mechanism materially proves the stated narrow claim
and is suitable for CI wiring. `PARTIAL` means useful evidence exists but a
required layer or subclaim remains uncovered. `MISSING` means no current
mechanism was identified. `BROKEN` means the intended mechanism cannot be
trusted as executed evidence. `FALSE_ASSURANCE` means the mechanism appears to
prove a claim that it does not evaluate.

## Frozen matrix

| CI family | Required claim | Governing authority | Existing evidence | Targeted result / current gate | Classification | Minimum remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| Architectural execution | FEAT context and transaction boundary enforce mutation authority | `INV-ARC-000`, `INV-ARC-006`, `INV-ARC-007` | `tests/dom/operation/test_feat_enforcement.py`; `tests/dom/operation/test_feat_context_transactions.py` | 37 targeted tests passed on 2026-08-26; no workflow selects them as a constitutional family | `READY` evidence | Wire exact files to a runtime gate; retain static checks as a separate layer |
| Scope and identity | Class/seat scope, tenant isolation, explicit switching, nonexistent-scope failure, hard-delete sibling isolation | `INV-ARC-001`, `002`, `004`, `008`, `010`, `011`, `013`, `014`, `019` | `tests/dom/class/test_feature_scope_single_active_class.py`; `test_pending_student_class_isolation.py`; `test_hard_delete_class_scope_isolation.py`; `tests/dom/identity/test_class_context_and_switching.py`; `test_admin_tenancy.py` | 27 targeted tests passed on 2026-08-26; no workflow selects this family | `READY` evidence | Wire exact files; preserve the cartesian-product warning as a separate quality finding |
| Temporal integrity | Canonical SLE/CLE resolver behavior and fail-closed authority | `INV-ARC-015`, `SPEC-TIME-001` | `tests/dom/temporal/test_SPEC_TIME_001__canonical_temporal_resolver.py` | 26 targeted tests passed on 2026-08-26 | `PARTIAL` | Add evidence for prohibited direct temporal APIs, immutable class timezone, and historical non-reinterpretation |
| Lawful persistence | Append-only configuration, immutable economic versions, and authorized class destruction | `INV-ARC-012`, `INV-ARC-016` | `tests/test_class_phase2_persistence.py`; hard-delete scope test above | Included in 37-test slice; all passed | `PARTIAL` | AuditEvent immutability/lineage and PII-specific deletion remain uncovered |
| PII and identity storage | Finite PII allowlist, encrypted display fields, HMAC lookup fields, and deletion retention | `INV-ARC-005`, `INV-ARC-018`, `INV-ARC-019` | No complete allowlist-plus-runtime deletion mechanism identified | No current constitutional gate | `MISSING` | Establish authoritative field inventory and persistence/deletion evidence before wiring a gate |
| Cross-domain boundaries | No unauthorized domain imports/calls; FEAT-only coordination; permitted anchors only | `INV-ARC-021` | No dedicated dependency/schema-boundary gate identified | No current constitutional gate | `MISSING` | Design static dependency and schema checks from the invariant, not from current workflow names |
| Rendering/accessibility | Actual rendered browser semantics and supported interaction | `INV-ARC-020` | `tests/test_accessibility.py` performs narrow static HTML checks; `tests/test_axe_compliance.py` is an unconditional placeholder | Existing accessibility workflow runs only the static suite; Axe claim cannot execute meaningful violations | `PARTIAL` + `FALSE_ASSURANCE` | Replace placeholder with real rendered-browser evidence before claiming full accessibility enforcement |
| Migration structure | Reachable single head, reversible migration structure, guarded operations | `INV-ARC-017` and persistence requirements in `SPEC-INV-001` | `scripts/validate-migrations.py`; `.github/workflows/check-migrations.yml` | Script executes with venv but currently reports 7 unguarded operations in `3a69db4907b4_clean_up_announcement_model.py` | `PARTIAL` / failing | Resolve legacy-validator policy explicitly; do not hide failures with broad whitelists |
| Schema rehearsal | Upgrade, downgrade, and re-upgrade are actually exercised | `SPEC-INV-001` VIII.5 and IX | `.github/workflows/schema-gate.yml` | Upgrade/re-upgrade commands exist; downgrade contains silent skip branches | `BROKEN` downgrade evidence | Fail closed when head/file/down-revision resolution fails; distinguish `BLOCKED` from `PASS` |
| Static policy guardrails | Narrow prohibited mutation, scope-fallback, and audit-lineage patterns | `INV-ARC-006`, `007`, `016`; scope invariants | `scripts/policy_guardrails.py`; `.github/workflows/policy-guardrails.yml` | Venv execution detects `NO_WRITE_ON_GET` at `app/routes/system_admin.py:567` | `PARTIAL` / failing | Fix or explicitly disposition the violation; document static-only scope and runtime complement |
| Audit PR process | Audit artifact and docs-only process discipline | Process automation, not an `INV-ARC` enforcement family | `.github/workflows/audit-guard.yml` | Label-dependent docs/process checks only | `ORPHAN` as constitutional enforcement | Keep separate from invariant gates; audit operational value under a separate process review |

## Targeted execution record

All tests below used the repository venv at
`/Users/timothychang/Documents/GitHub/classroom-economy/.venv/bin/pytest`.
No full suite was run.

| Slice | Result artifact |
| --- | --- |
| FEAT, transaction, persistence: 37 passed | `pytest_result/20260826_pytest_test_feat_enforcement_summary.md` |
| Scope, identity, tenant isolation, hard deletion: 27 passed | `pytest_result/20260826_pytest_test_feature_scope_single_active_class_summary.md` |
| Canonical temporal resolver: 26 passed | `pytest_result/20260826_pytest_test_SPEC_TIME_001__canonical_temporal_resolver_summary.md` |

## Non-results and execution limits

- A first attempt with the bare `python` command returned exit `127`; it is not
  treated as test or validator evidence.
- The venv-backed validators executed successfully. Migration validation failed
  on seven unguarded operations, and policy guardrails failed on one GET
  mutation.
- Existing targeted tests write canonical artifacts under `pytest_result/`.
  Those artifacts are audit outputs and are not application or workflow changes.
- No result in this matrix certifies a complete constitutional family while a
  required subclaim remains uncovered.

## Next authorized design input

Use this frozen matrix to design a manifest-driven, change-sensitive CI
classifier and runtime gate wiring. Implementation must preserve the result
semantics in `SPEC-INV-001`: `PASS`, `FAIL`, `NOT_APPLICABLE`,
`NOT_EVALUATED`, and `BLOCKED`. Missing evidence must fail closed.
