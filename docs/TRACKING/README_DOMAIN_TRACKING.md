# Tracking Documents

**Effective:** 2026-09-03
**Replaces:** the `DOMAIN_PROGRESS_MATRIX_2026.md` system (archived 2026-09-03)

---

## What lives here

`docs/TRACKING/` holds **only live, forward-looking work**. Completed phase notes, point-in-time
audits, and superseded plans live in [`docs/archive/v2-tracking-2026/`](../archive/v2-tracking-2026/README.md).

| File | Purpose |
|---|---|
| [`PRODUCTION_READINESS_2026-09.md`](PRODUCTION_READINESS_2026-09.md) | **Canonical tracker.** Domain readiness, blocking issues, fix tracks, ship gate. |
| [`ACCESSIBILITY_REVIEW_2026-09-03.md`](ACCESSIBILITY_REVIEW_2026-09-03.md) | Open accessibility remediation (INV-CORE-000 §III.7). |
| [`DOCS_PLATFORM_ROADMAP.md`](DOCS_PLATFORM_ROADMAP.md) | Documentation platform plan. Post-ship. |
| [`DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md`](DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md) | Reusable SOP-DEV-002 plan template for a single domain. |

---

## Rules

### 1. Readiness is judged from the normative documents, never from a tracker

Authority flows `INV-CORE → INV-ARC → DOM → FEAT`. A tracker records findings; it does not confer
status. When a tracker and a normative document disagree, the document wins and the tracker is
corrected. When a normative document and the code disagree, the document defines the target state
and the gap is a finding against the code.

### 2. Amend, do not accumulate

The previous system failed because each sprint minted a new dated document while the nominally
canonical one silently went stale — by 2026-09-03 the matrix was wrong about four domains. Update
`PRODUCTION_READINESS_2026-09.md` in place. Record closures with a commit SHA.

### 3. Archive on completion, never delete

When a document stops describing live work, `git mv` it to `docs/archive/v2-tracking-2026/` and add
a line to that directory's README explaining why.

### 4. Ephemeral domain plans are fine

Copy the template for one domain's migration, then archive it when the domain certifies. Do not let
it become a second source of truth.

---

## Working a domain

1. Read the domain's normative spec (`docs/DOMAIN/DOM-*.md`) and the invariants it cites.
2. Read the domain's row and findings in `PRODUCTION_READINESS_2026-09.md`.
3. If the work spans multiple phases, copy `DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md`.
4. Land the fix with a regression test that fails against the pre-fix commit.
5. Update the tracker with the closing commit SHA.
