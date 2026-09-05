# Change-Sensitive CI Classifier Design

| Field | Value |
| --- | --- |
| Status | Proposed design; implementation not started |
| Date | 2026-08-26 |
| Branch | `codex/constitutional-ci-reconstruction` |
| Authority | `SPEC-INV-001`, especially Sections VIII–XIII |
| Input | `CI_EVIDENCE_REUSE_MATRIX_2026-08-26.md` |

## Design objective

Select the smallest set of invariant evidence families affected by a change,
while conservatively over-selecting when file ownership is ambiguous. The
classifier selects evidence; it does not decide whether a family is complete.
Each selected family must still produce an explicit semantic result:

```text
PASS | FAIL | NOT_APPLICABLE | NOT_EVALUATED | BLOCKED
```

`NOT_EVALUATED` and `BLOCKED` fail mandatory gates.

## Authority boundary

The classifier may map changed repository surfaces to governing families. It
must not infer new requirements from workflow names, historical test counts,
or existing labels. The frozen evidence matrix and the governing INV/SPEC
documents remain authoritative.

## Family manifest

The implementation should use a checked-in declarative manifest with one entry
per family. Each entry must contain:

| Field | Requirement |
| --- | --- |
| `family_id` | Stable identifier such as `CI-ARC-EXEC` or `CI-SCOPE` |
| `governing_authority` | Every governing `INV-ARC` and applicable `INV-CORE` |
| `path_rules` | Repository paths that select the family |
| `evidence_commands` | Exact targeted commands, not broad marker guesses |
| `evidence_kind` | `static`, `runtime`, `persistence`, or `browser` |
| `mandatory` | Whether `NOT_EVALUATED`/`BLOCKED` blocks the change |
| `pass_contract` | What successful execution actually proves |
| `known_limits` | Explicit uncovered subclaims and false-green cases |

The manifest must reject duplicate family IDs, empty evidence commands, missing
authority, and entries with no path rules. A classifier configuration error is
`BLOCKED`, never `PASS`.

## Initial path selection

| Family | Conservative path selectors | Evidence currently available |
| --- | --- | --- |
| `CI-ARC-EXEC` | `app/feats/**`, `app/routes/**`, `app/services/**`, `tests/dom/operation/**`, FEAT docs | FEAT enforcement and transaction slices |
| `CI-SCOPE` | `app/routes/**`, `app/services/context*`, `app/models.py`, identity/class tests, class/identity docs | 27-test scope/identity slice |
| `CI-TEMPORAL` | `app/utils/canonical_temporal_resolver.py`, temporal utilities, class timezone code, temporal tests/docs | 26 resolver tests; required subclaims remain partial |
| `CI-PERSIST` | `migrations/**`, `app/models.py`, class deletion paths, persistence tests, lifecycle docs | 37 persistence tests plus hard-delete test |
| `CI-PII` | `app/models.py`, identity services, identity migrations, deletion paths, PII docs | No complete current evidence; selected changes must fail `NOT_EVALUATED` |
| `CI-XDOMAIN` | `app/domains/**`, `app/feats/**`, `app/routes/**`, `app/jobs/**`, `app/services/**`, migration FK changes | No dedicated current gate; selected changes must fail `NOT_EVALUATED` |
| `CI-RENDER` | `templates/**`, `static/css/**`, `static/js/**`, view-model builders, user-facing routes | Static accessibility only; browser subclaims remain unevaluated |
| `CI-VALIDATION` | `.github/workflows/**`, `scripts/**`, `tests/conftest.py`, CI docs/manifests | Meta-validation of classifier and evidence semantics |

Path rules intentionally over-select routes and services because architectural
authority cannot be inferred safely from filename alone. A later refinement may
narrow selectors only when the governing inventory authorizes the distinction.

## Change event inputs

The classifier must accept:

1. base revision;
2. head revision;
3. event type (`pull_request`, `push`, or manual);
4. changed path list;
5. optional explicit override for emergency/manual revalidation.

It must fail closed if the base/head cannot be resolved or if the changed path
list cannot be obtained. An empty changed path list is not automatically
`NOT_APPLICABLE`; it is `BLOCKED` unless the event contract explicitly proves
that no files were changed.

## Selection algorithm

```text
resolve base and head
        ↓
collect changed paths
        ↓
validate manifest
        ↓
match every path against every family selector
        ↓
apply conservative event-wide families
        ↓
emit selected family IDs and exact evidence commands
```

Conservative event-wide selection:

- migration/model changes select `CI-PERSIST`, `CI-PII`, and `CI-VALIDATION`;
- workflow/script/manifest changes select `CI-VALIDATION`;
- unknown paths select `CI-ARC-EXEC`, `CI-SCOPE`, and `CI-VALIDATION`;
- documentation-only changes select no application family unless the document
  is an authority or CI manifest, in which case `CI-VALIDATION` is selected.

The classifier must report the matching rule for every selected family so a
reviewer can distinguish an intentional conservative selection from a hidden
over-selection.

## Result aggregation

Each family runner returns a structured result, not a free-form green shell
exit. The meta-gate aggregates as follows:

```text
any FAIL          → FAIL
else any BLOCKED  → BLOCKED
else any required NOT_EVALUATED → NOT_EVALUATED
else all selected PASS or NOT_APPLICABLE → PASS
```

An unselected family is not represented as `PASS`; it is explicitly
`NOT_APPLICABLE` for that change. This prevents a meta-gate from converting
absence of execution into evidence.

## Required implementation boundaries

The first implementation slice should contain only:

1. manifest schema and validation;
2. changed-path classifier;
3. machine-readable selection output;
4. unit tests for classifier semantics;
5. no changes to application runtime behavior.

Runtime workflow wiring comes after the classifier demonstrates correct
selection and fail-closed aggregation. Existing targeted tests must be wired by
their exact paths, not by the historical `critical or regression` expression.

## Explicit non-goals

- Do not create constitutional PASS results for `CI-PII`, `CI-XDOMAIN`, or the
  browser portion of `CI-RENDER` before sufficient evidence exists.
- Do not repair unrelated application failures in this classifier slice.
- Do not expand to the full pytest suite.
- Do not change existing workflow triggers until classifier output is reviewed.
