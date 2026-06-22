# SOP-DEV-001: Refactor Best Practices

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEV-001      | 1.1     | 2026-04-01     | 1.0        | Normative       |

---

## I. Purpose

Define the required sequencing and guardrails for refactors so launch-critical delivery,
reconciliation work, and post-launch architecture changes do not get mixed together in a
way that creates invalid intermediate states or unreviewable scope.

---

## II. Scope

This SOP applies to:

- system-wide refactors
- architectural restructuring efforts
- reconciliation waves that touch shared runtime contracts
- cross-domain changes affecting identity, scoping, enforcement, or interface behavior

This SOP governs sequencing and proof obligations. It does not replace architecture
specifications or runtime invariants.

---

## III. Authority Level

Normative. Subordinate to:

- INV-CORE-000 (Foundational Invariants)
- INV-CORE-001 (Authority Model)
- SOP-DOC-000 (Documentation Standard)

This SOP must also remain consistent with the active v2 launch and reconciliation docs when
work is being performed on the v2 launch path.

---

## IV. Dependencies

- INV-CORE-000_CORE_INVARIANTS.md
- INV-CORE-001_Authority_Model.md
- ../../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md
- docs/TRACKING/V2_LAUNCH_PROJECT_CHECKLIST.md
- docs/TRACKING/V2_MAIN_RECONCILIATION_TRACKER.md
- docs/TRACKING/V2_LAUNCH_READINESS_MATRIX.md

---

## V. Core Rule

Refactors MUST follow the active program phase.

There are two valid modes:

### 1. Launch Stabilization Mode

Use when the branch is closing live-test or production blockers.

In this mode:

- correctness, safety, and source-of-truth reconciliation come first
- structural cleanup is allowed only if it is required to land the blocker safely
- deferred architecture targets MUST remain deferred unless explicitly re-scoped
- shared-file churn MUST be minimized

### 2. Post-Launch Architecture Mode

Use when launch-blocking reconciliation work is closed and architecture work has been
explicitly opened as its own project.

In this mode:

- deeper identity, scope, enforcement, and interface restructuring may proceed
- structural refactors MUST still preserve behavior unless the governing spec says
  otherwise
- migration and interface changes MUST be sequenced so each intermediate state is valid

---

## VI. Required Execution Order

### A. Launch Stabilization Mode

All major launch-path changes MUST follow this order:

1. Source-of-truth capture
2. Runtime invariant definition
3. Reconciliation or blocker fix
4. Proof of correctness
5. Active-document update

#### 1. Source-of-Truth Capture

- the governing tracker, spec, or source branch delta MUST be identified first
- work MUST be grouped by shipped behavior, not by commit count alone
- deferred architecture targets MUST be identified before editing shared files

#### 2. Runtime Invariant Definition

- the invariant being preserved or restored MUST be written down before implementation
- if current runtime and target architecture differ, the current runtime contract MUST be
  stated explicitly
- request-level convenience scope MUST NOT be mistaken for canonical write authority

#### 3. Reconciliation Or Blocker Fix

- implement the narrowest change that restores correctness or required parity
- prefer manual reconciliation over blind cherry-pick when schema or scope models diverge
- use v2-native migrations when the branch history has materially diverged

#### 4. Proof Of Correctness

- required regressions MUST be ported or updated in the same wave
- operational verification steps MUST be recorded for user-visible or money-sensitive
  behavior
- launch blockers are not considered closed until the corresponding proof exists

#### 5. Active-Document Update

- active docs MUST be updated in the same wave if runtime contract wording changed
- readiness and reconciliation trackers MUST reflect the new truth immediately

### B. Post-Launch Architecture Mode

Once launch stabilization is complete, major refactors MUST follow this order:

1. Identity
2. Scope
3. Enforcement
4. Services / domain extraction
5. Interface cleanup

#### 1. Identity

- authoritative identifiers MUST be explicit
- lifecycle semantics MUST be deterministic
- identity MUST NOT be inferred implicitly

#### 2. Scope

- one authoritative scoping model per domain MUST be chosen
- fallback or mixed scoping models MUST be removed
- teacher ownership and class data scope MUST remain distinct concepts

#### 3. Enforcement

- invalid states MUST be prevented structurally where feasible
- constraints SHOULD move closer to the database or schema boundary when the project is
  specifically hardening invariants
- application-only enforcement MAY exist temporarily only if the project plan documents
  the follow-up structural step

#### 4. Services / Domain Extraction

- business logic SHOULD move out of route/controller files
- destructive and invariant-heavy workflows SHOULD be isolated first
- extraction MUST preserve behavior and avoid opportunistic schema churn

#### 5. Interface Cleanup

- routes, APIs, and UI logic should become thin representations of the stabilized domain
- interface cleanup MUST NOT be used to hide unresolved identity or scope problems

---

## VII. Stage Gates

Progression is prohibited when any of the following is true.

### A. Launch Stabilization Gates

- the source document or parity target is unclear
- the runtime invariant is not stated
- the change set mixes blocker work with unrelated architecture cleanup
- tests or operational verification for the targeted behavior are missing
- active docs would be left knowingly inaccurate after the change lands

### B. Post-Launch Architecture Gates

- identity remains ambiguous
- multiple scoping strategies still coexist in the target domain
- constraints are being delegated to interface code to compensate for missing invariants
- service extraction is being used to mask unresolved model or scope contradictions
- interface cleanup begins before the domain contract is stable

---

## VIII. Shared-File And Parallel-Work Rules

- one thread owns one write set at a time
- shared files MUST have a named owner during concurrent work
- analysis and test preparation may happen in parallel, but final integration into shared
  files waits for the owning thread
- route and template churn should settle before schema-heavy follow-up waves land

---

## IX. Prohibited Patterns

The following are prohibited:

- mixing launch-blocker fixes with broad architecture rewrites in one wave
- replaying divergent migrations from another branch without schema comparison
- treating request parameters as canonical write authority when session authority is the
  active runtime rule
- refactoring interface layers to compensate for unresolved domain invariants
- retaining compatibility shims without naming whether they are active, transitional, or
  removal candidates
- silently promoting deferred architecture notes into active scope

---

## X. Required Deliverables For A Major Refactor

Every major refactor or reconciliation wave MUST name:

1. governing source document
2. build order and dependencies
3. invariants being preserved or introduced
4. owned files or write set
5. migrations, if any
6. required tests
7. operational verification, if applicable
8. active-doc updates, if applicable

---

## XI. Guiding Principles

- Launch work optimizes for correctness and controlled scope.
- Architecture work optimizes for clearer long-term invariants after launch risk is down.
- A clean execution order matters, but the correct order depends on whether the project is
  closing blockers or performing deferred structural cleanup.

---

## XII. Amendment

Revisions to this document MUST:

1. increment the version number per SOP-DOC-000
2. update the Effective Date
3. update the Supersedes field
4. remain consistent with the active invariant and launch-governance documents
