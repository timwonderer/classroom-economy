# CTH v2 Production Readiness — Ship Tracker

| Field | Value |
|---|---|
| Status | **ACTIVE — canonical tracker** |
| Audit date | 2026-09-03 |
| Branch | `codex/landed-architecture-execution-fixes` |
| Audit baseline commit | `09bdc353` |
| Ship target | **2026-09-17** |
| Supersedes | `DOMAIN_PROGRESS_MATRIX_2026.md` (archived — stale as of 2026-08-20, materially wrong on 4+ domains) |

---

## I. How Readiness Was Judged

Readiness is judged **against the normative documents only**: `INV-CORE-000` → `INV-ARC-*` → `DOM-*`.
Phase-completion claims in prior tracking documents were treated as hints, not evidence. Where a
document and the implementation disagree, the document defines the target state and the gap is
recorded here as a finding against the code.

Rubric anchors used:

- **INV-CORE-000 §III.1** — `class_id`-centric isolation; `join_code` is an alias only; `seat_id` anchors actor state
- **INV-CORE-000 §III.2 / INV-ARC-018** — PII never plaintext at rest; encrypted for display, HMAC-hashed for lookup
- **INV-CORE-000 §III.3** — deterministic financial logic; reversal is a counter-entry; **configuration changes must not retroactively alter prior ledger outcomes**
- **INV-CORE-000 §III.4 / INV-ARC-019** — principal (`users.id`) / actor (`seats.id`) / boundary (`classes.class_id`) authority separation
- **INV-CORE-000 §III.5 / INV-ARC-012** — hard deletion; a user with no remaining seats **must** be deleted
- **INV-CORE-000 §III.6 / INV-ARC-013 / INV-ARC-014** — existence-based membership; no lifecycle labels; `block`/`period`/`section` are display metadata and must never drive logic
- **INV-CORE-000 §III.7** — accessibility is a functional requirement, not polish
- **INV-ARC-006** — all mutation crosses the FEAT command boundary
- **INV-ARC-007** — GET handlers are pure
- **INV-ARC-021** — cross-domain coordination goes through a canonical FEAT, never domain-to-domain
- **DOM-POL-001 §VI** — policy repository is append-only and immutable; `policy_uuid` *is* the version

---

## II. Domain Scoreboard

| # | Domain | Verdict | Blocking |
|---|---|---|---|
| 1 | Identity | **NOT READY** | B3 |
| 2 | Class Configuration | READY (with caveats) | — |
| 3 | Ledger | READY (with caveats) | — |
| 4 | Productivity & Payroll | READY (with caveats) | — |
| 5 | Obligations | **NOT READY** | B1 |
| 6 | Store & Entitlements | READY (with caveats) | — |
| 7 | Policies | **NOT READY** | B1, B2 |
| 8 | Interpretation | READY (with caveats) | — |
| 9 | Operations | READY (with caveats) | — |
| 10 | Support | **NOT READY** | B4, B5, B6 |

**6 of 10 domains are production-ready.** Four are blocked by six defects, which collapse into
**three fix tracks** (§IV).

---

## III. Blocking Issues

### B1 — Rent settings mutate in place, retroactively rewriting prior obligations
**Domains:** Obligations, Policies · **Severity:** Critical · **Violates:** INV-CORE-000 §III.3, DOM-POL-001 §VI

`RentSettings.class_id` is `unique=True` (`app/models.py:1052`), so a class has exactly one mutable
settings row. The admin handler reassigns fields on the fetched row and never mints a new
`policy_uuid` (`app/routes/admin.py:5288-5337`). Prior obligation assessments resolve their
`amount_due` from that live row via the frozen `policy_uuid`
(`app/services/obligation_view_model.py:236,275-278`).

Consequence: a teacher editing rent from 50 to 200 silently rewrites the amount owed on every
already-assessed historical cycle. This corrupts financial truth, which is the single hardest
constraint in the system.

*Independently verified against source.*

### B2 — Policy `*_settings` tables are mutable singletons, not append-only versions
**Domain:** Policies · **Severity:** Critical · **Violates:** DOM-POL-001 §VI

`upsert_payroll_settings` mutates the existing row via `setattr`; `PayrollSettings` has **no
`policy_uuid` column at all**. `HallPassSettings` has the same shape. DOM-POL-001 §VI collapses
Insert/Update into a single Insert — every submission must create a new immutable row.

`InsurancePolicy` (`app/models.py:2063-2152`) is the correct reference implementation to copy.

> B1 and B2 are the same defect class. One immutability rework clears both and unblocks two domains.

### B3 — Orphaned `users` rows are never deleted
**Domain:** Identity · **Severity:** High · **Violates:** INV-CORE-000 §III.5, DOM-IDEN-001 §VI, INV-ARC-012, INV-ARC-018

`hard_delete_student_if_orphaned` (`app/utils/student_deletion.py:196`) deletes seats but leaves the
parent `User`. The class-teardown path (`app/routes/admin.py:1276-1290`) has the same gap. The
invariant is unconditional: a user with no remaining seat in any class must be deleted from the
system entirely. Because `User` carries credential material, this is also a PII-retention violation.
No test guards it.

### B4 — Sysadmin escalated-issue and support-ticket views crash (hard 500)
**Domain:** Support · **Severity:** High · **Violates:** INV-CORE-000 §III.7 (function is unreachable)

`_issue_to_view` (`app/routes/system_admin.py:781-797`) reads `issue.teacher`,
`issue.teacher.get_sysadmin_display_name()`, and `issue.class_label`. None exist: `Issue` has no
`teacher` relationship and no `class_label` column, and `get_sysadmin_display_name` is defined
nowhere in the codebase. Affects `escalated_issues`, `view_escalated_issue`, and `support_tickets`.

*Independently verified against source.*

### B5 — Sysadmin view leaks class name, ignoring the consent flag
**Domain:** Support · **Severity:** High · **Violates:** DOM-SUP-001 §VI, INV-CORE-000 §III.4

The same view returns a class label unconditionally, ignoring
`Issue.share_class_name_with_sysadmin` (default `false`). Currently masked by B4's crash — fixing B4
without fixing B5 turns a 500 into a live disclosure.

### B6 — `escalate_issue` mutates state outside a FEAT context
**Domain:** Support · **Severity:** Medium · **Violates:** INV-ARC-006

`escalate_issue` (`app/routes/admin.py:10562-10620`) writes without `@requires_feat_context`, unlike
its siblings `resolve_issue` and `close_issue`.

---

## IV. Fix Tracks

| Track | Clears | Unblocks | Est. | Owner | Status |
|---|---|---|---|---|---|
| **T1 — Policy immutability rework** | B1, B2 | Obligations, Policies | Large | — | Not started |
| **T2 — Sysadmin support surface** | B4, B5, B6 | Support | Medium | — | Not started |
| **T3 — Orphaned-user deletion** | B3 | Identity | Small | — | Not started |

**Sequencing to 2026-09-17.** T1 is the critical path and the only substantial design work; start it
first and in parallel with T2/T3, which are independent and touch disjoint files. T3 is the smallest
and should land first as a confidence check on the regression harness.

**Exit criteria for the ship gate.** All six blockers closed; each with a regression test that fails
against the pre-fix commit; full pytest suite green; `flask db heads` shows exactly one head.

---

## V. Non-Blocking Findings

Carried as post-ship backlog unless a track happens to touch the same code.

**Identity** — teardown logic lives in the route rather than a FEAT; 7 `print()` calls in
`context_resolver.py`; residual `Seat.block` property.

**Class Configuration** — dead FEAT-bypass branch (`app/services/economy_policy.py:289-295`); dead
`replace_enabled_class_features` import; cascade behavior untested; `customizations()` edits
DOM-CLASS fields under a FEAT-IDEN context.

**Ledger** — 3 ops scripts raise `ImportError` on the removed `BalanceCache`; misleading `student`
variable actually bound to a Seat (`app/routes/student.py:761`); residual `join_code` / `user_id`
columns on `Transaction`.

**Productivity & Payroll** — `daily_limit` missing from the `AttendanceReasonCode` enum; pay-rate
selection filters on a block/section label (**INV-ARC-014 violation, promote to blocking if it can
select the wrong rate**); hardcoded `0.25/60` fallback rate; heuristic reversal correlation.

**Store & Entitlements** — dual `StoreItem` / `StoreProduct` catalog; `InsuranceClaim` has mutable
status; reliance on FK cascade rather than explicit teardown.

**Interpretation** — stale docstrings claiming the payload is "partial" and materialization is "NOT
IMPLEMENTED"; both are false. Dead comment in `analytics_engine.py`.

**Operations** — DOM-OPS event tables not built; telemetry still goes to log files;
`combined_logs` / `error_logs` / `network_activity` are stubbed.

**Support** — `update_user_report` handler is dead and incorrect; announcement creation does not
re-verify ownership; zero test coverage on the sysadmin surface.

**Cross-cutting** — 9 Dependabot advisories on the default branch (8 high, 1 moderate); accessibility
remediation tracked separately in `ACCESSIBILITY_REVIEW_2026-09-03.md`.

---

## VI. Maintenance

Update this file when a track changes status or a finding is closed. Record closure with the commit
SHA. Do not create a new dated tracking document for this sprint — amend this one. Historical
tracking artifacts live in `docs/archive/v2-tracking-2026/`.
