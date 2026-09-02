# Changelog

All notable changes to the Classroom Token Hub project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows semantic versioning principles.


## [Unreleased]

### Fixed

- **FEAT execution-boundary remediation, part 1 — insurance policy creation unblocked + the Obligations orchestration cluster stops executing other FEATs (2026-09-02)** — Creating an insurance policy through the admin route crashed with `FEATContextError: Illegal nested FEAT context` because FEAT-CLASS-003 (`configure_insurance_definition`) executed FEAT-POL-001 (`execute_store_insurance_definition`) — a FEAT-to-FEAT call, forbidden by INV-ARC-000 §VIII.2 ("exactly one command path per request") and INV-ARC-021 §V.2 (the FEAT is the sole composition layer, within one execution path); mutation belongs in explicit **domain commands** (INV-ARC-006). The guard was correctly catching a real architectural violation; the tests missed it only because they passed `corr_`-prefixed correlation ids that coincidentally normalized to match, while the route's unprefixed id tripped the string comparison. Fix: FEAT-CLASS-003 now invokes the POL **domain commands** (`insurance_definition_service.create_insurance_definition` / `set_availability`) directly, never the FEAT-POL-001 executor (admin creation route regression added: `tests/test_admin_insurance_creation_route.py`). A repo-wide audit then showed the pattern is systemic; part 1 remediates the **Obligations orchestration cluster**: `FEAT-OBL-004` (insurance purchase), `rent_payment`, `reconcile_rent`, and the `nsf_fee` helper now compose the Obligations **domain commands** (`establish_bill_cycle` / `advance_bill_cycle` / `assess_obligation` / `satisfy_obligation` plain functions) within their single FEAT context instead of calling `execute_*` FEAT wrappers; the decorative `context=FEATContext(...)` params on those wrappers are cleaned to `context=None`. Business semantics are unchanged (Obligations/Insurance/Rent/NSF regressions green: 45 + 22 + 11 passed across runs). **Deferred to part 2** (a larger, system-wide effort touching the canonical monetary workflow and payroll): removing the FEAT-CORE-000 §V.2 "Core-FEAT" carve-out, refactoring `FEAT-STOR-001/003 → FEAT-LED-000` and `→ FEAT-PROD-002/003` (surfaced by a structural AST check), hardening `FEATContext` to reject any nested FEAT entry regardless of feat_name/correlation, and adding the structural CI + boundary tests — none of which can land until those remaining callers are clean.

### Added

- **Insurance claim form migrated off the dead integer-policy model (insurance-purchase arc, 2026-09-01)** — `GET/POST /student/insurance/claim/<policy_uuid>` replaces the old `<int:policy_id>` route (no compatibility shim — the legacy shape is deleted, not redirected). The route resolves the student's **active INSURANCE entitlement for exactly this policy, class-scoped** (`_active_insurance_entitlement_id`: matches the grant's immutable `policy_uuid`, excludes EXPIRED/REVOKED lineages) and **fails closed** if the student doesn't currently hold that coverage — even when the UUID names a real policy in the same class. `policy_uuid` is never resolved globally. The claim form is a real WTForms `InsuranceClaimForm` (replacing the `_DummyField` shell) and presents policy terms from the canonical `insurance_policies` read (no snapshot, no terms reconstructed in the template — INV-ARC-022); TRANSACTION policies pick from the student's eligible money-out transactions (filtered by the lawful `insurance_eligibility_contract` sets; the FEAT remains the eligibility authority), and submission drives **FEAT-STOR-003** `submit_insurance_claim`. Rebuilt `templates/student_file_claim.html` on the canonical shape and linked "File a claim" from each owned-coverage card. Both monetary and productivity surfaces are supported: **TRANSACTION** policies pick an eligible transaction; **PRODUCTIVITY** policies get a repeatable **date + hours + explanation** multi-day surface (JS "add another day") that posts the canonical `claimed_dates` list of `{date, hours, explanation}` (+ optional claim-wide `additional_information`), exactly the shape FEAT-STOR-003 parses — the FEAT stays the authority on class-local date eligibility, worked-hours capacity, and the two-resource payout rule (non-monetary policies, unsupported by the claim FEAT, are gated with a clear message). Tests (in `tests/test_insurance_purchase_route.py`): a covered student renders the transaction form and submits a claim FEAT-STOR-003 records; a student without coverage is redirected (fail-closed) with no claim written; the productivity surface renders its multi-date rows and its submission is parsed and adjudicated by FEAT-STOR-003 (approval depends on the student's work records — covered end-to-end in `test_insurance_claim_feat.py`).

- **Students can buy insurance again — the marketplace/purchase routes are wired to FEAT-OBL-004 (insurance-purchase arc slice E, 2026-09-01)** — The student insurance surface, dead since it was left on the retired `PolicyVersion(domain="insurance")` model, is rebuilt on the canonical model end-to-end. `GET /student/insurance` now lists the class's **`IN_USE` `insurance_policies`** (title, type, premium/cadence, reimbursement %, payout multiple, claim window) with an owned-coverage indicator, plus the student's active coverage (resolved from `EntitlementEvent` history through the immutable policy) and their claims. `POST /student/insurance/purchase/<policy_uuid>` (was `<int:policy_id>` against `PolicyVersion`) drives **`execute_purchase_insurance`** (FEAT-OBL-004): a purchase assesses + satisfies the first premium and grants the `INSURANCE` entitlement atomically, with friendly flash messages for `POLICY_ALREADY_HELD` / `INSUFFICIENT_FUNDS` / unavailable / not-found. A fresh per-request idempotency key means a double-submit is caught by `POLICY_ALREADY_HELD` (never a double charge) while a lawful re-purchase after cancellation starts a clean lineage. Rebuilt `templates/student_insurance_marketplace.html` on the canonical shape (dropping the legacy tier/enrollment/`policy.id` machinery); the still-legacy claim-form / cancel / view-policy routes are intentionally not linked yet (their rewiring is the next sub-slices). Folded in the earlier guards that keep INSURANCE entitlements out of the *general* store item display (`student.py`) and the availability-based badge on the admin insurance page (`For sale` / `Hidden — winding down`). Tests: new `tests/test_insurance_purchase_route.py` (marketplace lists a policy and a funded student buys it end-to-end → coverage active and shown as owned; insufficient funds flashes and writes nothing); the existing `/student/insurance` schema-surface check still passes. *Known limitation:* FEAT-OBL-004 derives its correlation/ledger identifiers from the `idempotency_key`, so a very long caller-supplied key can overflow a `varchar(100)` column — the route passes a short key; bounding this inside the FEAT is a follow-up.

### Changed

- **Insurance claims resolve the immutable policy via `policy_uuid` — the frozen snapshot model is dead (insurance-purchase arc slice D, 2026-09-01)** — FEAT-STOR-003 (insurance claim lifecycle) now computes all eligibility and economics from the **immutable `insurance_policies` definition**, resolved through the GRANTED entitlement's `policy_uuid` (`_resolve_claim_policy`), instead of reading a `frozen_contract` payload snapshot. Because a policy edit mints a *new* `policy_uuid`, the exact row an entitlement references cannot change after purchase — it *is* the frozen contract, same non-retroactivity guarantee, with **no duplicated policy terms in the entitlement payload** (INV-ARC-009, DOM-STORE-001 §VII.A). The entitlement proves acquisition; the policy provides the terms. **Strict, no compatibility fallback** (per the pre-release directive): a claimed grant that carries no `policy_uuid`, or a `policy_uuid` that does not resolve within the claim's class, **fails closed** (`POLICY_UNRESOLVABLE`) — there is no `if policy_uuid … else frozen_contract` third path. With the last runtime reader gone, **deleted** the frozen-contract machinery entirely: `app/services/frozen_insurance_contract.py` (the `parse_frozen_contract`/`get_frozen_insurance_contract` reader + `FrozenInsuranceContract` model) and `app/services/insurance_contract_freeze.py` (the `build_frozen_contract`/`build_purchase_metadata` writer). Reworked the claim tests to create real immutable `insurance_policies` rows (via `create_insurance_definition`) and grant entitlements carrying only `{policy_uuid}`, replacing the synthetic frozen payloads; deleted `tests/test_insurance_claim_freeze_read.py` (it tested the now-deleted reader). Added fail-closed tests for missing and wrong-class `policy_uuid`. FEAT-STOR-003 doc → v1.2 (claim-time authority is the immutable policy row). Claim FEAT green (38 + 2 new fail-closed = 40 passed); no runtime claim dependency on frozen insurance payloads remains — the old snapshot system is genuinely dead, not merely unused.

### Removed

- **Insurance removed from the Store purchase path — the loose thread is cut (insurance-purchase arc slice C, 2026-09-01)** — Now that FEAT-OBL-004 owns insurance acquisition (slice B), the misbuilt store-based insurance purchase is deleted. `execute_store_purchase` (FEAT-STOR-001) is StoreProduct-only again: its entire INSURANCE branch is gone — the `insurance_policies` resolution, the availability re-check, the premium reconciliation, the `build_frozen_contract`/`build_purchase_metadata` snapshot, and the `frozen_contract`/`purchase_metadata`/`insurance_policy_uuid` payload writes — replaced by a single guard that rejects any INSURANCE-typed policy (`INSURANCE_NOT_PURCHASABLE_VIA_STORE`, directing to FEAT-OBL-004). Deleted `app/feats/store_publication_feat.py` (FEAT-STOR-007 "Publish Insurance Product") and its registry entry — the StoreProduct wrapper for insurance no longer exists, so nothing publishes one. Deleted the tests that exercised the misbuild: `tests/test_insurance_purchase_freeze_feat.py` (StoreProduct-based purchase — its behavioral assertions were ported to FEAT-OBL-004 in slice B per INV-ARC-017) and `tests/test_insurance_publication_feat.py`. Amended FEAT-STOR-001 to v3.1 (§II narrowed to "sole writer of PURCHASE grants for actual Store products"; insurance out of scope; stale insurance error codes replaced). Deliberately **kept** the frozen-contract model (`insurance_contract_freeze` / `frozen_insurance_contract`) — the claim path still reads it, and it disappears with the claim rework in slice D. Regression green: general store purchase + claim freeze-read + FEAT-OBL-004 (25 passed); app boots (199 routes) with no dangling references.

### Added

- **FEAT-OBL-004 Insurance Policy Purchase / Enrollment (insurance-purchase arc slice B, 2026-09-01)** — New dedicated insurance-purchase FEAT (`app/feats/purchase_insurance_feat.py::execute_purchase_insurance`) that resolves the class-scoped immutable `insurance_policies` definition and orchestrates the acquisition as an **Obligations** action — NOT a branch of `execute_store_purchase`, and with **no `StoreProduct`** anywhere in the path. Atomic spine under one FEAT transaction: resolve `policy_uuid` under `class_id` → verify `IN_USE` → reject same-policy concurrent coverage (`POLICY_ALREADY_HELD`, derived from entitlement history via new `entitlement_read_service.has_active_insurance_coverage`) → **`establish_bill_cycle`** genesis (cycle 1, records the next recurring-premium boundary from the policy charge cadence via canonical temporal evaluation) → assess `INSURANCE_PREMIUM` for cycle 1 → satisfy it through the canonical Ledger path (`create_pending_transaction_idempotent` + `execute_satisfy_obligation_payment`) → grant the `INSURANCE`/`PURCHASE` entitlement (new `entitlement_service.grant_insurance_entitlement`, which references `policy_uuid` in the event payload and snapshots no policy terms — DOM-STORE-001 §VII.A) → commit. `policy_uuid` is the frozen contract; terms are retrieved later by resolving the immutable row, never copied forward. Idempotency is command-owned: `correlation_id` embeds the `idempotency_key`, so a same-command replay returns the original grant (`already_enrolled`) while a different command that finds active coverage is rejected `POLICY_ALREADY_HELD`. Registered `FEAT-OBL-004` (HIGH blast radius) in the FEAT registry. **The FEAT is built and tested but intentionally unwired** — the old Store-based insurance purchase path is left fully intact (its removal is slice C; route wiring is slice E). Tests (`tests/test_insurance_purchase_feat.py`, 7 passed): the centerpiece is transaction-boundary behavior — insufficient funds / unavailable policy / policy-not-found write **nothing**; a successful purchase leaves **exactly one** cycle-1 assessment, satisfaction, grant, bill cycle, and premium debit; a same-key retry adds no duplicates; a different key after success is `POLICY_ALREADY_HELD`; and an injected failure during the grant (after the premium is charged) **rolls the entire transaction back including the Ledger post** — proving atomicity is real, not prose.

- **Bill-cycle genesis is now an explicit Obligations command (DOM-OBL-001, insurance-purchase arc slice A, 2026-09-01)** — Separated bill-cycle **genesis** (`nothing → cycle 1`) from **advancement** (`cycle N → cycle N+1`), which had been silently conflated: `reconcile_rent` created its first cycle via `execute_advance_bill_cycle(cycle_number=1)` even though FEAT-OBL-002's contract defines "advance" as successor-only. New `app/feats/establish_bill_cycle_feat.py::establish_bill_cycle` / `execute_establish_bill_cycle` establishes cycle 1 with a hard precondition that **no prior cycle exists** for the lineage — a second genesis raises `BillCycleLifecycleError` regardless of idempotency key (idempotency guards retries, not a second cycle 1). `cycle_number = 1` is intrinsic, never caller-selected. Genesis carries no new FEAT-registry number; it runs under the shared `FEAT-OBL-002` bill-cycle authority (the genesis-vs-advancement distinction lives in the command contracts). Introduced `BillCycleLifecycleError` in `obligations_service`. This is slice A of the FEAT-OBL-004 insurance-purchase arc (see `docs/FEATURE-EXECUTION/FEAT-OBL-004_INSURANCE_POLICY_PURCHASE.md`); it provides the lawful genesis primitive that insurance enrollment needs before any recurring premium can be assessed.

### Changed

- **Bill-cycle advancement is now advancement-only (FEAT-OBL-002 v1.1, 2026-09-01)** — `advance_bill_cycle` now **requires an existing current cycle** (raises `BillCycleLifecycleError` if none — advancement is not genesis) and **derives-and-verifies** the strict successor number (`current + 1`), rejecting any non-sequential value; the caller-supplied `cycle_number` serves only as the replay/idempotency key and is checked against the derived successor. Migrated `reconcile_rent_feat` genesis from `execute_advance_bill_cycle(cycle_number=1)` to `execute_establish_bill_cycle`, so rent no longer relies on the old contract overloading. Amended the governing docs in the same change (INV-ARC-017): FEAT-OBL-002 spec (§I/§IV/§V, advancement-only + derived successor) and DOM-OBL-001 (§V.7 genesis/advancement/termination lifecycle; `bill_cycles` generalized from rent-only to any continuing obligation-producing relationship, distinguished by `internal_ref`/`obligation_type`). Tests: new `tests/test_bill_cycle_genesis.py` (genesis produces cycle 1; second genesis fails even as a fresh invocation; advance rejects genesis; advance rejects non-sequential successor; sequential advance succeeds); updated `tests/dom/obligations/test_obligations_domain.py` to the split lifecycle. Genesis + obligations (15 passed) and rent/obligation regression (32 passed) green.

- **Interpretation page made teacher-legible (DOM-ITR-001, slice §8.4c-follow-up, 2026-09-01)** — Reworked the ITR presentation content so a teacher can *interpret* the page rather than re-analyze it, and renamed the surface to **Interpretation** (route `/admin/interpretation/`, nav label + `insights` icon). Each of the seven sections now carries a **"How to read this"** explanation (a calm callout, not an alert) stating both what the section shows and how to make sense of it — e.g. resources: "money left over at the end, not money earned … watch the 'at or below zero' count." Every number is phrased in plain, contextual language instead of statistical jargon: balance distributions read as "Half the class ended with $32.00 or more · Most students were between $8.00 and $61.00 · 2 students ended at or below $0.00 · Average $36.50" (no raw percentiles); a rate leads with the graspable count ("48 student-started transactions this cycle") and gives the per-day figure as context; income sources and obligation outcomes use friendly labels ("attendance-based work", "paid in full", "waived", "unpaid") with money framing ("$700.00 paid by students, $150.00 waived, $150.00 left unpaid"); amounts render as `$`. The resilience `signal_set` now **names and explains each independent signal on its own line** (Attendance per student, Obligation outcomes, Checking/Savings/Total balances, Teacher support, Persistence across cycles) so multiple signals under one category are never an undifferentiated blob. Purely a presentation-layer change: no compute, no contract, still a pure no-recompute transform over the frozen record, and guiding questions remain non-prescriptive. Tests updated to the new legible strings; presentation + template + route + accessibility green (32 passed, 1 skipped).

### Removed

- **V1 Analytics retirement — DOM-ITR has replaced it (slice §8.4d, 2026-08-31)** — With the teacher surface fully on DOM-ITR, the retired V1 interpretation authority is deleted from runtime. Removed: `app/utils/analytics_engine.py` (the `AnalyticsEngine`, `generate_alerts`, `suggested_action`, snapshot/cache semantics, and per-window threshold machinery), `app/services/analytics/` (the old dashboard builder `build_analytics_dashboard_view` + `AnalyticsWindowView`/`AnalyticsDashboardView`), and the `ANALYTICS_POLICY_DEFAULTS` / `get_analytics_policy` thresholds from `app/utils/economy_policy.py` (the legitimate `POLICY_MODES` economy config is untouched). The `analytics` blueprint is slimmed to the single Interpretation route: the `AnalyticsEngine`-backed `api_snapshot`, `api_alerts`, `acknowledge_alert`, `events`, and the individualized `student_drill_down` (a student-vs-CWI surface the DOM-ITR dignity constraint forbids — teachers investigate specific students through the authoritative source domains) are retired, along with their orphaned templates (`admin_analytics_events.html`, `admin_analytics_student_detail.html`) and the now-dead window/cycle helper machinery. The transitional `metrics`/`recent_events` compatibility fields are removed from `InterpretationPageView` now that the template (8.4c) no longer needs them. Doctrine/status updated to truth: DOM-ITR-001 §XIII marks Threshold Ownership and the `suggested_action` runtime disposition **RESOLVED (by deletion)**, and SPEC-ITR-001 §14.5 records the removal; archived/log records are left as history. Retirement guards (`tests/test_analytics_retirement.py`): runtime references to `AnalyticsEngine`, `suggested_action`, and `ANALYTICS_POLICY_DEFAULTS` (and the builders/window views/alerts) are **0**; the retired modules are unimportable; the analytics blueprint exposes only `analytics.dashboard`; and `POLICY_MODES` remains intact. Obsolete tests (`test_analytics_builders.py`, `test_analytics_events_route.py`) removed.
  - *Here lies `suggested_action`. It told exactly one teacher what to do. That teacher had written the advice himself. 2025–2026.* 🫡

### Changed

- **Interpretation page template — the teacher surface is reborn (INV-ARC-022 / INV-ARC-020, slice §8.4c, 2026-08-31)** — `templates/admin_analytics_dashboard.html` is rewritten as a **pure consumer** of the ITR page view model: it renders the seven themed sections (participation, activity, obligations, savings, income, resources, resilience) and never branches on `candidate_id` or `value.kind` — 8.4a already translated those into presentation objects (INV-ARC-022; a test strips Jinja comments and asserts the template code contains neither). Each observation follows **observation first → context second → question third, never a verdict**: the value and supporting counts, then the plain-language explanation, then — only when present — a collapsed, keyboard-accessible `<details>` "Questions to consider" disclosure (native semantics, visually modest, never an alert box and never competing with the observation). `not_applicable` reads intentionally ("Not applicable this cycle. Savings is disabled for this class this cycle.") rather than a dash, 0, or empty card. Empty history is a real page state ("No completed interpretation yet — Interpretation will appear after the first payroll cycle is completed") with **no** "generate analytics" cue that would revive the old on-demand mental model. No badges, no green/red, no "good"/"concerning". As a template slice it meets the accessibility contract (INV-ARC-020): the layout's single `h1`, logical `h2`→`h3` heading order, an accessible no-JS GET cycle selector (`<label for>` + named submit), visible keyboard focus on disclosures, and no color-only meaning. Tests: `tests/test_interpretation_page_template.py` (pure-consumer check; the rendered page passes the canonical accessibility audit — one h1, named controls, labeled selects, no duplicate ids; all seven sections render; a value renders; `not_applicable` reads intentionally; guiding questions are collapsed `<details>` disclosures; empty state carries no generate cue). Existing accessibility + route-cutover regressions green.

- **Interpretation page authority cutover — route now reads DOM-ITR, not AnalyticsEngine (INV-ARC-022 / INV-ARC-007 / INV-CORE-000, slice §8.4b, 2026-08-31)** — Authority cutover only, no visual redesign: the `/admin/analytics/` dashboard route is now fed by the DOM-ITR read/presentation layer over immutable `interpretation_cycle_record`s and no longer touches `AnalyticsEngine`, `get_or_create_snapshot`, or alert generation. New page view model `app/services/interpretation/page_view.py` (`build_interpretation_page_view`) composes `list_cycle_summaries` + `get_latest_cycle_view`/`get_cycle_view` into a single page contract; the route assembles it from lawful domain reads without reconstructing domain truth (INV-ARC-022). Four boundaries held hard: **no mixed authority** — zero `AnalyticsEngine` reads on the page (the legacy template renders confused-but-200 until 8.4c updates it; the page view exposes empty `metrics`/`recent_events` purely as transitional crash-safety for the old template's iteration); **empty history is a first-class state** — a class with no cycle record yet is `awaiting_first_completed_cycle`, rendered successfully, never an error or a recompute cue; **cycle drill-down is class-scoped** — a `?cycle=` selection resolves under the active `class_id` and fails closed (404) for a cycle not belonging to the class (INV-CORE-000); **GET stays pure** — the old route's `get_or_create_snapshot` write on view is gone; the ITR read service consumes frozen records only (INV-ARC-007). The `AnalyticsEngine`-backed API endpoints (`api_snapshot`, `api_alerts`, `student_drill_down`) are untouched here — they are retired wholesale in 8.4d. Tests: `tests/test_analytics_route_cutover.py` (page view latest+ordered history; empty-state; class-scoped selection; HTTP 200 with/without history; unknown/cross-class cycle → 404; GET writes nothing; and an AST identifier check proving the `dashboard` route references none of `AnalyticsEngine`/`get_or_create_snapshot`/`create_snapshot`/`generate_alerts`/`build_analytics_dashboard_view`). Existing analytics regression green (28).

### Added

- **ITR-owned read/presentation models over cycle history (DOM-ITR-001, INV-ARC-022, slice §8.4a, 2026-08-31)** — The first upward slice: a clean domain-owned presentation contract the route/template can consume without knowing anything about JSONB storage or candidate internals (no `candidate_id == "Q3-C2"` or `value.kind == "coverage_by_type"` logic ever reaches a template). No compute, no route, no template changes. New `app/services/interpretation/read_service.py` (`list_cycle_summaries`, `get_cycle_view`, `get_latest_cycle_view` — all class-scoped) and `app/services/interpretation/presentation.py`. Three surfaces: a **cycle-history** projection (`InterpretationCycleSummary`); a **cycle-detail** presentation (`InterpretationCycleView` → seven themed `InterpretationSection`s — participation, activity, obligations, savings, income, resources, resilience — of `ObservationPresentation`s with plain titles, summaries, formatted values, supporting counts, humanized qualifiers/applicability, and attached guiding questions); and value formatters that transform every stored value-kind (fraction, ratio, rate, amount, distribution, category_fractions, category_fractions_by_type, coverage_by_type, counts, signal_set) into teacher-readable text. **Presentation consumes the frozen record and never recomputes** — the module has no import of the compute layer, so reviewing cycle N returns the interpretation materialized when cycle N closed (a durable historical record, DOM-ITR-001 §VII/§IX), proven by a test whose stored `99 of 100` value could not come from the 4-student class. **Guiding-question contract (ITR presentation doctrine):** guiding questions are non-prescriptive presentation content attached here, never frozen into the immutable record; `GUIDING_QUESTION_CONTRACT` + an enforceable `validate_guiding_question` reject any question that presumes causation, characterizes an observation as desirable/undesirable, implies a preferred conclusion, or encodes an intervention — so `suggested_action` cannot sneak back wearing a fake mustache. Trend presentation deliberately postponed. Tests: `tests/test_interpretation_presentation.py` (all curated questions pass the contract and prescriptive/non-question phrasings are rejected; every value-kind renders; the frozen record is read without recompute; not_applicable/qualifiers humanized; history is class-scoped and ordered; and a real payroll-materialized record presents all 17 candidates across the 7 sections).
- **Automatic (scheduled) payroll — a second lawful caller of FEAT-PROD-004 (DOM-PROD-001 §XV, slice §8.3f, 2026-08-31)** — Automatic payroll now closes the payroll tranche by becoming merely another *initiation mechanism* for the same canonical completion, with the mechanism difference ending entirely at ingress. New `run_automatic_payroll_job()` (`app/scheduled_tasks.py`, registered hourly, `max_instances=1`) owns exactly one question — *"is this class due for automatic payroll now?"* (`PayrollSettings.is_active` and `next_payroll_date <= now`) — then constructs the class actor context, resolves the window via the shared `get_completed_cycle_window`, and calls `complete_payroll_cycle` inside `FEATContext("FEAT-PROD-004")`. It contains **no** payroll, interpretation, or activation logic of its own. **Scheduler-retry idempotency without a new job-run substrate:** the idempotency key is derived from the *scheduled occurrence* — `f"auto-payroll:{class_id}:{next_payroll_date.isoformat()}"` — so every retry of the same occurrence shares one key (the `payroll_cycle_completion` anchor makes it a no-op), while the next intended occurrence gets a new key once `next_payroll_date` advances. Neither derived from the downstream `payroll_cycle_id` nor a per-invocation random nonce. Each class runs under its own top-level FEAT transaction (a plain loop, no shared FEAT context), and the `next_payroll_date` advance (by `payroll_frequency_days`) commits atomically with the cycle so a failed run stays due under the same key. Safe by default: a class with no `next_payroll_date` never auto-fires. Tests: `tests/test_automatic_payroll_job.py` (a due class runs the full lifecycle and advances its next date, then a second tick is inert; a not-due class is skipped; re-arming the same occurrence resolves the completed run and reproduces nothing). This closes the payroll tranche — manual and automatic payroll are now two initiation mechanisms for one economic-cycle completion operation, producing real `interpretation_cycle_record` history for the upcoming 8.4 ITR presentation work.
- **Manual payroll runtime cutover to FEAT-PROD-004 (DOM-PROD-001 §XV, slice §8.3e, 2026-08-31)** — The manual `/admin/run_payroll` route now drives the canonical economic-cycle completion instead of its own per-seat loop: the old seat enumeration + `record_payroll_event` batch is deleted and replaced with a single `complete_payroll_cycle(...)` invocation inside `FEATContext("FEAT-PROD-004")`. There is now exactly one payroll-completion implementation. The route sources its closed-cycle window from a new **PROD-owned boundary read** `get_completed_cycle_window(class_id, boundary_utc)` (`app/services/payroll/cycle_completion.py`) — the window opens at the last class-level `payroll` accrual (`max(PayrollEvent.recorded_at)` for `payroll_event_type='payroll'`, so per-student events define the class boundary; `manual_credit`/`reversal` do not) and falls back to class genesis (`ClassEconomy.created_at`) for a class's first cycle — rather than deriving it from route-local timestamp archaeology. Manual payroll is idempotent per a client-supplied `idempotency_token` (one rendered page carries one token → a double-submit resolves as a replay; a fresh render is a new intended run). Tests: `tests/test_run_payroll_route_cutover.py` proves a real HTTP `POST /admin/run_payroll` produces the full lifecycle (PayrollEvent rows stamped with the run's `payroll_cycle_id` → one complete `interpretation_cycle_record` → pending next-cycle policy activated → `payroll_cycle_completion` anchor) and that replaying the same command reproduces nothing (no new events, one ITR record, same cycle id); `get_completed_cycle_window` unit tests (genesis when no prior payroll; last-accrual boundary; `manual_credit`/`reversal` ignored); and the existing `test_run_payroll_empty_desk` regression now flows through the FEAT unchanged. Automatic/scheduled payroll remains a separate later slice — merely another lawful caller of this same route-shared FEAT.
- **FEAT-PROD-004 Complete Payroll Cycle orchestration — payroll completion becomes the constitutional boundary (DOM-PROD-001 §XV, slice §8.3d, 2026-08-31)** — The integration slice: `complete_payroll_cycle` (`app/feats/complete_payroll_cycle.py`) composes the independently-certified substrate into one flat, atomic lifecycle — **replay guard → allocate cycle id → PROD settle → ITR compute+materialize → CLASS activate next-boundary → record completion → one commit** — owning nothing but sequencing and atomicity. Two orderings are held as hard invariants: **the replay guard is literally first** (a completed replay resolves the completion anchor and returns *before* any cycle-id allocation, timestamp, config read, `reference_configuration` capture, or ITR/CLASS work — protecting the historical-configuration seam 8.2c exposed), and **`record_run_completion` is literally last before commit** (the anchor exists iff the entire cross-domain transition committed). The orchestrator does not derive boundary legality (the lawful closed-cycle window is a caller input) and does not commit (it runs inside the caller's `FEATContext("FEAT-PROD-004")`, which owns the single commit and fail-closed rollback); a discovered gap would be a missing substrate slice, never absorbed here. Tightened the FEAT-PROD-004 doctrine (§II.2, §III steps 0/1/5/6) to make replay-resolves-before-allocation explicit now that the persistent replay substrate exists. Tests: `tests/test_complete_payroll_cycle.py` — a normal run (PROD events + one complete ITR record + CLASS P17→P18 activation + one completion anchor, all sharing the cycle id); a spied replay proving the same `payroll_cycle_id` is returned with **zero** downstream calls (allocate/settle/compute/materialize/activate/record all `assert_not_called`); the full failure-injection matrix (PROD fail; ITR compute fail after PROD flushes; ITR materialize fail; CLASS activation fail; completion-anchor fail — each rolls back **everything**, and the CLASS/completion cases prove the policy lineage is restored) and a commit-time abort leaving no resolvable completed run; plus no-pending-transition completing with a lawful activation no-op. **Deliberately excluded:** automatic/scheduled payroll — the scheduler becomes merely another lawful caller of this canonical FEAT in a later slice, never smuggled in here.
- **CLASS next-boundary policy activation (DOM-CLASS-003, slice §8.3c, 2026-08-31)** — Third 8.3 substrate slice: the narrow CLASS command that applies a class's authoritative pending `next_boundary` policy transition exactly once at a payroll boundary. New `apply_next_boundary_transition(class_id, boundary_at)` (`app/services/class_boundary_activation.py`) owns only policy-lineage mechanics: find the authoritative pending transition, activate its target version, deactivate the prior active version (same class + domain), mark the transition `applied`, record `applied_at` — **no commit** (the orchestrator owns atomicity). Held hard per DOM-CLASS-003: **no boundary interpretation inside CLASS** (the caller supplies a boundary already established as lawful; CLASS never asks whether payroll "really completed"); **exactly one authoritative pending transition** (zero → lawful no-op; more than one → fail-closed `BoundaryActivationConflict`, never guess by timestamp); only `next_boundary` (spelled `next_payroll` in the lineage vocabulary) transitions claim authority, so pending `manual` / `immediate` / `next_renewal` transitions are left untouched; and **cross-scope corruption fails closed** — a target/source policy version not belonging to the transition's class+domain raises `BoundaryActivationError` rather than activating. Replay-safe: an already-applied transition leaves nothing pending, so a re-invocation is a lawful no-op with unchanged state. Reuses the existing `economy_rebalance` lineage constants and pending-transition query rather than reinventing them. Tests: `tests/test_class_boundary_activation.py` (applies successfully; no-pending no-op; already-applied idempotent; multiple authoritative pending fail closed; `manual`/`immediate`/`next_renewal` untouched; target scope mismatch fails closed; and rollback leaves the existing active version unchanged — proving no internal commit).
- **Class-wide payroll-cycle settlement (DOM-PROD-001 §XV, slice §8.3b, 2026-08-31)** — Second 8.3 substrate slice: the PROD capability that, given a `class_id`, a `payroll_cycle_id`, and a lawful resolved cycle boundary, settles the entire eligible class under the currently governing payroll configuration and stamps the same `payroll_cycle_id` on every payroll event. New `payroll_event.payroll_cycle_id` column (migration `d5f6a7b8c9e0`, nullable/additive, up/down/re-up verified, single head) threaded through the existing per-seat `record_payroll_event` primitive as an optional argument (existing callers unaffected). New service `settle_class_payroll_cycle` (`app/services/payroll/settlement.py`): enumerates eligible seats by current PROD doctrine (student seats with attendance activity — empty desks are excluded by construction), derives each seat's pay window via the per-seat primitive, reuses the caller's active correlation so all seats settle under one transaction (the primitive re-enters FEAT-PROD-003 as a no-op rather than committing per seat), and **NEVER commits**. It emits only `payroll` events — never `manual_credit` or `reversal` — so teacher credits and reversals never become cycle-boundary events; and it is ignorant of ITR, CLASS activation, and the completion anchor. Re-invoking with the same `payroll_cycle_id` inside the same transaction is idempotent (already-settled seats are skipped via an existence check — no duplicate rows). No active payroll policy fails closed (`ClassSettlementError`). Registered nothing new beyond FEAT-PROD-004 (already present). Tests: `tests/test_payroll_class_settlement.py` (all eligible seats share the cycle id; no-attendance seat is ineligible; a monkeypatched one-seat failure rolls the whole transaction back — even the first flushed event is gone; same-transaction retry makes no duplicates; a pre-existing manual credit is never stamped and settlement produces only `payroll` events; no-policy fails closed).
- **Payroll-cycle completion replay-identity substrate (DOM-PROD-001 §XV, slice §8.3-substrate, 2026-08-31)** — Lands the persistent anchor that makes the payroll cycle boundary replay-safe, *before* any orchestrator is wired (FEAT-PROD-004 orchestration is a later slice). Inspection established that no existing machinery could answer the load-bearing question — *"have I already completed this class-level payroll run, and which `payroll_cycle_id` did it produce?"* — because `FEATContext.idempotency_key` is never persisted and ledger/`PayrollEvent` idempotency only dedups individual rows. New table `payroll_cycle_completion` (migration `c4e5f6a7b8d9`, idempotent helpers + upgrade/downgrade/re-upgrade verified, single head) with one row per `(class_id, idempotency_key)` recording the run's allocated `payroll_cycle_id`; it is meant to be written in the *same atomic commit* as PROD settlement + ITR materialization + CLASS activation, so the anchor exists iff the whole lifecycle committed. New PROD read/write API `app/services/payroll/cycle_completion.py`: `resolve_completed_run(class_id, idempotency_key)` (pure read — the top-level replay guard, consulted before any domain work), `allocate_payroll_cycle_id()` (fresh id, exactly once per new run — never on replay), and `record_run_completion(...)` (final lifecycle step; idempotent on same content, fail-closed `PayrollCycleCompletionConflict` on a different `payroll_cycle_id` for the same key — the anchor is immutable, no update path). Registered `FEAT-PROD-004` (Complete Payroll Cycle, HIGH) in the FEAT registry. This directly closes the replay seam identified in 8.2c: a replay resolves the completed run first and reuses the original `payroll_cycle_id`, so the immutable ITR writer is never re-invoked with an advanced reference configuration. Tests: `tests/test_payroll_cycle_completion.py` (unknown→None, resolvable-after-record, distinct id allocation, the resolve→record→resolve handshake returning the original id, idempotent replay, fail-closed conflict with no update, class scoping under a shared key, and the DB uniqueness guard).
- **Interpretation cycle-record materialization writer — DOM-ITR can create history (DOM-ITR-001 §IX/§VII, slice §8.2c, 2026-08-31)** — The first slice in which DOM-ITR lawfully writes a durable record. New command `materialize_interpretation_cycle` (`app/services/interpretation/materialization.py`) turns a complete, lawful `observations_json` payload into **exactly one immutable** `interpretation_cycle_record` per `(class_id, payroll_cycle_id)`. Four responsibilities, and only these: (1) **re-validate, never trust** — it re-runs `validate_for_materialization` inside the writer and fails closed on an incomplete payload regardless of the payload's own `coverage.complete` claim (a test drops Q9-C1, sets `complete=True`, and is still rejected); (2) **freeze `reference_configuration`** at the cycle boundary via a new capture (`reference_configuration.py`) that projects authoritative CLASS/economic reads (CWI, expected weekly hours, hourly pay rate, active payroll policy lineage) into a versioned, informational, FK-free snapshot with its own `schema_version` (§VII); (3) **write one record**, scoped by `(class_id, payroll_cycle_id)`; (4) **idempotent replay / fail-closed conflict** — re-presenting the same cycle with the same canonical payload *and* reference configuration is idempotent success (no second write), while the same cycle with *different* content raises `CycleMaterializationConflict` and leaves the immutable record untouched — there is no update path. The writer is deliberately **dumb about candidate meaning** (it knows only the serialization contract), performs **no Analytics call** (asserted by an AST import check), and `add`/`flush`es within the caller's FEAT transaction without committing, so any failure rolls back with it. **FEAT-PROD-004 orchestration is intentionally NOT wired here** — the ITR materialization command is proven independently first; slice 8.3 will orchestrate PROD settlement → ITR materialization → CLASS policy activation in one transaction. Tests: `tests/test_interpretation_materialization.py` (complete-inserts-one, incomplete-rejected-despite-claim, not_applicable-accepted, idempotent same-content replay, fail-closed different-content conflict with no update, `reference_configuration` persisted exactly as the frozen projection, class/cycle scoping, and the no-Analytics guard).
- **Interpretation Q9-C1 resilience set — compute core is contract-complete (SPEC-ITR-001 §13, slice §8.2b-5, 2026-08-31)** — Final compute slice: implements Q9-C1, the resilience observation set, bringing the core to **17/17** so that over a lawful cycle window the payload's serializer-derived `coverage.complete` is `True` and `validate_for_materialization` **accepts** it. Q9-C1 is a **composition of already-certified observations**, not a new "resilience score": it is the sole `signal_set` candidate, whose five independent §13.3 groups are distinct member signals never collapsed into a scalar (§13.2). The governing discipline is **reuse, not recomputation** — each signal nests the *same canonical primitive* its owning candidate already certified, so the domain keeps exactly one definition of each fact: `labor_participation` (Q1a attendance primitive), `obligation_outcomes` (Q3 `interpret_obligations`), `resource_checking`/`resource_savings`/`resource_total` (Q6 resource surface), `teacher_support` (Q3 waiver counts + Q5 inbound-ledger primitive). Tests assert this literally — Q9's `resource_checking` value is byte-identical to Q6-C1's, and its `obligation_outcomes` tally equals Q3-C1's summed outcomes. **Persistence is presence, never a trend** (§13.3.e): with no prior `interpretation_cycle_record` source yet (DOM-ITR-001 §XIII.a), the `persistence` signal is `not_applicable` (structured reason) — no slope, direction, or magnitude comparison. Savings-dependent resource signals are per-signal `not_applicable` when savings is disabled. **Dignity (INV-ITR-009):** Q9 uses per-seat observations internally but the serialized output is class-level distributional evidence only — a test asserts no seat identifier appears in the value. The §13.3.a duration sub-observation (days with checking ≤ 0) has no certified per-day historical primitive and is a documented deferred sub-signal rather than a new recompute. New builders `signal_set_value`/`computed_signal`/`not_applicable_signal`; new `app/services/interpretation/resilience_observation.py`; composed into `compute.py`. **The slice stops at compute:** it does not persist anything — writing an immutable `interpretation_cycle_record` (reference_configuration capture, idempotency, fail-closed persistence) remains the separate 8.2c boundary. Tests: `tests/test_interpretation_compute_q9.py` (signal_set structure + sort, dignity, persistence-as-presence, per-signal savings N/A, the two reuse-equality proofs, and the 17/17 `complete=True` + materializable gate); the three prior per-slice coverage tests are flipped from "still fails for incomplete coverage" to "the complete payload is materializable."
- **Interpretation Q4 + Q6 compute over a historical resource surface (SPEC-ITR-001 §9 & §11, slice §8.2b-4, 2026-08-31)** — Sixth build slice, implementing savings behavior (Q4) and resource distribution (Q6) — leaving **only Q9-C1** unimplemented (16/17). Both draw on one shared, historically-correct resource surface but keep their semantics distinct. **The key architectural guard is end-of-cycle correctness:** new Ledger read `get_posted_balances_as_of(class_id, as_of, account_type)` sums settled (`POSTED`), non-void amounts with `timestamp < as_of` — a strict point-in-time read, never the current cached balance — so a transaction dated after the cycle boundary can never leak into an earlier cycle's materialized interpretation (INV-ITR-003). New shared helper `app/services/interpretation/resource_reads.py` (enrolled population, savings enablement as of the boundary, per-seat balances/total-resources in cents) is consumed by both candidates. **Q4** (`savings_behavior.py`): `Q4-C1` savings-holding fraction (*stock* — seats with savings > 0 at window end), `Q4-C2` savings-contribution fraction and `Q4-C3` contribution volume (*flow* — student-originated savings deposits in the window, new Ledger read `get_student_savings_contribution_rows` applying the §6.3 classifier to the savings-credit leg). Stock and flow are never blurred: a seat can hold savings without contributing this cycle, and a system credit creates a holder who never contributed. **Q6** (`resource_distribution.py`): `Q6-C1` checking, `Q6-C2` savings, `Q6-C3` total-resource balance distributions, each the pinned `distribution` value-kind (core percentiles + `iqr` + `n_at_or_below_zero`, §15.6.1) computed over the full enrolled roster (zero-balance seats included) via a new `balance_distribution_value` builder that scales integer-cents percentiles to dollars. **Exact `not_applicable` semantics (§9.6, §11.5):** savings enablement is a CLASS fact (the `banking` feature) evaluated at the cycle boundary; when disabled, all Q4 candidates and Q6-C2 are `not_applicable` with a structured reason and **no value** — never zero (new `not_applicable_entry` builder) — while Q6-C1 stays computed and Q6-C3 falls back to a checking-only distribution carrying the required `{basis_note: {code: checking_only_savings_disabled, …}}` qualifier. Composed into `compute.py`; the partial payload now presents 16 candidates and still fails materialization **solely** for the one missing candidate (Q9-C1). Tests: `tests/test_interpretation_compute_q4_q6.py` (stock-vs-flow divergence, fixed distribution vocabulary with exact percentiles, savings-disabled `not_applicable` + Q6-C3 checking-only basis note, and a historical-balance guard proving a post-window transaction is excluded); coverage expectations in the q1a_q1b/q2_q5/q3 files moved to 1 missing.
- **Interpretation Q3 per-obligation-type correction + contract amendment (SPEC-ITR-001 §8.4/§8.6 & §15.6, slice §8.2b-3a, 2026-08-31)** — Corrects slice 8.2b-3 to match the normative per-obligation-type subject that §8.4 declares for **all three** Q3 candidates and the §8.6 requirement that NSF-fee obligations be identified distinctly in every Q3 output (not only Q3-C3). Rather than pooling Q3-C1/C2 across types (the prior shape), their value payloads are now keyed by obligation type, without multiplying the 17-candidate manifest. This required a **serialization-contract amendment** (§15.6) — done now, before any `interpretation_cycle_record` is written, so no immutable history encodes the mismatch: two value kinds are added to the closed v1 vocabulary — `category_fractions_by_type` (`{obligation_types: {<type>: category_fractions}}`, used by Q3-C1) and `coverage_by_type` (`{obligation_types: {<type>: {assessed_cents, student_paid_cents, waived_cents, unmet_cents}}}`, used by Q3-C2). The per-type `obligation_types` map is keyed by type and order-independent (jsonb-safe, §15.9); an empty map is the lawful zero-observation state; each nested `category_fractions` still sorts its categories per §15.9. Q3-C1/C2 subjects are restored to `"class_id, per obligation type"`; Q3-C3 is unchanged (per-`(type, kind)` counts). The two watch-point behaviors are preserved verbatim — Q3-C2's `student_paid_cents` still counts only student-originated payment rows (§6.3/§8.5, no funds-lineage inference), and NSF remains ordinary (an `"NSF_FEE"` map key, never special compute). SPEC-ITR-001 §15.6 amended to document both kinds; contract validator, value builders (`category_fractions_by_type_value`, `coverage_by_type_value`), and Q3 compute updated; dead `COVERAGE_*` category constants removed. Tests: `tests/test_interpretation_compute_q3.py` C1/C2 rewritten to assert the per-type shape (RENT four-outcome vector + NSF distinct; per-type coverage partitioning assessed); `tests/test_interpretation_observation_contract.py` gains five validator tests for the new kinds and updates the canonical full-payload fixture to use them.
- **Interpretation Q3 obligation-outcome compute (SPEC-ITR-001 §8, slice §8.2b-3, 2026-08-31)** — Fifth build slice of the payroll-cycle-boundary lifecycle, adding the three Q3 candidates: `Q3-C1` count-based satisfaction across the four disjoint outcome categories (`category_fractions`), `Q3-C2` amount-based coverage keeping student-paid vs waived vs unmet as separate numerators against the assessed denominator (`category_fractions`, integer cents), and `Q3-C3` raw event counts per `(obligation_type, event kind)` plus per-type unsatisfied (`counts`). Built on **one canonical obligation-read primitive** (`app/services/interpretation/obligation_outcome.py::interpret_obligations`) that returns the final interpreted state per assessment/correlation, so partial payments, mixed payment+waiver, unsatisfied-at-window-end, and window scoping are decided in exactly one place; the pure `classify_outcome` and `decompose_coverage` helpers are unit-tested DB-free. **NSF is observationally boring (§8.6):** an NSF fee enters Q3 solely because an `NSF_FEE` `ASSESSMENT` event exists in `assessment_events` — `obligation_type` is opaque data, never a special-cased string, never a Ledger `type` fallback (INV-ITR-015), never a synthesized obligation; Q3-C3's per-type counts are where NSF is identified distinctly so a reader can net it out. **Funds attribution never inferred (§8.5):** Q3-C2's paid numerator counts only `PAYMENT` events whose referenced Ledger row is student-originated per the §6.3 classifier (new Ledger read surface `get_student_originated_transaction_ids`), so a teacher-mechanism payment satisfies the obligation by count yet contributes zero student-paid dollars — the code never infers where a seat's balance was funded from. New DOM-OBL read surface `obligations_service.get_obligation_events_for_window` (assessed amounts resolved from upstream policy; PAYMENT magnitudes from the referenced `Transaction`) and value builder `counts_value`. Scope discipline: 10 of 17 required candidates now implemented; the remaining 7 are **not** stubbed and the materialization gate is **not** weakened — the partial payload's serializer-derived `coverage.complete` stays `False` and `validate_for_materialization` still rejects it **solely** for incomplete coverage (7 missing). Tests: `tests/test_interpretation_compute_q3.py` (DB-free outcome/coverage logic; a DB-backed mixed RENT+NSF_FEE window proving the four outcomes, the paid/waived/unmet partition, per-type NSF-distinct counts, and the teacher-funded-payment attribution boundary; lawful empty-window zero baseline; still-failing coverage gate).
- **Interpretation Q2/Q5 compute + shared income-origin classifier (SPEC-ITR-001 §7 & §10, slice §8.2b-2, 2026-08-31)** — Fourth build slice of the payroll-cycle-boundary lifecycle, extending the compute layer to four more required candidates: `Q2-C1` (student-initiated transaction *frequency* as a `rate` over active-seat-days), `Q2-C2` (student-initiated *monetary volume* as an integer-minor-unit `amount`), `Q5-C1` (income *composition* as a six-category `category_fractions` share of inbound volume), and `Q5-C2` (labor *share* as a `ratio` of labor-derived to total inbound volume). Built, per directive, on a **shared provenance primitive first**: new `app/services/interpretation/income_origin.py` classifies each inbound Ledger inflow into exactly one of the six §10.2 origin categories via a **deterministic precedence order** — reversal (structural, `original_transaction_id`, INV-LED-003) → labor → teacher/admin → interest → system-non-labor → other — so the same inflow can never land in two categories and "other/unclassified" is only reached after every canonical check fails (never a garbage chute). **Source-domain precedence (INV-ITR-016):** labor is corroborated against the authoritative `PayrollEvent` surface by shared `correlation_id`, not by trusting a Ledger row's payroll-ish `feat_code` — new PROD-owned read surface `app/services/payroll/read_service.py` (`get_payroll_correlation_sets`) projects the labor vs `manual_credit` correlation-id sets. Interest has no canonical FEAT code today, so `INTEREST_ACCRUAL_FEAT_CODES` is deliberately empty (dormant per §10.4): interest inflows fall to category 6/4 — the honest documented outcome, not a defect. New Ledger read surfaces `get_student_originated_rows` (Q2 count + volume) and `get_inbound_ledger_rows` (Q5 provenance projection), both consuming the §6.3 classifier and integer `amount_cents`; `Transaction.type` never consulted (INV-ITR-015). New value builders `rate_value`, `amount_value`, `ratio_value`, `category_fractions_value` (canonical fixed-scale decimals; `category_fractions` sorted by category id, §15.9). New compute modules `economic_activity.py` (Q2) and `income_composition.py` (Q5), composed into `compute.py`. Scope discipline unchanged: only 7 of 17 required candidates are now implemented; the remaining 10 are **not** stubbed and the materialization gate is **not** weakened — the partial payload's serializer-derived `coverage.complete` stays `False` and `validate_for_materialization` still rejects it **solely** for incomplete coverage (10 missing). Tests: `tests/test_interpretation_compute_q2_q5.py` (DB-free classifier-precedence coverage including reversal-wins-over-labor, corroboration-not-feat, and no-double-count; DB-backed Q2 rate/volume and Q5 six-category composition + labor share; still-failing coverage gate).
- **Interpretation Q1a/Q1b compliant compute vertical (SPEC-ITR-001 §5–§6, slice §8.2b-1, 2026-08-31)** — Third build slice of the payroll-cycle-boundary lifecycle: the first real candidate computation, a full source-domain → contract-valid observation-entry vertical for the three participation/economic-interaction candidates (`Q1a-C1` labor-participation fraction, `Q1a-C2` participation-count distribution, `Q1b-C1` student-initiated economic-interaction fraction). Compute modules consume **authoritative source-domain read surfaces only**, never arbitrary ORM (INV-ARC-009, INV-ITR-016): added read-only query helpers `identity_service.get_enrolled_student_seat_ids` (denominator population), `attendance_service.get_attendance_session_counts_by_seat` (DOM-PROD-001), `entitlement_read_service.get_seat_ids_with_purchase_grants` (DOM-STORE-001), `obligations_service.get_seat_ids_with_self_payments` (DOM-OBL-001), and `ledger_service.get_seat_ids_with_student_originated_activity`. The §6.3 provenance classifier lives in the Ledger domain (which owns the provenance of its own rows): `SYSTEM_ORIGINATED_FEAT_CODES` excludes system-FEAT rows (payroll/interest/NSF/scheduled-obligation/admin-adjustment) so a `mechanism=SELF` payroll accrual does **not** count as student agency, while a STORE purchase grant does via the §6.4 source-domain union — with `Transaction.type` never consulted (INV-ITR-015). New modules: `app/services/interpretation/observation_builders.py` (pure deterministic value/entry builders — canonical fixed-scale decimal strings, pinned `(n-1)` linear-interpolation percentiles), `participation.py` (Q1a), `economic_interaction.py` (Q1b), and `compute.py` (**composition only**). Scope discipline: only 3 of the 17 required candidates are implemented; the remaining 14 are deliberately **not** stubbed and the 17-candidate materialization gate is **not** weakened — so `compute_partial_payload` returns a *partial* payload whose serializer-derived `coverage.complete` is `False` and `validate_for_materialization` rejects it **solely** for incomplete candidate coverage (14 missing). That rejection is the intended end-state of this slice, not a defect. Tests: `tests/test_interpretation_compute_q1a_q1b.py` (4 tests proving individual entry lawfulness, source-domain-faithful values, classifier exclusion + source union, and incomplete-coverage-only materialization failure).

- **Interpretation `observations_json` serialization contract (SPEC-ITR-001 v1.3 §15, 2026-08-30)** — Second build slice (§8.2a) of the payroll-cycle-boundary lifecycle: the canonical serialized shape of the `observations_json` payload that a future writer will persist into `interpretation_cycle_record`. Authored SPEC-ITR-001 §15 (v1.2→v1.3): the 17-candidate `required-set-v1` manifest, a closed two-state applicability model (`computed | not_applicable` — no "fill in later" third state under immutability), the envelope/entry structure carrying the three INV-ITR-012 output properties per observation, a closed v1 `value.kind` vocabulary with fraction/count provenance nested inside each value shape, a structured `qualifiers` basis-note field (records Q6-C3's checking-only basis when savings is disabled per §11.5), pinned `distribution` statistics (core `count/p10/p25/p50/p75/p90/iqr`, balance extension `n_at_or_below_zero`, optional `mean`), and determinism rules (observations sorted by `candidate_id`, canonical decimal strings, **no** reliance on JSONB object-key ordering). Normatively tightened Q1a-C2 and Q6-C1 to the pinned distribution vocabulary (withdrawing the prior "or equivalent" latitude) so immutable records from different cycles speak one statistical language. The completeness gate (§15.8) is **serializer-derived**: `coverage.complete` is recomputed from `observations[]` against the manifest and never trusted from the payload. Added a pure, DB-free validator `app/services/interpretation/observation_contract.py` (`validate_payload_structure`, `derive_coverage_complete`, and the fail-closed `validate_for_materialization` the 8.2c writer will call) plus 18 contract tests in `tests/test_interpretation_observation_contract.py`. Scope discipline: contract + validator only — **no** candidate computation (§8.2b) and **no** write path (§8.2c) yet, so the materialization side effect of FEAT-PROD-004 remains unreachable until the full required payload is implemented.

- **Interpretation cycle-record schema (DOM-ITR-001 §IX, 2026-08-30)** — Created the durable, immutable `interpretation_cycle_record` table via idempotent migration `b3d7f1a9c2e4` (head `68e4cabff66e` → `b3d7f1a9c2e4`; single head preserved). One row per completed economic cycle keyed by `(class_id, payroll_cycle_id)` (unique constraint), with `class_id` a real shared-anchor FK to `classes.class_id` (`ON DELETE CASCADE`) and `payroll_cycle_id` an informational economic-cycle identity (not an FK, per INV-ARC-021 §V.7). Persists `cycle_started_at` / `cycle_completed_at` / `computed_at` (TIMESTAMPTZ) plus two JSONB projections: `reference_configuration` (versioned, immutable snapshot of the economic config consumed) and `observations_json` (materialized descriptive observations + interpretive signals). Both JSONB columns use `none_as_null=True` so a missing projection is rejected as SQL NULL rather than silently stored as JSON `null`. First build slice (§8.1) of the payroll-cycle-boundary lifecycle; the write path (FEAT-PROD-004 orchestration / FEAT-ITR-001 materialization) is a later slice and does not yet exist. Model: `app/models.py::InterpretationCycleRecord`; migration lints clean and passes upgrade/downgrade/re-upgrade; 3 schema certification tests in `tests/test_interpretation_cycle_record_schema.py`.

- **PRODUCTIVITY claims: evidentiary submission form + advisory weekly guidance (FEAT-STOR-003, 2026-08-28)** — Reworked the PRODUCTIVITY insurance-claim lifecycle. Each claimed date now requires a student-authored `student_explanation` (new `NOT NULL` column on `insurance_claim_productivity_dates`, added via migration `d0bb45617620`; a zero-row inventory confirmed no backfill and no fabricated evidence). Claim submission carries an optional claim-wide `additional_information` string, persisted in `InsuranceClaim.claim_basis` (JSON) with no parent column and surfaced to the teacher at review. Removed the hard weekly-hours submission gate (`PRODUCTIVITY_WEEKLY_HOURS_EXCEEDED`): `expected_weekly_hours` is now economic normalization plus **advisory** guidance only. The FEAT derives, per Monday-anchored week, the aggregate `actual_worked_week + claimed_week` vs `expected_weekly_hours` and surfaces non-blocking warnings (in `eligibility_flags`, never persisted as eligibility truth) to the student at submission and the teacher at review. The daily-hours limit remains a hard boundary; the only monetary ceiling stays `maximum_policy_payout = period_premium × payout_multiple`, and `reimbursement_percentage` stays a real per-date multiplier. Files: `app/models.py`, `app/services/insurance_claim_service.py`, `app/feats/insurance_claim_feat.py`, `migrations/versions/d0bb45617620_add_student_explanation_to_productivity_dates.py`, `tests/test_insurance_claim_feat.py` (38 passing). Spec: `docs/FEATURE-EXECUTION/FEAT-STOR-003_INSURANCE_CLAIM_LIFECYCLE.md` §V.B.

- **Class Configuration Phase 5: View Models (2026-08-13)** — Implemented Phase 5 read models for Class Configuration domain (DOM-CLASS-001). Created 4 frozen dataclasses: `ClassSummaryView` (lightweight class identity for lists/selectors), `ClassConfigurationView` (full class config for settings pages), `FeatureConfigurationView`/`FeatureStateView` (feature enablement state). Wired `EconomicView` builder with real CWI calculations, payroll rate validation, and policy-mode-aware health scoring (replacing stub). All builders consume `class_configuration_query_service` — no direct ORM access. 16 tests passing (happy path, missing data, multi-tenancy isolation, immutability). Files: `app/services/class_configuration_view_models.py`, `app/services/class_configuration_economic_service.py`, `tests/test_class_configuration_view_models.py`.

- **Phase 2-3 Part 1: Analytics Domain View Models (2026-08-07)** — Completed Phase 2-3 Part 1 of SPEC-UI-001 template remediation for Analytics domain. Implemented domain-specific view model builders in `app/services/analytics/builders.py`: `MetricSnapshotView`, `AlertCardView`, `RecentEventView`, `AnalyticsDashboardView` (4 frozen dataclasses). Refactored route `app/routes/analytics.py::dashboard()` to build and pass single `AnalyticsDashboardView` to template instead of raw ORM objects. Eliminated all Jinja2 formatting expressions: Pattern 1 (numeric formatting `"%.1f"|format()`, `"%.2f"|format()`) → pre-formatted `display_current_value`, `display_cwi_value`; Pattern 2 (date formatting `|format_datetime()`) → pre-computed `display_window_start`, `display_window_end`, `display_timestamp`; Pattern 4 (business logic: trend classification, threshold-based status) → pre-computed `trend_direction`, `status_color`, `status_label` in builder. Simplified template `templates/admin_analytics_dashboard.html` from 574 to ~350 lines: removed 67-78 alert lookup namespace construction, 94-169/186-199/256-274/331-363 threshold/trend logic, 399-414 event formatting. Added 23 comprehensive test cases in `tests/test_analytics_builders.py` covering formatting, trend classification, immutability, multi-tenancy scoping, zero ORM leakage. Final status: 1/1 template complete, 0 Jinja2 formatting expressions, 23/23 tests passing.

- **Phase 1 Jinja2 Remediation Complete (2026-08-07)** — Completed Phase 1 of SPEC-UI-001 template remediation for Store, Obligations, and Payroll domains across all 3 admin/student-facing templates. Implemented domain-specific view model builders: `StoreItemCardView`, `EntitlementCardView`, `CollectiveProgressView` (store); enhanced `StudentObligationView`, `ClassObligationSummary` (obligations); `StudentPayrollStatusView`, `PayrollConfigurationView` (payroll). Updated all routes to build and pass view models instead of raw ORM objects. Moved ALL Jinja2 date/currency formatting to route display fields: `student_shop.html` (37% reduction), `admin_rent_settings.html` (rent_amount, late_penalty, dates), `admin_payroll.html` (payroll timestamps, settings dates, pay dates). Fixed violations across all templates: Pattern 1 (numeric formatting) → pre-formatted display strings; Pattern 2 (ORM `.strftime()`) → pre-computed dates; Pattern 4 (business logic) → view model computation; Pattern 6 (ORM traversal) → flattened properties. Final status: 3/3 templates complete, 0 Jinja2 formatting expressions. Commits: 9103ded8, ffd76ad2, 942a7342, 8b7d740f.

- **Template Jinja2 Element Inventory Audit** — Comprehensive audit of all 96 application templates analyzing Jinja2 variable and tag patterns, domain authority mapping, view model wiring status, and compliance against INV-ARC-022 and SPEC-UI-001. Includes per-template breakdown, violation categorization (CRITICAL/HIGH/MEDIUM), affected templates, and 6-week remediation roadmap. Document: `docs/TRACKING/TEMPLATE_JINJA_INVENTORY.md` (#1314).
- **Canonical Page Rendering Specification (SPEC-UI-001)** — Normative specification defining implementation requirements for authenticated page routes, page view models, builder responsibilities, template contracts, and route orchestration. `docs/SPEC/SPEC-UI-001_PAGE_RENDERING_SPECIFICATION.md` (#1314).
- **Request Context and Page Rendering Pipeline Invariant (INV-ARC-022)** — Foundational architectural invariant establishing the 8-layer rendering pipeline (Request → Canonical Context → Temporal Context → Identity Display Context → Domain Reads → Page View Model → Template) and strict separation of authority, interpretation, and presentation responsibilities. `docs/INVARIANT/ARCHITECTURE/INV-ARC-022_REQUEST_CONTEXT_AND_PAGE_RENDERING.md` (#1314).

### Fixed

- **Accessible names added to controls in `admin_recover.html` and `hall_pass_setup.html`** — The accessibility smoke suite flagged interactive elements with no accessible name that screen readers could not announce: the `.btn-close` modal dismiss button in `hall_pass_setup.html`, the `#masterToggle` hall-pass switch there, and the unlabeled `join_code[]`/`student_username[]` recovery inputs (static and dynamically-added rows) in `admin_recover.html`. Added `aria-label` attributes so each control is announced. Pre-existing on the HEAD baseline; not caused by a recent change.

- **Payroll hourly rates retain their entered value** — Increased `payroll_settings.pay_rate` from `NUMERIC(12,2)` to `NUMERIC(18,8)` via migration `6f79a33fe78a`, preserving the precision required when hourly rates are converted to per-minute storage. Entering `$80.00/hour` now saves and displays as `$80.00` instead of `$79.80`, and CWI calculations no longer round the stored per-minute rate back to cents.

- **Admin runtime log and dashboard correctness** — Replaced Unix-only temporal display directives so dashboard dates render on Windows, joined pending redemptions to same-class entitlement events to eliminate a cartesian product and inflated counts, corrected TLCP classification for the public tips API, and keyed the successful admin-login FEAT mutation.

- **Landing-page fonts comply with CSP** — Replaced the remaining Google Fonts and duplicate Material Symbols stylesheet requests in `github-pages/landing.html` with the vendored same-origin font stylesheet, preventing `style-src-elem` violations while preserving the restrictive CSP.

- **`admin_payroll.html` residual `"%.2f"|format()` currency expressions eliminated** — The Phase 1 payroll remediation missed 10 raw Jinja2 formatting expressions covering next-payroll estimates, total/average payout stats, recent-payroll and payroll-history amounts, and simple/advanced pay-rate display and input pre-population. Added `build_payroll_settings_display()` in `app/services/payroll/builders.py` and pre-formatted `display_amount`/`display_estimate` fields on the payroll row/summary dicts built in `app/routes/admin.py`, so the template now consumes only pre-formatted display strings, matching the `StudentPayrollStatusView`/`PayrollConfigurationView` pattern used elsewhere on the page.

### Changed

- **Web fonts self-hosted; Google Fonts CDN dependency removed (2026-08-29)** — Inter, Atkinson Hyperlegible Next, IBM Plex Mono, and Material Symbols Outlined are now vendored locally under `static/fonts/` (15 woff2, ~4.1 MB) and served through a single new stylesheet `static/css/fonts.css`, eliminating all runtime requests to `fonts.googleapis.com` / `fonts.gstatic.com`. Inter and Atkinson are consumed as variable fonts via the css2 `wght@min..max` range syntax (one woff2 per subset covering the full weight range); IBM Plex Mono ships discrete static-instance weights. Only the `latin` and `latin-ext` subsets are vendored. The previously requested-but-unused Google Sans and IBM Plex Sans links were dropped. 32 templates had their Google font `<link>` tags (stylesheet/preconnect/preload) replaced with the local stylesheet link. CSP tightened in `app/__init__.py`: `https://fonts.googleapis.com` removed from `style-src` and `https://fonts.gstatic.com` removed from `font-src` (jsdelivr/cdnjs retained for Font Awesome). New tooling: `scripts/vendor_fonts.py` (downloads woff2 + regenerates fonts.css, deterministic and re-runnable) and `scripts/localize_font_links.py` (one-off template delocalization, kept for auditability). Accessibility validation per SOP-TEST-002 surfaced 2 pre-existing `btn-close` findings (`admin_recover.html`, `hall_pass_setup.html`) that are identical on the HEAD baseline and are NOT regressions of this change (the font diff touches only `<link>` lines).

- **Identity Domain Phase 10 Certification (2026-08-06)** — All 10 phases of SOP-DEV-002a completed and audited. Identity domain is production-ready. Certification document: `docs/TRACKING/SOP-DEV-002a_IDENTITY_20260806_AUDIT.md` (#1313).
- **Canonical Temporal Resolver Refactoring** — `app/utils/canonical_temporal_resolver.py` made fully self-contained with no external configuration dependencies. Payroll, attendance, scheduled-task, and route surfaces now resolve time via the canonical resolver. Improves testability and removes coupling to global application state (#1312).
- **Entitlements Contract Violation Fix (Phase 8 Test Verification)** — Fixed rent hall pass contract violations where `RentPayment` terminal state was not properly synchronized with entitlements lifecycle. Added `one_terminal_per_lineage` unique constraint on `RentPayment(policy_uuid, lineage_key)` to enforce one paid payment per student per rent period. Tests in `test_entitlement_service.py` verify contract compliance (#1311).
- **Obligations Domain Phase 10 Certification (2026-08-04)** — All 10 phases of SOP-DEV-002a completed and audited. Obligations domain is production-ready. Full view model wiring and surface integration complete. `StudentObligationView` and `ClassObligationSummary` immutable models standardize rent/insurance obligation presentation. Admin and student templates exclusively consume view.* fields. Certification document: `docs/TRACKING/OBLIGATION_DOMAIN_QA_AUDIT_AUG_2026.md` (#1305).
- **DOM-PROD-001 (Productivity and Payroll) Schema Alignment and Audit Completed** — The v2 canonical schema migration for the PROD domain is fully verified. `AttendanceSession`, `HallPassLog`, and `PayrollEvent` tables are actively enforcing `class_id` scoping. All legacy `student.block` scope derivations have been completely removed from runtime surfaces (API and Templates). The audit confirms 100% PASS for DOM-PROD compliance.
- Full v2 test stabilization checkpoint landed: the FEAT transaction teardown leak was fixed in `app/feats/base.py`, legacy v1-style rent/time/payroll tests were rewritten to current canonical helpers where needed, and the latest full suite now passes as `744 passed, 19 skipped, 1 warning`.
- Shared canonical fixture cleanup moved the collective-goal and economy-policy test slices onto a single explicit class scope per scenario, eliminating teacher-ownership lookup from the test setup path and keeping student/item seeding anchored to `class_id`.
- FEAT-by-default repair work now lands the remaining canonical test slices for API fixes and dashboard rendering: `/api/set-timezone` now returns a valid unauthorized response instead of a bare falsey value, dashboard rendering tests use canonical FEAT-backed setup, and the student dashboard no longer crashes when canonical class metadata omits legacy block state.
- Canonical auth-session tests now seed student identity via unclaimed-seat then claim-binding semantics, and use canonical class scope creation instead of non-authoritative convenience seed helpers in `tests/test_canonical_auth_session.py`.
- **Canonical monetary resolution FEAT landed** — Added `FEAT-LED-000` as the single monetary-resolution boundary, rewired store/rent/insurance/admin monetary flows to build intended ledger plans before posting, and removed the legacy `app/utils/overdraft.py` helper. Targeted FEAT regressions now pass against the canonical path only.
- **Pytest artifacts no longer emit on collect-only discovery runs** — Artifact generation now skips when pytest is invoked with `--collect-only`, preventing VS Code test discovery from recreating files in `pytest_result/` when no tests were actually executed.
- **Pytest failure classification quality improved** — Result artifacts now extract exception classes from pytest traceback `E ...` lines (for example `FEATContextError`) and prefer application frames when computing `first_project_frame`, so grouped-failure sections collapse by root cause instead of splitting by per-test callsite lines.
- **Pytest artifacts redesigned with canonical CSV output** — Standard pytest runs now emit three coordinated artifacts under `pytest_result/`: `YYYYMMDD_pytest_<label>_results.csv` (canonical machine-readable source of truth), `YYYYMMDD_pytest_<label>_summary.md` (human-readable run report derived from CSV), and `YYYYMMDD_pytest_<label>_failures.log` (full tracebacks for failed/error outcomes). CSV rows are captured directly from pytest hooks with one executed test per row, including outcome, duration, exception type/message, first project frame, and markers. Repeated runs on the same date/label no longer overwrite; they append numeric suffixes (`_1`, `_2`, ...).
- **`Seat.join_code` column removed** — Constitutional violation of DOM-IDEN-007 (ClassEconomy is the sole owner of `join_code`). Dropped via migration `1c6893a8b375`. All runtime callsites in `scope_factory.py`, `__init__.py`, `rent_payment_feat.py`, `attendance_helpers.py`, `banking.py`, `admin.py`, `student.py` now resolve `join_code` from `ClassEconomy` by filtering on `class_id`.
- **`ClassMembership`, `StudentBlock`, `StudentTeacher` removed from all test imports** — 51 test files previously imported one or more of these retired models. All imports and add-to-session calls removed or rewritten to canonical v2 equivalents: `Seat` (existence = membership), `ClassEconomy.user_id` (teacher ownership), `SeatAttendanceState` (tap/done state).
- **Test isolation rewired to `Seat.class_id` scoping** — `test_admin_multi_tenancy.py`, `test_unassigned_visibility.py`, `test_admin_membership_gates.py`, `test_teacher_student_flow.py`, `test_analytics.py`, `test_insurance_class_scoping.py`, `test_api_tenancy.py`, `test_attendance_seat_scope.py` rewritten to query isolation via `Seat.class_id → ClassEconomy.user_id` instead of the removed `StudentTeacher` and `ClassMembership` tables.
- **Four `StudentBlock`-dependent API tests removed** — `test_admin_student_block_settings_rejects_out_of_scope_join_code`, `test_admin_student_block_settings_rejects_null_join_code_row`, `test_admin_block_tap_settings_get_ignores_out_of_scope_join_code_row`, `test_admin_block_tap_settings_post_preserves_out_of_scope_join_code_row` deleted — the routes and data model they tested no longer exist in v2.
- **`test_admin_multi_tenancy.py` rewritten to canonical isolation model** — tests verify teacher-scoped student visibility via direct `Seat → ClassEconomy.user_id` join; `_scoped_students()` helper (removed from admin routes) replaced.
- **`test_unassigned_visibility.py` rewritten** — removed dependency on `_scoped_students()`; tests verify isolation via canonical `Seat → ClassEconomy.user_id` join.
- **Admin help-support now keys support scope by `class_id`** — The help-support route now stores and filters support tickets by `class_id` while keeping `join_code` as the public label shown to the user. This removes the internal dependency on `join_code` for support-scope selection and keeps the route aligned with the canonical identity model.
- **Admin help-support wording aligned to owner-user naming** — The help-support route docstring in `app/routes/admin.py` now uses owner-user wording around the canonical join-code lookup path. This is a small cleanup slice; behavior remains unchanged.
- **Admin export and help-support helper locals renamed to owner-user naming** — The export and help-support helpers in `app/routes/admin.py` now use owner-user local names around the canonical join-code lookup path. This keeps the runtime naming aligned with the current identity model without changing behavior.
- **Admin feature-scope helper renamed to owner-user language** — The helper stack that resolves admin feature join codes now uses `owner_user` naming internally instead of a teacher-shaped local name. This is a focused cleanup slice aligned with the canonical identity references; behavior remains unchanged.
- **Admin payroll adjustments now use `user_id` payloads** — The admin payroll and manual payment helpers now pass `user_id` to the adjustment FEAT instead of `teacher_id`, matching the FEAT contract while leaving behavior unchanged.
- **Admin bonus-all helper now uses canonical owner context** — The `give_bonus_all` route helper now pulls its owner boundary from `g.canonical_context.user_id` instead of relying on a stale local name, keeping the payroll/adjustment path aligned with the current admin context contract. This is a focused cleanup slice; behavior remains unchanged.
- **Admin class-delete helper boundary renamed to `owner_user_id`** — The class-delete helper now uses owner-user naming for its boundary and announcement purge, matching the rest of the admin cleanup. This is a focused cleanup slice; behavior remains unchanged.
- **Admin hard-delete account scope renamed to `owner_user_id`** — The admin account-deletion fan-out now names its owner boundary as `owner_user_id` and threads that naming through the class-deletion cascade. This is a focused cleanup slice; behavior remains unchanged.
- **Admin deletion-helper owner boundary renamed to `owner_user_id`** — The admin cleanup helpers now use owner-user naming for the deletion block instead of `teacher_id`, and the associated comments were tightened to match. This is a focused cleanup slice; behavior remains unchanged.
- **Admin issue-resolution wording and seed-script shadow rows removed** — The admin issue workflow now uses owner/admin wording in its local boundary names and messages without changing the FEAT/status contract, and `scripts/seed_canonical_v2.py` now seeds directly from `User`, `Seat`, and `IdentityProfile` instead of writing legacy shadow rows. This is a focused cleanup slice; behavior remains unchanged.
- **System-admin announcement and escalated-issue labels moved further toward owner-admin naming** — The system-admin announcement display and form copy now use owner-admin language, and the escalated-issue docstrings were tightened to match the canonical owner-user framing. This is a small cleanup slice; behavior is unchanged.
- **System-admin delete-admin reason string aligned to owner-user wording** — The delete-admin universe-collapse reason string now says owner-user instead of teacher, matching the canonical ownership language used elsewhere in the cleanup.
- **System-admin bug-reward bookkeeping boundary made explicit** — The system-admin issue-resolution flow now names the issue owner explicitly as `issue_owner_user_id` before issuing the bug-reward transaction. This keeps the reward path aligned with the canonical owner-user naming.
- **System-admin delete-admin boundary aligned to `owner_user`** — The system-admin delete-admin flow now names its resolved canonical account as `owner_user`, matching the owner-user terminology used elsewhere in the cleanup.
- **System-admin TOTP reset endpoint renamed** — The system-admin TOTP reset route helper is now named `reset_admin_totp`, matching the actual actor type that the route handles.
- **System-admin issue-resolution boundary made consistent** — The system-admin issue-resolution flow now uses `sysadmin_user_id` consistently for its record-status bookkeeping. This is a small runtime cleanup that removes the last local variable mismatch in the flow.
- **System-admin overview and issue-resolution boundaries aligned to canonical user naming** — The system-admin teacher-overview aggregation maps now use owner-user naming, and the issue-resolution flow now uses `sysadmin_user_id` internally. This keeps the system-admin surface moving toward the same canonical naming as the rest of the cleanup.
- **System-admin announcement create boundary aligned to `sysadmin_user_id`** — The system-admin announcement create flow now uses canonical user naming internally for the system admin actor while leaving the audience semantics unchanged.
- **Admin public student-detail route aligned to owner-user naming** — The public student-detail admin route now threads `owner_user_id` through its class-scoped reads instead of a teacher-shaped local name. Behavior is unchanged; the route now matches the canonical ownership language used elsewhere in the cleanup.
- **Redemption disposition FEAT actor boundary aligned to `actor_user_id`** — The redemption disposition FEAT now names its actor boundary explicitly as an owner-user identifier while keeping the underlying ledger write shape intact. This keeps the store approval/rejection path internally aligned with the rest of the canonical runtime naming.
- **Admin rent/store helpers aligned to owner-user naming** — The rent-to-store sync helper and the insurance tier namespace helper now use owner-user naming, and the stale internal callsite was rewired. This keeps the remaining admin-side provisioning path consistent with the canonical runtime ownership model.
- **Admin student-seat provisioning helper aligned to owner-user naming** — The admin helper that ensures the shadow student seat now uses owner-user naming, and the remaining internal callsites were rewired to the renamed helper. This keeps the admin class provisioning path consistent with the canonical ownership model.
- **Transfer and admin-adjustment FEAT boundaries aligned to `user_id`** — The account-transfer FEAT and admin-adjustment FEAT now name the owner-user boundary explicitly where they already operate on canonical user ownership. The ledger calls still pass `teacher_id` into legacy-shaped service APIs, but the FEAT layer itself now speaks the same runtime language as the rest of the cleanup.
- **Admin helper boundaries aligned to owner-user naming** — The top-of-file admin class-anchoring helpers now use `user_id` naming for class resolution and feature-settings lookup, matching the canonical owner-user boundary used elsewhere in the runtime.
- **API helper boundaries aligned to owner-user naming** — `app/routes/api.py` now uses owner-user naming for the redemption audit and hall-pass helper boundaries while preserving the existing outward payload shapes. This is a runtime-only cleanup that keeps the canonical class-owner model moving through the remaining API surface.
- **Economy-balance boundary aligned to `user_id`** — The economy balance checker now takes `user_id` instead of `teacher_id`, and the scheduled rent-cycle FEAT now uses owner-user naming at the boundary. This keeps the remaining class-scope helpers aligned with the canonical runtime ownership model.
- **Economy-policy helper boundary renamed** — Class-scope policy helpers now speak `user_id` instead of `teacher_id`, matching the canonical runtime actor boundary that was already active in scope resolution and student rent processing. The app startup check remained clean after the signature rename.
- **Identity cleanup checkpointed** — Removed the remaining bridge-service surface from the active admin/recovery identity paths, shifted the runtime access boundary from `Scope.teacher_id` to `Scope.user_id`, and reconciled the context-resolver tests to the current canonical session contract. The tracker docs were updated with the latest verified slice, and startup stayed clean under focused validation.
- **Wave 8 store domain cutover** — Canonical store tables `store_purchases`, `redemption_events`, and `store_item_visibility` replace `student_items`, `store_item_blocks`, and `redemption_audit_logs` as the store domain authority. DOM-STORE-001 v2.0 aligned with DOM-CORE-002. Migration `0009_store_domain.py` creates the canonical tables. `store_service.py` and `store_purchase_feat.py` rewritten to v2-only execution with no legacy fallback. Schema and behavioral tests in `tests/domain/test_store.py`. (#1244+)

- **Wave 7 closeout completed for the insurance obligations slice** — legacy `StudentInsurance` runtime usage was removed, all insurance runtime paths now use `InsuranceEnrollment`, and the focused insurance/decimal regressions were rewritten to the v2 seat-based architecture. The remaining table-drop cleanup is tracked separately and no longer blocks the Wave 7 exit gate.
- **Wave 7 admin rent read surfaces moved further onto canonical obligations** — the admin rent privilege cache and cycle reversal flow now read paid rent state from `obligations_service.get_paid_rent_assessments_for_cycle(...)` rather than direct `RentPayment` queries. The remaining legacy report/deletion surfaces are now isolated to non-1:1 maintenance paths.
- **Wave 7 student rent read path moved to canonical obligations helpers** — `student.rent` now renders payment status and history from `obligations_service.get_paid_rent_assessments_for_cycle(...)` and `get_rent_payment_history(...)` instead of reading `RentPayment` rows directly. The live rent route now stays on the v2 assessment/lifecycle model end-to-end.
- **Canonical auth hydration now fails closed only after seat-aware recovery** — Student login first validates persisted `last_active_class_id`, then falls back to explicit class selection when one or more valid class/seat options exist. If no valid option exists, the login flow now logs an invariant violation and returns the generic role-appropriate recovery message instead of treating missing persisted selection as a terminal session error.
- **Tuple-only runtime cutover checkpointed** — Admin, recovery, analytics, attendance, deletion, and shared seat-scope helpers now operate on canonical `User`/`Seat`/`class_id` boundaries instead of reconstructing runtime identity from `StudentTeacher` or `Seat.student_id`. The remaining migration work is test-corpus cleanup and `canonicalContextFactory` adoption.
- **Wave 7 / P0 remediation session** — Created `codex/wave7-closure-p0-remediation`, rewrote the v2 authority guardrail tests to assert canonical source-level behavior, and wrapped the touched dead-route mutation entrypoints in FEAT ownership (`admin.process_claim`, `admin.passkey_auth_finish`, `admin.resolve_issue`, `sysadmin.resolve_escalated_issue`). Focused validation: `pytest -q tests/test_v2_authority_guardrails.py -q`. Added regression coverage that pins those route surfaces to FEAT ownership and keeps the read-only admin GET guardrail source-checked.
- **Wave 6 attendance cutover completed** — Legacy `TapEvent` runtime usage has been removed in favor of canonical `AttendanceSession` + `SeatAttendanceState` flows. The Wave 6 migration chain now drops `tap_events`, the downgrade path recreates the retired schema shape for rehearsal, and attendance/admin/student/deletion paths all operate on canonical attendance tables.
- **Wave 6 authoritative docs aligned with runtime truth** — Updated the active migration tracker, attendance domain docs, schema ownership/index pages, recovery doc, README, and developer vocabulary so live documentation reflects that `tap_events` is retired and Wave 6 is complete.
- **Wave 7 rent-waiver actor cutover completed** — `ObligationReversal` now uses seat-scoped actor attribution (`reversed_by_seat_id`) instead of the legacy nullable user FK. Rent-waiver add/remove flows no longer emit legacy `AnalyticsEvent` compatibility rows; the follow-up analytics event will return only after the analytics schema is seat-scoped.
- **README rewritten for v2 architecture** — Corrected platform framing (classroom management tool, not financial literacy), updated key models table to reflect `Seat`/`IdentityProfile`/`ClassEconomy`, removed stale v1 references
- **Wave 11 bulk test refactoring: TeacherBlock→Seat** — ~60 test files migrated from `TeacherBlock` fixtures to canonical `Seat` + `IdentityProfile` + `ClassEconomy` constructs. Deleted `tests/helpers/mock_teacher_block.py` shim. 7 legacy-only test modules marked skipped for decommissioning. TeacherBlock test surface reduced from 71 to 27 files (62% reduction). (#1220)
- **Default branch switched to `codex/v2.0`** — CI workflows (actionlint, check-migrations, policy-guardrails) now trigger on `codex/v2.0` instead of `main`. Deploy to DigitalOcean workflow intentionally remains on `main` only.
- **Documentation reorganized for v2 canonical structure** — v2 restructure docs promoted from `docs/development/v2_restructure_doc/` to top-level canonical directories: `docs/DOMAIN/`, `docs/FEATURE-EXECUTION/`, `docs/INVARIANT/`, `docs/MAP/`, `docs/TESTING/`. Development specs and tracking promoted to `docs/SPECS/` and `docs/TRACKING/`. All internal cross-references updated across 47 files.
- **v1 docs archived** — User guides moved to `docs/archive/v1-user-guides/`, GitHub Pages landing assets to `docs/archive/github-pages/`, superseded development artifacts to `docs/archive/v1-development/`.
- **Root-level cleanup** — Removed 24 scratch/debug/temp files (fix_*.py, debug_*.py, pytest output dumps, ephemeral assessment reports). Moved `student_upload_template.csv` to `app/data/`. Removed duplicate `app/data/random-words.txt`.

### Added
- **REFERENCE vocabulary standards** — `docs/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY.md` (normative developer terms) and `REF-TERM-002_USER_VOCABULARY.md` (normative user-facing terms) establish canonical v2 terminology with explicit deprecated-term mappings
- **Terminology audit** — `docs/TRACKING/TERMINOLOGY_AUDIT_V1.md` inventories 177 terms across the codebase with frequency analysis and v1→v2 migration status
- **Wave 7 canonical insurance-claim lifecycle coverage** —
  `tests/test_insurance_snapshots.py::test_admin_claim_approval_uses_frozen_claim_cap`
  now asserts that the live admin approval path emits canonical
  `assessment_events`, `obligation_lifecycle`, and `obligation_satisfaction`
  rows in addition to the reimbursement ledger entry.
- **`FEAT-STOR-006` (Redemption Disposition) FEAT** — registered in the canonical
  registry and implemented in `app/feats/redemption_disposition_feat.py`.
  Exposes `execute_redemption_approval(...)` and `execute_redemption_rejection(...)`,
  both `@requires_feat_context("FEAT-STOR-006")`-guarded. The FEAT is named for
  the business action so the Wave 8 `StudentItem` → `StorePurchase` +
  `RedemptionEvent` split will change the FEAT's internals without changing
  its contract.
- **Enforcement-active redemption tests** —
  `tests/test_redemption_disposition_feat.py` adds 5 tests under
  `@pytest.mark.enforce_feat`, exercising the redemption routes with the
  global `FEATBypass` opted out. `FEATBypass` is used only inside
  fixture-setup blocks, not around route calls. These tests would have
  caught the dead-route bug surfaced in the audit; they now lock the fix in.
- **`V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md`** —
  `docs/TRACKING/V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md` documents
  the audit findings, methodology note, and 5-phase plan for inverting the
  conftest FEAT-enforcement default so that production-shaped enforcement is
  the default in CI and bypass is explicit per-test. Master tracker updated
  to reference the plan under Wave 11 post-launch hardening.
- **Phase 1 (instrumentation) of the FEATBypass default-flip plan landed.**
  New pytest plugin `tests/_feat_bypass_audit.py` opts in via
  `FEAT_BYPASS_AUDIT=1` and hooks SQLAlchemy `before_flush` to record every
  flush that occurs while `FEATBypass` is the only thing keeping the
  constitution quiet. The dispatch discriminator uses the call stack
  (Flask's `wsgi_app`/`full_dispatch_request`/`dispatch_request`/
  `preprocess_request` frames) rather than `has_request_context()`, because
  pytest-flask leaves a dangling context around fixture code.
  `scripts/regenerate_feat_bypass_report.py` re-emits the markdown from the
  raw JSON without a fresh suite run. Findings written to
  `docs/TRACKING/V2_FEAT_BYPASS_DEPENDENCY_REPORT.md`:
  **4 unique mutating endpoints are dead in production**
  (`admin.process_claim`, `sysadmin.resolve_escalated_issue`,
  `admin.rent_settings`, `admin.passkey_auth_finish`), far below the
  pre-instrumentation ceiling of ~78. **Zero GET-side-effect bypass-hidden
  flushes** (INV-ARC-007 largely respected). 585 of 590 observed tests
  have fixture-only bypass dependency, concentrated on
  `tests/helpers/class_scope.py:create_class_scope` (~587 flushes). The
  raw JSON output is gitignored (it's regenerated by re-running the
  audited suite); the markdown report is the durable artifact.

### Changed
- **TeacherBlock test fallout reduced after the landed table drop** —
  `tests/test_feature_settings.py` and `tests/test_admin_membership_gates.py`
  now assert canonical `Seat` / `ClassEconomy` behavior directly instead of
  querying the removed `TeacherBlock` authority surface. Legacy add-student
  assertions that still depend on pre-v2 shadow-seat semantics are now
  explicitly skipped pending a canonical rewrite, rather than silently
  preserving `TeacherBlock`-era expectations.
- **Wave 8 obligation identity canonicalization** — all obligation domain
  identity references now use canonical v2 identifiers (`user_id`, `seat_id`,
  `enrollment_id`) exclusively. Migration `0008` renames
  `obligation_reversal.reversed_by_teacher_id` → `reversed_by_user_id` (FK →
  `users.id`), `insurance_claims.processed_by_teacher_id` →
  `processed_by_user_id` (FK → `users.id`), `insurance_claims.student_insurance_id`
  → `enrollment_id` (FK repointed from `student_insurance` to
  `insurance_enrollments`), and drops `insurance_claims.student_id`. FEAT layer
  and admin routes updated to pass `user_id` instead of `teacher_id`/`admin_id`.
  All 23 insurance/obligation tests pass with canonical fixtures.
- **Wave 7 insurance-claim resolution now dual-writes canonical obligation
  state** — `app/services/obligations_service.py` now emits
  canonical claim assessments using deterministic idempotency keys
  (`insurance-claim:{claim_id}`), advances `obligation_lifecycle` to `PAID`
  or `REVERSED` on claim resolution, and records `obligation_satisfaction`
  or `obligation_reversal` rows under the clean-cutover model.
- **Wave 7 rent-waiver analytics compatibility write removed** — `admin.add_rent_waiver` and `admin.remove_rent_waiver` no longer emit legacy `AnalyticsEvent` rows for waiver actions. The route now keeps waiver state canonical and leaves analytics reintroduction for a later seat-scoped schema pass.
- **`/api/approve-redemption` and `/api/reject-redemption` now route through
  `FEAT-STOR-006`** — both routes were dead in production runtime prior to
  this change: they performed `db.session.add(RedemptionAuditLog(...))` and
  mutated `StudentItem.status` without a `@feat_shell` decorator, so the
  `before_flush` constitutional enforcement raised `FEATContextError` and
  returned HTTP 500 with zero rows persisting. The breakage was invisible to
  CI because `tests/conftest.py` wraps every test in `FEATBypass`. Both
  routes now wear `@feat_shell("FEAT-STOR-006")`, delegate all mutation to
  the new FEAT module, and narrow their exception handling to
  `RedemptionDispositionError` (mapped to HTTP 409). Infrastructure errors
  propagate to the FEAT shell for rollback rather than being swallowed.
- **Cross-FEAT `Transaction` UPDATE enforcement corrected
  (`app/models.py:_enforce_transaction_integrity`)** — the "Mixed correlation
  in flush" check was firing on UPDATE as well as INSERT, making it
  impossible for any FEAT to mutate a `Transaction` created by a prior FEAT
  (refunds, voids, `reversal_transaction_id` linkage). Real production paths
  were affected. The bug was hidden because every test ran under a single
  `FEATBypass` correlation. The check is now gated on
  `_target_state.transient or pending` so it fires only on INSERT; on UPDATE
  the row's `correlation_id` is preserved as historical lineage and the
  active FEAT's identity is captured via `feat_code` (which is unconditionally
  set on both insert and update).
- **Wave 7 obligations schema contract corrected** — Added forward migration
  `0007` to create and backfill canonical `assessment_events` and
  `obligation_lifecycle`, repoint satisfaction/reversal/entitlement foreign
  keys, and preserve downgrade data in the transitional `0006` table. Runtime
  rent and insurance enrollment writes now emit canonical assessment and
  lifecycle state while legacy tables remain available for the later read
  cutover and parity validation.
- **Closed the next post-Wave 4 authority-reduction slices** — TLCP actor
  correlation now derives student/teacher `actor_public_id` from the active
  seat context instead of reconstructing it from legacy `student_id` or
  `admin_id`. Sysadmin auth probes and passkey-management endpoints now trust
  canonical resolver identity rather than raw `sysadmin_id` session checks.
  Payroll route entry, settings writes, and disabled-scope gating now resolve
  canonical admin identity first and use class-scoped seat data instead of
  `TeacherBlock.teacher_id` as the primary runtime authority.
- **Completed-surface feature gating now prefers canonical `class_id` helpers** —
  `app/utils/economy_policy.py` now exposes explicit
  `resolve_feature_class_for_class()` and
  `get_class_feature_settings_for_class()` helpers for class-authoritative
  feature reads. Active admin, student, API hall-pass, and attendance policy
  callers in already-completed Wave 4 surfaces now resolve feature enablement
  from `class_id` first instead of rebuilding scope from
  `teacher_id + block/join_code`. Focused regressions cover class-scoped helper
  behavior, admin join-code option discovery without `TeacherBlock` authority,
  insurance management feature gating from the active class, fail-closed
  handling for unknown class IDs, and canonical user/seat contexts in feature
  enforcement tests. The hall-pass legacy-scope migration now safely handles a
  missing table and restores its teacher foreign key on downgrade.
- **Wave 4 class-configuration canonicalization completed** — The active class
  configuration tables now align on `class_id` as the runtime and schema
  boundary: `class_features`, `feature_settings`, `hall_pass_settings`,
  `banking_settings`, `payroll_settings`, `payroll_cache`, and `rent_settings`
  no longer carry live `teacher_id` / `join_code` scope columns, and all seven
  now require non-null `class_id` in the database. This closes the legacy
  settings-column retirement lane for Wave 4.
- **PayrollSettings and PayrollCache moved further into canonical Wave 4 scope** —
  `payroll_settings` now treats `class_id + block` as its only runtime authority,
  and `payroll_cache` is now class-owned only. The model, payroll cache writer,
  payroll settings admin writes, and class-deletion cleanup path no longer depend
  on legacy `teacher_id` / `join_code` scope fields. Migration
  `2a4f6c8d0e21` drops those legacy columns from `payroll_settings` and
  `payroll_cache`, including dependent payroll-settings RLS policy cleanup.
  Focused payroll helper, cache, shared-student, and admin route tests were
  updated to assert class-scoped behavior directly.
- **BankingSettings moved further into canonical Wave 4 scope** — `banking_settings`
  now treats `class_id + block` as the runtime authority contract. The model and
  admin banking settings write path no longer create or depend on legacy
  `teacher_id` / `join_code` scope fields, and migration `1f6c2b8d4e90` drops
  those columns from the schema. Focused banking helper and admin route tests were
  updated to assert class-scoped behavior directly.
- **Canonical auth and roster-provisioning docs aligned** — Updated active v2
  identity, recovery, lifecycle, schema, session, README, and development docs so
  `User` owns authentication/recovery/passkey capability, `Seat` owns class-local
  actor authority and claim hashes, `IdentityProfile` remains display-only, and
  roster upload is documented as provisioning an inactive participant position
  rather than creating a student. Added `V2_CANONICAL_AUTH_RUNTIME_CUTOVER.md` to
  separate current bridge implementation facts from constitutional target docs, then
  updated the active migration tracker, development docs index, authority extraction
  plan, and Wave 3 risk doc to stop presenting pre-cutover v1 auth as current
  runtime guidance. Refreshed active teacher/student user guides that still described
  DOB-based claim or recovery flows.
- **Canonical identity foundation schema added** — Expanded `users` with unified
  auth, credential, session, role, and last-active-seat fields; added seat-owned
  claim verification hashes; made `identity_profiles` seat-bindable; and completed
  lifecycle fields for `user_invite_tokens` and `user_recovery_tokens`. Migration
  `a6d9c2e4f1b7` is additive and intentionally does not infer canonical bindings
  from deprecated `Student`, `Admin`, `TeacherBlock`, or class teacher ownership.
- **Fresh canonical database rebuild path repaired** — Hardened squash-era
  migrations that assumed historical `classes`, `transaction`, `users.username`,
  or `users.last_active_class_id` shapes even though `0001_bootstrap.py` creates
  live runtime metadata. The canonical seed no longer calls `db.create_all()` and
  now provisions canonical user, seat, seat-bound profile, and unclaimed-seat
  claim state before adding explicit legacy compatibility shadows.
- **Canonical identity principal backfill added** — Migration `b7e4c1d9a2f6`
  deterministically migrates credentialed legacy principals into `users`,
  normalizes existing bound-seat claim state, creates teacher seats for
  credentialed teachers' classes, and binds student display profiles to seats.
  The migration fails on username, role, or seat-binding ambiguity and does not
  derive authority from `TeacherBlock`. Successful login sessions now populate
  canonical `user_id` when a migrated user exists, and deprecated user-session
  aliases are no longer read or written.
- **Canonical User credential login activated for TOTP and PIN flows** — Teacher,
  student, and system-admin login now resolve and verify credentials from `users`
  before resolving deprecated principal rows as route compatibility shadows.
  Student claim/setup, teacher signup/reset, system-admin provisioning, and
  student recovery now keep canonical credentials synchronized; legacy-only
  principals and missing canonical recovery identities fail closed. Passkey
  external IDs remain a separate legacy-backed cutover.
- **Passkey credential ownership moved to canonical users** — Added migration
  `c8f1e2d3a4b5` to store canonical `user_id` owners on teacher and system-admin
  passkey metadata, backfill existing credentials, and fail closed on unmapped
  rows. Passwordless registration/authentication now uses `user_<User.id>`
  external IDs; legacy `admin_<id>` and `sysadmin_<id>` passkey principals are
  rejected.
- **Auth resolvers now require canonical user identity** — `get_current_admin()`,
  `get_current_system_admin()`, and `get_logged_in_student()` now resolve the
  canonical `User` first and only then hydrate deprecated `Admin`, `SystemAdmin`,
  or `Student` route shadows. Raw legacy session IDs alone no longer establish
  resolver identity.
- **Ledger Identity Severance Completed (Wave 5 / Phase 1C)** — Formally decommissioned `student_id` from the canonical ledger tables (`ledger_transaction` and `ledger_balance_snapshot`). All balances and financial histories are now strictly derived via `seat_id` + `class_id` joints. `Student.transactions` backrefs were replaced with explicit seat-proxied properties. `db.session.in_nested_transaction` support was formalized in the FEAT orchestrator to allow savepoints within top-level atomic feats without violating authority isolation.
- **Support issue actor reference now uses canonical public actor naming** — Support
  issue rows now expose the filing seat's UUID `Seat.public_id` as
  `issues.actor_public_id`, matching the same actor-public identity language as TLCP.
- **TLCP support correlation now uses seat public IDs at runtime** — Request traces,
  error events, support-ticket correlation packs, and student recent-error prompts now
  use the active class-scoped `Seat.public_id` value instead of generating a separate
  student-wide actor marker. Physical TLCP columns, indexes, log labels, tests, and
  sysadmin copy affordances now use `actor_public_id`.
- **Class-scoped teacher public lookups now use teacher-seat UUIDs** — New class anchors provision a teacher `Seat`, `/api/hall-pass/verification/active` now requires one explicit `class_id` plus that teacher seat's UUID `public_id`, and the obsolete `/student/switch-teacher/<teacher_public_id>` route now returns `404`. Hall-pass pass-type lookup rejects `teacher_public_id` input, and explicit invalid `join_code` aliases now fail closed instead of falling back to another claimed seat.
- **Seat public identity formalized as one UUID family** — Added the normative v2 identity ownership model: `users.id` authenticates, `seats.id` acts, `classes.class_id` scopes, and UUID-encoded `seats.public_id` is the single deidentified public actor identifier for both teacher and student seats. Role-specific public-ID fields and separate TLCP actor identity families are now classified as invalid v2 residue rather than supported identity alternatives.
- **Class-period metadata is being formalized as `section` on `classes`** — The v2 architecture docs now explicitly define `section` as the canonical metadata field for labels such as `2`, `Block A`, and `Period 1`, while `display_name` remains the human-facing class title such as `Honors Chemistry`. Remaining `block` fields are transitional naming debt and should not be treated as canonical identity or authority.
- **Teacher student-detail URLs now expose class-local seat public IDs only** — Numeric `/admin/students/<student_id>` detail URLs now return `404`. Teacher-facing student-detail links use signed, short-lived navigation URLs carrying `seats.public_id`, and route resolution requires the seat public ID, signed token class, teacher ownership, and active `current_class_id` to identify the same seat. This prevents cross-class seat selection for shared students, including when one teacher owns both classes.
- **Class-scoped feature authority and disabled-route behavior tightened** — Admin feature pages now enforce class-scoped feature toggles as the sole authority and render a dedicated disabled page with a direct link to feature settings; student feature-gated routes now return hard `404` when disabled. Feature settings UI is now per-period only.
- **Runtime settings normalization toward `class_id` authority** — Payroll, analytics, student banking settings, rebalance activation, and admin settings cleanup paths were updated to resolve class scope and query settings rows by `class_id`, reducing reliance on teacher/global settings reads in active runtime paths.
- **Class-scoped test fixtures aligned with clean-break semantics** — Rent waiver tests now seed canonical `RentSettings` scope (`class_id` + `join_code`) to match runtime authority.
- **Wave 2 bootstrap migration squash started** - Archived 196 legacy Alembic revisions into `migrations/archive/v1_196_migrations/`, introduced `migrations/versions/0001_bootstrap.py` as the new baseline head (`down_revision = None`) to idempotently co-create legacy and canonical tables, and added `scripts/verify_migration_squash.py` to assert head/table expectations.
- **V2 money authority model closed** — Student, admin, sysadmin, and redemption money paths now funnel through FEAT/domain services into `ledger_service`, with `Transaction(` construction restricted to `app/services/ledger_service.py` and enforced by structural guardrails.
- **Admin-side authority extraction completed for money workflows** — Payroll runs, manual payroll adjustments, bonus/fine flows, insurance claim reimbursement, transaction void, and bug-reward issuance no longer create money rows inline in route handlers.
- **Transfer zero-sum invariant is now explicit** — Added a class-scoped critical smoke test proving canonical transfer pairs net to zero within a `join_code` boundary and remain isolated from transfer activity in other class scopes.
- **District assurance brief page and trust-link rollout** — Added the district-facing `/district-assurance` page and linked it from privacy and authentication-related templates so the v2 branch exposes the current data-protection summary across key entry points.
- **Foundational v2 architecture corpus expanded** — Added execution-model, core-invariant, and capability-architecture foundation documents plus parked realignment drafts so the branch carries a clearer written baseline for the ongoing rebuild.
- **Architecture invariants now capture rebuild intent and downstream consequences** — Expanded each v2 architecture invariant with explicit "Rebuild Intent" and "Downstream Consequence" sections to formalize which migration constraints future work must preserve.
- **Collective goal reactivation strict scoping** — Added deterministic UUID-based instance mapping for collective goals using `collective_goal_instance_code` across `StoreItem` and `StudentItem` ensuring robust reactivation progress tracking preventing bleed across past purchase states. Replaced lazy overlaps with direct DB inner join references.
- **v2 launch-readiness checklist reconciled with current docs state** — Updated the readiness matrix, launch project checklist, reconciliation tracker, README, and documentation SOP references so branch-local launch planning stays aligned with the latest branch status.
- **v2.0 launch-readiness and rehearsal documentation finalized** — Refreshed the v2 tracking artifacts, rehearsal checklist, and final live-test report so `codex/v2.0` reflects the current branch state, readiness blockers, and production transition guidance.
- **Class-scoped admin and student onboarding workflow expansion** — Added join-code and class-ID aware admin context handling for student addition, store management, and rent item sync, then extended student claiming and class-membership flows to preserve class scope during teacher-managed onboarding.
- **Attendance, migration validation, and test date handling tightened** — Aligned attendance calculations and tests around timezone-consistent date handling, expanded migration upgrade/downgrade validation checks, and updated attendance status handling to recognize the "done for the day" completion path.
- **v2.0 live-test candidate documentation refresh** - Updated the living engineering docs to reflect the consolidated v2 branch, current PostgreSQL test evidence (`708 passed, 1 skipped`), resolved migration heads, and the v2 authority model where `ClassEconomy` and `ClassMembership` define class scope. Added explicit live-test and production transition runbooks, refreshed architecture/API/schema references, and updated user guides that previously implied numeric teacher IDs, teacher-global class behavior, or legacy fallback semantics.
- **ClassEconomy and ClassMembership data-integrity hardening** — Added SQLAlchemy `Enum` types for `ClassEconomy.status` (active, archived), `ClassMembership.role` (admin, student), and `ClassMembership.status` (active, archived). Aligned the membership XOR check constraint name with existing DB constraints and added migration `a11213ca4afb` to normalize invalid values and enforce strict DB check constraints for class economy status, membership status, and membership role consistency. (Addresses PR #1078 review comments)

### Fixed
- **Test database reset stability for v2 Postgres runs** — Improved the test reset path by disposing pooled connections before rebuilding the database state, reducing failures caused by lingering connections during repeated v2 test runs.
- **DB-level student ownership invariant enforcement** — Added migration `1adc6456ab0e` with deferrable PostgreSQL constraint triggers that reject commits where any `students` row exists without at least one `student_teachers` link. This hardens the "no global/orphan student state" rule at the database layer during join-code/class deletion workflows.
- **Student account claim failure when teachers upload roster with same name twice** — Fixed `_sync_identity_profile()` which was skipping `IdentityProfile` creation when `first_name` or `last_initial` was empty, leaving `identity_id` as NULL. This caused `TeacherBlock` inserts to fail with a NOT NULL constraint violation. Now uses placeholder values `"[Unknown]"` and `"?"` if identity fields are missing, ensuring the profile is always created. By-product: When multiple roster uploads or manual adds target the same student, the claim flow now handles partial-state records gracefully. Cleaned up one limbo student (Student#2) that was linked to multiple unclaimed seats due to duplicate add attempts.
- **Test: Removed false positive assertion for non-existent sysadmin teacher deletion** — The test `test_manage_teachers_hides_delete_actions` was asserting that "Teacher-managed" text appears in the sysadmin manage-teachers template, but this text doesn't exist. The assertion was removed since the actual intent of the test (verifying delete URLs are NOT present) is already correctly validated.
- **Foreign key violation when adding individual students** — Fixed `IntegrityError` in `add_individual_student` and `_link_student_to_admin` where `TeacherBlock` records were created without first ensuring the parent `ClassEconomy` record exists. Both functions now call `_ensure_join_code_anchors` before creating `TeacherBlock` records to satisfy the `fk_teacher_blocks_join_code_class_economies` foreign key constraint.
- **Rent validation recommendation mismatch for block-scoped API checks** — Updated `EconomyBalanceChecker.validate_rent_value()` so block-scoped rent validation uses AGENTS monthly multipliers (`2.0x-2.5x`, default `2.25x`) while global validation continues to honor policy-mode weekly burden conversion. This resolves incorrect minimum recommendations (for example `$733.76` instead of `$562.50`) in `/admin/api/economy/validate/rent` for class-selected flows.
- **Pre-merge fix: Missing ClassEconomy and ClassMembership models** — Added `ClassEconomy` and `ClassMembership` SQLAlchemy models to `app/models.py` to match the `class_economies` and `class_memberships` tables created in prior migrations. These models were referenced in `app/utils/deletion.py`, multiple test files, and `tmp_admin.py` but were absent from the model layer, causing `ImportError` at startup.
- **Pre-merge fix: Stale `admin_id` column name in test fixtures** — Updated 58 test files (121 occurrences) to use `teacher_id` instead of `admin_id` when constructing or querying `StudentTeacher`, `DeletionRequest`, and `RecoveryRequest` records, after migration `c4e1a2b3d4f6` renamed those columns.
- **Economy analytics/report class-scoping hardening** — Removed teacher-global fallback behavior for selected-class analytics windows and economy API checks. `analytics.py`, `analytics_engine.py`, and admin economy APIs now resolve class settings with join-code-first precedence (join-code scoped rows first, then legacy block-scoped compatibility rows), instead of falling through to `block=None` teacher-global rows during class-selected flows.
- **Join-code strict scoping for hall-pass availability** — `/api/hall-pass/available-types` now supports `join_code` and `teacher_public_id` identity inputs and enforces active class scope for student sessions; legacy numeric `teacher_id` fallback was removed.
- **Join-code strict scoping for student settings lookups** — Student banking/rent/feature settings resolution now uses current class context (`teacher_id` + `join_code`, block-preferred) across transfer, interest, insurance purchase, shop rent checks, and rent payment flows. Direct teacher-only settings queries were removed from these routes.
- **Legacy numeric student teacher-switch route disabled** — `/student/switch-period/<int:teacher_id>` no longer mutates class context; students are redirected to use join-code/public-id based class switching only.
- **Broken help/guide links after doc system revamp** — Updated all doc path references in `layout_admin.html`, `layout_student.html`, `admin_insurance.html`, `admin_store.html`, and `admin_payroll.html` from hyphenated paths (e.g., `teacher-students`) to the new slash-separated directory structure (e.g., `teacher/students`).
- **Passkey "Never used" always displayed** — Passkeys are tracked in our database without a `credential_id` (credentials are managed on the Passwordless.dev servers). The auth-finish handler was looking up credentials by `credential_id` (which is always `NULL`), so `last_used` was never updated. Fixed by updating `last_used` on all credentials for the authenticated admin/sysadmin when a successful passkey sign-in occurs.
- **Rent coverage month label off by one for end-of-month due dates** — The coverage month label was computed by building a datetime for the due date and adding 1 day, which caused due dates on the last day of the month (e.g., Jan 31) to roll into the next month (Feb). Coverage month is now derived directly from `payment.coverage_month` and `payment.coverage_year`, which already hold the correct billing period.
- **Docs: GitHub-style alert rendering** — `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, and `> [!CAUTION]` callouts in markdown files now render as styled alert boxes instead of displaying the raw `[!TYPE]` text inside a plain blockquote. A `preprocess_github_alerts()` pre-processor was added to `app/routes/docs.py` that converts alert blockquotes in the markdown source before the library renders them, circumventing a Python `markdown` library limitation where adjacent blockquotes are merged into one element. Each alert body is rendered through a dedicated markdown pass so inline and block markup (bold, code, links, lists) inside the alert body is fully processed. Five alert types are supported with on-brand colours and Material Symbols icons: Note (blue/info), Tip (teal/lightbulb), Important (purple/priority_high), Warning (amber/warning), Caution (red/dangerous).
- **Docs: Unordered list display** — Lists were sometimes rendering without bullets due to missing `list-style-type` declarations and Python markdown's "loose list" behaviour (wrapping each item's content in `<p>` tags, which some browser/CSS combinations display as block paragraphs). Added explicit `list-style-type: disc/decimal`, `display: list-item`, and compact `<p>`-inside-`<li>` margin rules to the documentation stylesheet.

## [1.9.0] - 2026-03-04

### Security
- **Class Deletion Audit** — Comprehensive audit of all four class/period deletion paths, identifying inconsistent semantics, a P1 BalanceCache orphaning bug, sysadmin use of the deprecated `Student.block` field, and missing data-loss warnings in sysadmin confirmation dialogs. See `docs/SECURITY/AUDITS/SEC-AUD-011_Class_Deletion_Audit.md`.
- **P1 fix: BalanceCache orphaning** — `_hard_delete_join_code_scope` now deletes `balance_cache` rows for the deleted `join_code`, preventing stale balance reads after class deletion.
- **P2 fix: Sysadmin period deletion scope** — `delete_period` now resolves the period name to its `join_code(s)` via `TeacherBlock` before finding enrolled students, replacing the deprecated `Student.block` field lookup.
- **P2 fix: Sysadmin confirmation UX** — Period and teacher account deletion dialogs now accurately describe what is preserved versus removed and note the action cannot be undone.
- **P3 fix: Orphaned settings cleanup** — `_hard_delete_join_code_scope` now deletes `PayrollSettings` and `RentSettings` for block names that have no remaining `TeacherBlock` entries after a join-code deletion.

### Changed
- **Post-claim PII minimisation** — `dob_sum` and `last_name_hash_by_part` are now deleted from both the `TeacherBlock` roster seat and the `Student` record immediately after a student completes account setup. These fields are only needed during the one-time claim verification; retaining them afterwards served no purpose and increased the sensitive-data footprint.
  - `TeacherBlock.dob_sum` and `TeacherBlock.last_name_hash_by_part` are nulled when `is_claimed` is set to `True` (all claim paths: initial claim, add-class, recovery).
  - `Student.dob_sum` and `Student.last_name_hash_by_part` are nulled in `setup_pin_passphrase` once credentials are established; `has_completed_profile_migration` is set to `True` at the same time to suppress the legacy migration prompt.
  - `TeacherBlock.dob_sum` and `TeacherBlock.last_name_hash_by_part` database columns made nullable via migration `a1b2c3d4e5f6`.
- **Simplified student account recovery** — The recovery flow no longer asks students to re-enter their name and date of birth. The new two-step flow is: enter join code + reset code → set up new username + credentials. First name and last initial are preserved from the teacher-managed roster and are not editable by the student.
  - `recovery.account_lookup` now clears credentials (username, PIN, passphrase) directly on successful code verification and redirects to `student.create_username`.
  - `recovery.verify_identity` is retired; the route now redirects to `recovery.account_lookup` so bookmarked URLs remain functional.
- **`add_class` credential verification scoped to target class** — When a student adds a new class, credentials (first initial, last name, DOB) are now verified exclusively against the target class's own unclaimed roster seat hashes. The previous pre-check against the student's stored `dob_sum` (which is null post-claim) has been removed. Each join_code is an independent verification universe; claiming one class does not expose or depend on hashes from another.
- **`claim_account` duplicate detection** — Finding an existing student during initial claim now uses `first_half_hash` lookup instead of `dob_sum` filter, which remains correct after post-claim PII cleanup.
- **Documentation system consolidation** — Migrated remaining loose markdown files into the canonical documentation taxonomy under `docs/LOGS/AUDITS`, updated references to the new locations, and refreshed the canonical docs index.

### Added
- **Collective Goal Expiration** — Teachers can now set an optional expiration date on collective goal store items.
  - If the goal is met before the deadline, the item unlocks normally (existing behavior unchanged).
  - If the deadline passes without the goal being reached, all pending purchases are automatically refunded, the item is deactivated, and a `voided` status is recorded for each affected `StudentItem`.
  - Expiration is processed lazily: triggered on admin store page load, student shop load, and at purchase time — no background scheduler required.
  - Teacher deactivating an active collective item also triggers automatic refund for all pending purchasers.
  - A reactivated collective goal always starts progress at zero because voided `StudentItem` records are excluded from the progress count.
  - New `collective_goal_expires_at` column on `StoreItem` with Alembic migration `e3f4g5h6i7j8`.
  - New `app/utils/store.py` module with `refund_pending_collective_purchases()` and `process_expired_collective_goals()` helpers.
  - 16 new tests in `tests/test_collective_goal_expiration.py` covering happy paths, edge cases, API blocking, and multi-tenancy scoping.
- **Admin Transaction Backfill** — One-time remediation page (`/admin/backfill-transactions`) that lets teachers fix student balances when past transactions lack a class-period `join_code`. Detected automatically on dashboard load; teachers select the correct period for each affected student and the system links all orphaned transactions to the right class context.
- **Interactive Project Timeline** — New `/docs/timeline` page showcasing the full development history of Classroom Token Hub
  - Visual vertical timeline organized into four eras: Genesis, Crisis Resolution, Feature Expansion, and Refinement
  - Filter bar: All / Features / Fixes & Crises / Security / Architecture / Philosophy
  - Expandable version cards with details on every release from v1.0.0 through current unreleased
  - Design Philosophy section with all ten anti-goals and core educational principles
  - Scroll-triggered entry animations with intersection observer
  - Linked from the Help & Support Center (`/docs/`) index and Quick Links section
  - Added `docs/LOGS/AUDITS/LOG-ARC-039_Project_Timeline.md` as the source timeline document

### Changed
- **Audit follow-up for canonical v2 repair slices** — Updated the rent-display test fixture to full canonical student display names, recorded the implied-authority doc gaps in `docs/TRACKING/AUDIT_IMPLIED_AUTHORITY_TODO.md`, and confirmed the repaired policy-mode and collective-goal slices still pass targeted validation.
- **System Admin interface redesigned** - Complete redesign matching teacher/student interface patterns
  - **Mobile-friendly layout** - Fixed sidebar with hamburger toggle on mobile, mobile bottom navigation bar with quick access to Dashboard, Teachers, Support, Logs, and Announcements
  - **Dashboard revamped** - Stat cards (Total Teachers, Total Students, Active Invites, Open Tickets), 6 quick-action buttons, recent teacher registrations and errors panels, system admins table
  - **Teacher Management consolidated** - Unified page combining invite code generation/voiding (with copy-to-clipboard and void button), teacher accounts with class badges, student counts, last login, status, and per-period/account deletion actions; pending deletion requests displayed in a dedicated table
  - **Logs consolidated** - New combined `/sysadmin/combined-logs` page with tabbed Error Logs and Network Activity views; raw system log viewer removed (Grafana available instead)
  - **Support Tickets unified** - New combined `/sysadmin/support` page showing both User Reports (teachers + students) and Escalated Issues in tabs; bug bounty reward workflow preserved; detail views link back to the unified page
- **Template Design System Unification** - Standardized template styling across teacher, student, and sysadmin views
  - Replaced legacy Bootstrap icon usage (`bi-*`) with Material Symbols in templates and JS-rendered button states
  - Removed legacy opacity utility patterns (`bg-opacity-*`) in favor of semantic subtle backgrounds (`bg-*-subtle`)
  - Replaced hardcoded inline color literals in template style contexts with token/semantic values
  - Normalized standalone and shell templates to use consistent token-driven theming behavior

### Added
- **`void_invite_code` route** (`/sysadmin/manage-teachers/void/<id>`) - Allows sysadmin to void unused invite codes directly from the Teacher Management page
- **`combined_logs` route** (`/sysadmin/combined-logs`) - New consolidated log viewer combining error logs and network activity
- **`support_tickets` route** (`/sysadmin/support`) - New consolidated support ticket view combining user reports and escalated issues
- **`open_tickets` stat** on dashboard - Shows sum of new user reports + pending/in-review escalated issues

### Performance
- **Read-Path Audit & Optimization** - Conducted comprehensive audit of student list rendering and admin dashboard performance
  - **Removed Write-on-Read Side Effects**: Refactored `Student.checking_balance`, `Student.savings_balance`, and `Student.total_earnings` properties to be read-only calculations. Moved legacy automated settlement logic (which triggered database writes during read operations) to explicit mutation endpoints (`/transfer`, `/pay-rent`). This eliminates race conditions and significantly improves read performance.
  - **Optimized Admin Dashboard internals**: Refactored daily limit enforcement (`auto_tapout`) to use batch processing instead of per-student iteration and moved dashboard balance calculations to batched, scoped queries. Stage 2 audit kept dashboard query totals unchanged at 402 (explicit dashboard query-count reduction remains out of scope for this stage).
  - **Optimized Student Roster**: Eliminated N+1 query patterns in the student management table by batch-fetching balances and rent privileges. Query count reduced from ~1225 to ~10 for a class of 60 students.
  - **Scoped Balance Calculations**: Fixed a critical multi-tenancy flaw where student balances were aggregated across all classes instead of being scoped to the current teacher's context. Dashboard and roster now correctly reflect class-specific financial state.

### Fixed
- **Student rent/shop regression follow-up** - Addressed review-driven cleanup after the rent/store hotfix
  - Added shared helper logic for determining whether a student's current rent coverage period is paid, and reused it across student rent/shop and API purchase flows to reduce duplicated validation code
  - Kept incremental rent payment form available when incremental mode is enabled (even when full remaining balance exceeds checking), so partial payments are not blocked in the UI
  - Corrected mixed rent-link behavior in student shop so privilege-only rent items are deactivated while per-use rent perks remain purchasable at `$0`
  - Made the mixed rent-link regression test time-independent by using a relative due date instead of a fixed calendar date
- **Student store block scoping** - Student shop and purchase APIs now enforce block visibility while preserving the existing "no block mapping = visible to all blocks" semantics for unscoped legacy items
- **Student markdown toolbar icons restored** - Reintroduced Font Awesome in the student layout so markdown editor toolbar icons render correctly on student issue forms
- **Student payroll rate lookup** - Student payroll page and status projections now pass teacher context into pay-rate resolution so block-specific teacher rates display correctly instead of defaulting
- **P0: Duplicate auto-tap-out events causing payroll overpayment** - Added idempotency check to prevent race conditions when multiple sources (student browser polling, scheduled job, admin dashboard) call auto-tap-out logic simultaneously. Previously, duplicate "Daily limit reached" tap-out events would be created, causing payroll to count the same session multiple times and resulting in massive overpayment. Now checks if a daily limit tap-out already exists before creating a new one. Includes cleanup script (`cleanup_duplicate_tapouts.py`) to fix existing duplicate records. See `docs/LOGS/AUDITS/LOG-ARC-038_Duplicate_Tapout_Bug_Report.md` for full details.
- **Void redemption creating transactions without join_code** - Fixed `/api/reject-redemption` endpoint creating refund transactions with `join_code=NULL` when voiding redemptions for legacy StudentItem records. Added fallback logic to resolve join_code from TeacherBlock or current session when StudentItem.join_code is NULL, preventing balance fix warnings for teachers. This resolves the "Fix Student Balances" alert appearing after voiding old redemptions.
- **Void transaction CSRF 400 error** - Fixed student detail page void transaction button failing with 400 error. Added missing X-CSRFToken header to fetch request in `voidTransaction()` JavaScript function. Teachers can now successfully void transactions from student detail pages.
- **P0: Rent payment applied to wrong period with bill preview enabled** - Fixed critical bug where students with unpaid overdue rent were allowed to pre-pay for future periods instead of paying overdue amounts first. When bill preview was enabled with a long preview period (e.g., 30 days), the system incorrectly classified overdue students as being in "preview period" for next month's rent. This caused payments to be recorded for the wrong coverage period (next month instead of current/overdue month), preventing students from receiving rent benefits even after paying. Now verifies current coverage period is fully paid before allowing preview period payments. Students must pay oldest overdue period first, and benefits are granted immediately when current period is paid. Also fixed rent page to display correct period being paid for with OVERDUE badge when applicable.
- **Rent transaction month label now matches the coverage period being paid** - Fixed rent payment transaction descriptions to use the selected coverage due date (e.g., January 2026 for overdue January rent paid on February 17) instead of the wall-clock payment month. This keeps late-fee transactions aligned with the actual rent period and avoids showing overdue January payments as February charges.
- **Recovery and Claim Page Styling Not Applying** - Fixed account claim/recovery pages that referenced design tokens but did not load `tokens.css`
  - Added missing `tokens.css` includes in standalone recovery/claim templates
  - Corrected student recovery layout shell class from `student-theme` to `student-shell`
  - Restored valid template syntax in `student_detail.html` that affected recovery-related page rendering/tests
- **Documentation site link integrity** - Corrected stale docs navigation paths, breadcrumb dead links, and release-note route resolution so technical docs render from the current taxonomy with validated internal/external links.

## [1.8.0] - 2026-02-09

### Added
- **Rent Item Types (Privilege / Per-Use / Hall Pass)** - Extended itemized rent with three distinct item types
  - **Privilege**: Shows as a badge on the roster when rent is paid; optionally listed in store for individual purchase
  - **Per-Use**: Grants free store redemptions when rent is paid (single-use by default, or limited uses when set); always listed in store with "Rent Perk" badge; cannot be deleted from store (only via rent settings)
  - **Hall Pass**: Tops off student hall passes when rent is paid using source-tracking model (rent-granted vs purchased passes tracked separately via `StudentBlock.rent_hall_passes`)
  - **Mid-period edit guardrail**: Once any student has paid rent for the current period, item type, use limits, and hall pass counts are locked; only cosmetic changes (name, description, price) are allowed
  - **Store integration**: Per-use items marked `is_rent_linked` on `StoreItem`, preventing accidental deletion; admin store shows "Rent Perk" badge with disabled delete buttons for linked items
  - **Multi-use item tracking**: Added `uses_remaining` to `StudentItem` for per-use rent items with limited uses
  - **Free uses from rent**: When rent is fully paid, per-use items grant a free `StudentItem` with `uses_remaining` set (default 1); students can redeem these at no cost via the store
  - **Free purchase flow**: Store purchase route checks for active rent-granted uses before charging; shows "Free use (rent perk)" message
  - **Student shop indicators**: Rent-linked items show free uses remaining badge; "Included in your rent!" only shown for privilege-type items
  - **Models**: Added `rent_item_type`, `use_limit`, `hall_pass_count` to `RentItem`; `is_rent_linked` to `StoreItem`; `rent_hall_passes` to `StudentBlock`; `uses_remaining` to `StudentItem`
  - **Migrations**: `c2d9cf951ddc`, `9b0e06f05fcf`, `2765a36d76ff` (all idempotent)
- **Pre-paid Rent Coverage Period Tracking** - Rent payments now explicitly track which period they cover
  - Added `coverage_month` and `coverage_year` columns to `RentPayment` model
  - Paying rent on the due date (e.g., 1/28) now covers the student from 1/29 to the next due date (2/28)
  - All rent privilege checks, purchase blocking, dashboard status, and shop indicators use coverage-based lookups
  - Itemized rent item purchases (`per_period` duration) follow the same coverage period
  - **Migration**: `a1b2c3d4e5f6` adds columns with backfill from existing `period_month`/`period_year`

### Fixed
- **Privilege Badges Showing Non-Privilege Rent Items** - Fixed roster badge display to only show privilege-type rent items, not per-use or hall pass items
  - **Issue**: `_build_rent_privileges_by_block()` and `_get_rent_privileges_for_student()` filtered by `purchase_duration='per_period'` but not `rent_item_type='privilege'`, causing per-use and hall pass items to incorrectly appear as roster badges
  - **Solution**: Added `rent_item_type='privilege'` filter to both functions and the student shop "Included in your rent!" indicator
- **Insurance Class Selector Not Filtering Data** - Fixed multi-tenancy scoping issue where insurance management page showed all classes' data regardless of selected class
  - **Issue**: The "Viewing Insurance For" dropdown on the Insurance Management page did not filter policies, enrollments, or claims. Teachers with multiple class periods saw all insurance data aggregated together instead of scoped to the selected period.
  - **Root Cause**:
    - `InsurancePolicy` queries filtered only by `teacher_id`, not by `InsurancePolicyBlock.block`
    - `StudentInsurance` enrollments were not filtered by `join_code`
    - `InsuranceClaim` queries did not include `join_code` filtering
  - **Solution**:
    - Added `InsurancePolicyBlock` join to filter policies by selected block (or show policies available to all blocks)
    - Added `join_code` lookup from `TeacherBlock` for the selected period
    - Added `join_code` filter to all `StudentInsurance` and `InsuranceClaim` queries
  - **Impact**: Teachers now see only the insurance policies, enrollments, and claims for the currently selected class period
- **Store Purchase Blocked After Rent Paid Across Month Boundary** - Fixed rent-check logic using wrong month/year when verifying rent payments
  - **Issue**: `purchase_item()` used `now.month`/`now.year` instead of `current_due.month`/`current_due.year` when querying `RentPayment`. When a rent due date fell in January but the purchase check ran in February (past the grace period), the query looked for February payments and found none, incorrectly blocking the student.
  - **Solution**: All rent lookups now use `coverage_month`/`coverage_year` derived from the due date, not the wall-clock time
- **Issue Ticket Filing Fails With "An error occurred"** - Fixed Decimal serialization error in issue context snapshots
  - **Issue**: `create_context_snapshot()` stored raw `Decimal` objects (balances, transaction amounts) in a dict destined for a `db.JSON` column. Python's `json` module cannot serialize `Decimal`, causing a `TypeError` caught by the generic exception handler.
  - **Solution**: Convert all `Decimal` values to `float` before storing in the context snapshot
- **Duplicate Store Items When Applying Rent to All Periods** - Fixed `_sync_rent_items_to_store` creating duplicate store items
  - **Issue**: When a teacher applied rent settings to multiple blocks, each block created its own store item copy instead of sharing one item with block visibility
  - **Solution**: Look up existing store items by `teacher_id` + `name` before creating new ones; use `StoreItemBlock` to add block visibility without replacing existing associations

### Changed
- **Redundant Check Removal** - Simplified `_add_period` utility function in `app/routes/api.py` by removing a redundant `isinstance` check.
- **Documentation Update Plan Retired** - Removed `docs/development/DOCUMENTATION_UPDATE_PLAN.md` after v1.7 documentation updates were completed and tracked.

### Security
- **Hardened Grafana Proxy XSS Protection** - Improved content-type filtering to prevent XSS attacks (#897)
  - **Issue**: Original implementation had case-sensitivity issues, missed dangerous MIME types (SVG), and could be bypassed
  - **Solution**:
    - Made Content-Type check case-insensitive per RFC 2045
    - Added `image/svg+xml`, `text/xsl`, and `application/xslt+xml` to blocked MIME types
    - Properly handles Content-Type parameters (e.g., "text/html; charset=utf-8")
  - Prevents reflected XSS attacks via Grafana proxy endpoint
- **Fixed Function Redefinition in Student Routes** - Removed duplicate `_is_safe_url` function definition (#897)
  - **Issue**: Two identical function definitions in `add_class()` route, causing code clarity issues
  - **Solution**: Removed redundant first definition, kept wrapper around shared `is_safe_url` helper
  - Improves code maintainability and prevents potential bugs from function shadowing

## [1.7.1] - 2026-01-22

### Fixed
- **CRITICAL: Decimal.InvalidOperation in Student Dashboard Earnings/Spending Calculations** - Fixed crash when calculating weekly/monthly analytics with NULL transaction amounts
  - **Issue**: Dashboard earnings and spending calculations compared `tx.amount > Decimal('0')` without checking for NULL
  - **Impact**: Student dashboard returned 500 error with `decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]` when corrupted transactions exist
  - **Affected Code**: Lines 1261-1283 in `app/routes/student.py` (earnings_this_week, earnings_this_month, spending_this_week, spending_this_month)
  - **Additional Fix**: Line 1697 in savings interest calculation also needed NULL check
  - **Solution**: Added null check (`tx.amount is not None`) before all Decimal comparisons in dashboard calculations
  - Completes the NULL handling fix from PR #885 which fixed the Student model properties
- **Duplicate Student Claim Handling** - Added IntegrityError handling for duplicate student account claims
  - **Issue**: Edge cases in deduplication logic could cause IntegrityError when claiming student accounts with duplicate `first_half_hash` values
  - **Solution**: Wrapped `db.session.flush()` in try-except block to catch IntegrityError and link to existing student accounts gracefully
  - Prevents crashes and provides better user experience when duplicate claims occur
- **NameError in Payroll Function** - Fixed import error for `calculate_payroll_breakdown` in admin routes
  - **Issue**: Admin payroll routes referenced `calculate_payroll_breakdown` without proper import
  - **Solution**: Added explicit import of `calculate_payroll_breakdown` from `app.payroll` module
- **Decimal.InvalidOperation in recent_deposits** - Fixed crash when accessing student dashboard with NULL transaction amounts
  - **Issue**: `Student.recent_deposits` property compared `tx.amount <= Decimal('0')` without checking for NULL
  - **Impact**: Student dashboard returned 500 error with `decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]`
  - **Solution**: Added null check (`tx.amount is None`) before comparison in both `recent_deposits` and `total_earnings` properties
  - Prevents crashes when database has corrupted transaction data with NULL amounts
- **CRITICAL: Float/Decimal Type Error in Savings Interest Calculation** - Fixed `TypeError: unsupported operand type(s) for *: 'float' and 'decimal.Decimal'` in `apply_savings_interest()` function
  - **Issue**: The `student.savings_balance` property returns a `float`, but interest calculations were using `Decimal` arithmetic. When the float balance was multiplied by a Decimal rate expression, Python raised a TypeError.
  - **Impact**: Student dashboard returned 500 errors when compound interest was enabled for the class
  - **Root Cause**: The Decimal refactoring (PR #882) updated the interest calculation logic to use Decimal, but the `savings_balance` property still returns float for backward compatibility with other parts of the codebase
  - **Solution**: Wrap `student.savings_balance` with `_quantize_currency()` to convert it to Decimal before performing Decimal arithmetic
  - **Location**: `app/routes/student.py` in `apply_savings_interest()` function, line 1621
- **Decimal JSON Serialization Error** - Fixed `TypeError: Object of type Decimal is not JSON serializable` in student dashboard and API endpoints
  - **Issue**: After Decimal refactoring, Decimal values in templates and JSON responses were not converted to serializable types
  - **Impact**: Student dashboard and `/api/student-status` endpoint returned 500 errors
  - **Solution**: Convert all Decimal values to float before passing to templates or JSON serialization:
    - `app/routes/student.py`: Dashboard variables (checking_balance, savings_balance, forecast_interest, earnings, spending, projected_pay_per_block)
    - `app/routes/student.py`: Student dashboard `period_states_json`
    - `app/routes/api.py`: `/student/start-work` and `/student/stop-work` endpoints (projected_pay)
    - `app/routes/api.py`: `/student/status` endpoint (period_states)
  - Maintains Decimal precision for calculations, converts only at template/serialization boundary
- **CRITICAL: Decimal Precision in All Financial Calculations** - Refactored all financial logic to use Python's `Decimal` type throughout, not just for database storage
  - **Issue**: PR #880 was a hotfix that converted `Decimal` to `float` to resolve TypeErrors, but introduced floating-point precision errors
  - **Impact**: Small residual balances accumulate over time, incorrect interest calculations, potential overdraft fee issues
  - **Solution**: Systematic refactoring of all financial calculations to use Decimal arithmetic
  - **Changes**:
    - Updated `Student.get_checking_balance()` and `Student.get_savings_balance()` to return Decimal instead of float
    - Updated `calculate_scoped_balances()` to return Decimal tuples
    - Refactored all interest calculations in `student.py` to use Decimal arithmetic with proper exponentiation
    - Updated `apply_savings_interest()` to use Decimal throughout for compound and simple interest
    - Refactored transfer route to convert form inputs to Decimal before validation
    - Updated rent payment processing to use Decimal for payment amounts
    - Updated `payroll.py` `get_pay_rate_for_block()` to return Decimal per-second rate
    - Refactored all `admin.py` financial form handling (rent, payroll, store items, rewards, fines) to use `_quantize_currency()`
    - Updated `api.py` demo session balance inputs to use Decimal
    - Updated `system_admin.py` reward amounts to use Decimal
    - Refactored `utils/economy_balance.py` CWI calculations and balance validators to use Decimal
    - Updated `_normalize_to_weekly()` helper to work with Decimal inputs/outputs
  - **Backward Compatibility**: Decimal objects convert to float only for JSON serialization and template rendering
  - **Testing**: All existing decimal precision tests pass; financial calculations now mathematically exact
- **Decimal.InvalidOperation in get_total_earnings** - Fixed crash when calculating student earnings with NULL transaction amounts
  - Added null check (`tx.amount is not None`) before comparison in `get_total_earnings()` method
  - Prevents `decimal.InvalidOperation` error on `/admin/students` page when database has corrupted transaction data
  - Handles edge case where historical data migrations or database inconsistencies result in NULL amounts
  - Fix applied to all three code paths (join_code, teacher_id, and no parameters)
- **CRITICAL: Floating-Point Rounding Errors in Financial Calculations** - Converted all financial amounts from Float to Decimal for exact precision
  - **Bug 1**: Transfers that zeroed out checking accounts incorrectly triggered $35 overdraft fees due to -0.00 balance representation
  - **Bug 2**: Partial rent payments left unpayable tiny balances (e.g., $0.0000001) due to float precision errors
  - **Fix**: Changed `Transaction.amount` from `Float` to `Numeric(12, 2)` in database for exact decimal representation
  - **Fix**: Updated all financial models (RentSettings, BankingSettings, PayrollSettings, StoreItem, InsurancePolicy, etc.) to use Numeric
  - **Fix**: Updated balance calculation methods to use Python's `Decimal` type instead of `float`
  - **Fix**: Added near-zero balance normalization (|balance| < $0.01 → $0.00) to prevent false overdraft fees
  - **Migration**: Created migration to convert all Float columns to Numeric(12, 2) without data loss
  - **Testing**: Added comprehensive test suite for edge cases (zero transfers, partial payments, near-zero balances)
- **Student Creation Without Deprecated teacher_id** - Removed deprecated `teacher_id` assignment when creating new students to prevent `TypeError: 'teacher_id' is an invalid keyword argument for Student`.
- **Scheduled Auto Tap-Out Transactions** - Avoided committing inside the scheduled auto tap-out loop to prevent closed-transaction errors during background checks.
- **Student Claim DOB Field** - Aligned the claim-account form field name with the templates to prevent 500 errors on /student/claim-account.
- **Student Transfer Banking Settings Import** - Removed a local import shadowing `BankingSettings` to prevent UnboundLocalError on /student/transfer.
- **Rent Calculation Accuracy** - Improved rent amount calculations for monthly display (#839)
  - Fixed daily rent calculation to use actual days in month (via `monthrange`) instead of approximating 30 days
  - Added support for 'custom' frequency type in rent calculation logic
  - Fixed timezone inconsistency by using timezone-aware `datetime.now(timezone.utc)` consistently
  - Added null checks for `grace_period_days` and `due_day_of_month` fields to prevent TypeError
  - Refactored duplicated late payment check logic into single code path
  - Optimized payments query using subquery instead of list comprehension for better performance
- **Rent Statistics Display** - Fixed incorrect student counts in rent overview cards (#839)
  - "Paid This Month" now correctly shows count of students who paid (not payment count)
  - "Unpaid This Month" now correctly shows count of students with outstanding balances
  - Both statistics use accurate `unpaid_students` calculation instead of payment count
- **Rent Period Display** - Fixed misleading "Period" column in unpaid students list (#839)
  - Now shows billing period (e.g., "January 2026") instead of class block/period
- **Hall Pass Queue Scoping** - Removed deprecated `students.teacher_id` filtering to prevent hall pass queue errors.

### Changed
- **Rent Calculation Helper** - Extracted rent amount calculation into reusable helper function (#839)
  - Created `_calculate_base_rent_amount()` helper to avoid code duplication
  - Used in both payroll warning calculation and unpaid students calculation
  - Follows DRY principle for better maintainability
- **CSP Headers for Public Hall Pass Pages** - Modified Content Security Policy to allow embedding for read-only hall pass display pages
  - `/hall-pass/verification` and `/hall-pass/queue` can now be embedded in external sites (e.g., Schoology, Canvas)
  - These pages are public, read-only displays with no state-changing actions
  - `/hall-pass/terminal` remains protected (not embeddable) as it performs state-changing check-in/check-out actions
  - Removed `X-Frame-Options` header for embeddable pages and added `frame-ancestors *` to CSP
  - All other pages remain protected with `X-Frame-Options: SAMEORIGIN` and `frame-ancestors 'self'`

## [1.7.0] - 2026-01-09

### Added
- **ToS Acknowledgment Modal** - Implemented a modal during admin sign-up that requires explicit acknowledgment of Terms of Service and Privacy Policy.
  - Modal blocks the sign-up process until the "I have read and agree" checkbox is checked.
  - `tos_accepted` status and timestamp are recorded in the `Admin` table.
  - Ensures compliance with legal requirements for teacher account creation.

### Fixed
- **Analytics Events Value Display** - Show zero-value economy changes in the analytics events timeline by checking for `None` instead of falsy values.
- **EasyMDE Form Submission** - Fixed issue where forms with EasyMDE markdown editors could not be submitted due to hidden required fields
  - EasyMDE markdown editor hides the underlying textarea, causing browser validation to fail on required fields
  - Removed HTML `required` attribute from hidden textareas after editor initialization
  - Server-side validation via `DataRequired()` still enforces required fields
  - Applied fix to insurance claim form (`student_file_claim.html`) and issue submission form (`student_submit_issue.html`)
  - Resolves console error: "An invalid form control with name='[field]' is not focusable"

### Added
- **Analytics Dashboard (Phase 1-3)** - System health observability dashboard per analytics specification
  - Three new database models: `AnalyticsSnapshot`, `AnalyticsEvent`, `AnalyticsAlert`
  - Analytics computation engine with CWI-relative metrics (no absolute balances/rankings)
  - System health metrics: participation rate, money velocity, CWI deviation bands, budget survival pass rate
  - Trend analysis: tracks improving/stable/worsening patterns across periods
  - Visual alerts with explanations (what changed, why it matters, suggested actions)
  - Event annotation system for rent changes, wage changes, inflation events
  - Metrics precomputed and cached by time window for 5-second readability
  - Weekly and monthly time window views
  - All metrics properly scoped by `join_code` for multi-tenancy compliance
  - Dashboard route at `/admin/analytics`
  - API endpoints for snapshot data and alerts
  - Comprehensive test coverage for analytics engine
  - Database migration: `a7b8c9d0e1f2_add_analytics_models`
  - Per spec: no student names in default views, no leaderboards, no comparative rankings
  - Design principle: "Something is drifting — and I know what lever to pull"
- **Mobile Navigation Enhancement** - Full navigation menu now accessible on mobile devices and PWA
  - Added floating hamburger menu button that appears on mobile (<768px)
  - Sidebar slides in from left with smooth animation and backdrop overlay
  - Help buttons now visible as icon-only on mobile screens
  - Contextual help links show icon on mobile, hiding text to save space
  - Same template works for desktop, mobile, and PWA - no separate mobile templates needed
  - Sidebar automatically closes when clicking navigation links or backdrop
  - Resolves PWA limitation where full navigation menu was previously inaccessible
- **Rent Itemization Feature** - Teachers can now specify what rent pays for and offer items as store alternatives (MVP)
  - New `RentItem` model to track itemized rent components (e.g., Desk, Chair, Locker)
  - Teachers can add/remove/reorder rent items in Rent Settings page
  - Optional store integration: mark items as "Available in Store" with custom pricing
  - Automated sync: items marked for store availability automatically create/update StoreItem records
  - StoreItem created with `limit_per_student=1` to enforce single-purchase behavior
  - Store items inherit block visibility from rent settings
  - Student rent view displays itemized breakdown showing what rent includes
  - Students see store price comparison for items available separately
  - Pro tip message encourages rent payment by showing total value comparison
  - Manual pricing (teacher sets store price manually - automatic pricing calculator coming in future release)
  - Database migration: `6feaa660d6c3_add_rent_item_table`
- **Enhanced Purchase Restrictions** - "Prevent Purchase When Late" toggle now has dynamic behavior based on itemization
  - When rent itemization is disabled: blocks ALL store purchases when student is late on rent (original behavior)
  - When rent itemization is enabled: students late on rent can ONLY purchase items covered by rent (at à la carte prices), all other store items blocked
  - Creates strong incentive structure: pay rent to get everything, or buy individual rent items at higher prices while missing out on other store items
  - UI dynamically updates toggle label and description based on itemization status
  - JavaScript updates label when items are added/removed dynamically
  - Implemented in `/api/purchase-item` endpoint with proper rent late detection and item validation
- **Purchase Duration Options for Rent Items** - Teachers can now choose how long individually-purchased rent items last
  - New `purchase_duration` field on RentItem model: 'per_use' or 'per_period'
  - **Per Use**: Student must buy each time they want to use it (unlimited purchases allowed)
  - **Per Rent Period**: Student buys once and can use until next rent is due (limit 1, expires when rent comes due)
  - Radio button selector in rent itemization UI with clear explanations
  - Store items automatically configured with appropriate purchase limits based on duration type
  - Purchase API calculates expiration dates for "per_period" items based on rent frequency settings
  - Automated expiration when next rent payment is due
  - Database migration: `h7i8j9k0l1m2_add_purchase_duration_to_rent_items`
- **Rent Privilege Badges** - Visual indicators on student detail page showing active rent privileges
  - Displays all "per_period" rent items that students currently have access to
  - **Green badges**: Privileges covered by paid rent (automatic for rent-paying students)
  - **Blue badges**: Privileges purchased individually (shows "(Purchased)" label)
  - Badges only show for non-expired privileges
  - Rent-paying students automatically receive all per-period privilege badges
  - Teachers can quickly see which students have which privileges at a glance
  - Hover over badges to see item descriptions

## [1.6.0] - 2026-01-01

### Added
- **Documentation Organization** - Improved repository structure and documentation consistency
  - Consolidated duplicate script files into scripts/ directory
  - Standardized file paths and references across documentation
  - Removed obsolete root-level duplicates
  - Improved navigation and file organization

### Fixed
- **Getting Started Widget** - Fixed onboarding widget state persistence issues
  - Widget state now persists to database instead of browser localStorage
  - Widget dismissal and task completion now sync across logins and devices
  - Skipped tasks are now properly marked as complete in the widget
  - Added `widget_tasks_completed`, `widget_dismissed`, and `widget_dismissed_at` fields to `TeacherOnboarding` model
  - Updated `/admin/onboarding/status` endpoint to check both actual setup AND manually skipped tasks
  - Added `/admin/onboarding/dismiss-widget` endpoint to persist widget dismissal
  - Widget state is per-teacher (not per-block) for consistent onboarding experience
- **Multi-Tenancy Violation** - Fixed critical bug where `HallPassSettings` records were created without `teacher_id`, violating NOT NULL constraint and breaking multi-tenancy isolation
  - Fixed `/api/hall-pass/settings` endpoint to scope settings by `teacher_id` from session
  - Fixed hall pass creation in `/tap` endpoint to retrieve `teacher_id` from `join_code` via `TeacherBlock` lookup
  - All `HallPassSettings` queries now properly scoped by `teacher_id` and `block`
- **Content Security Policy** - Restored `'unsafe-eval'` directive to `script-src` CSP policy as it is required by passwordless.dev library's minified build (uses `new Function()` internally)
- **Passkey Authentication** - Fixed environment variables not loading by specifying explicit path to `.env` file in `load_dotenv()` call - ensures environment is loaded regardless of gunicorn working directory
- **Passkey Authentication** - Fixed token destructuring in `signinWithDiscoverable()` to properly handle error responses from passwordless.dev SDK
- **Deployment** - Added verification steps to confirm environment variables are properly written to `.env` and loaded by systemd service
- **File Organization** - Fixed inconsistent paths for student upload template and script references

### Changed
- Consolidated duplicate scripts into scripts/ directory (seed_dummy_students.py, create_admin.py, etc.)
- Removed duplicate nginx configuration file from root
- Updated documentation to reference correct file paths

### Documentation
- Improved repository organization and file structure
- Updated path references throughout documentation
- Removed obsolete duplicate files

## [1.5.0] - 2025-12-29

### Added
- **Attendance Issue Reporting** - Students can now report issues with specific attendance/tap events (clock in/out records) directly from the Work & Pay page
  - New route `/help-support/tap-event/<id>/report` for reporting attendance record issues
  - Report buttons added to all tap event tables in Work & Pay > Attendance Record tab
  - Uses same issue resolution workflow as transaction reporting
  - Students can report up to 20 most recent tap events per block
- **Issue Resolution & Escalation System** - Structured, teacher-mediated issue handling system
  - **Student Features**:
    - New Help & Support interface with 3 tabs: Knowledge Base, Report an Issue, My Issues
    - Submit general issues (clock-in problems, features not working, balance incorrect, etc.)
    - Report transaction-specific issues directly from transaction history
    - Help icons next to each transaction in Recent Activity for quick issue reporting
    - Character-limited submissions (1000 chars) to encourage concise reporting
    - Automatic context capture: balances, transaction history, system metadata
    - Status badges (Submitted, Teacher Review, Resolved, Elevated, Developer Review) - no messaging
    - View all submitted issues with status tracking
  - **Teacher Features**:
    - Issue review queue with pending/resolved/escalated tabs
    - Detailed issue view showing student explanation, context, and transaction details
    - Resolution actions:
      - Reverse/void transactions directly from issue interface
      - Manual adjustment (teacher handles offline)
      - Deny issue with required explanation
    - Escalate to developer with:
      - Required escalation reason
      - Diagnostic notes for investigation
      - Optional class name sharing checkbox (default: opaque reference only)
      - **"Student may receive reward"** checkbox for legitimate bug reports
    - Complete status history and resolution action audit trail
  - **Technical Implementation**:
    - 4 new database models: `Issue`, `IssueCategory`, `IssueStatusHistory`, `IssueResolutionAction`
    - Default categories: 6 transaction types + 6 general issue types
    - Opaque student references for sysadmin privacy (non-reversible hashes)
    - Multi-tenancy scoping by `join_code` for proper class isolation
    - Context snapshots preserve ledger state at time of submission
    - Complete audit trail with timestamps and attribution
    - Immutable student submissions after creation
  - **Design Principles**:
    - No direct student-to-sysadmin communication
    - Teachers are first-line decision makers
    - Evidence-based issue tracking (tied to concrete transactions/records)
    - Data minimization for sysadmin review
    - Status badges only (non-communicative design)
  - Routes:
    - Student: `/student/help-support`, `/student/help-support/submit-issue`, `/student/help-support/transaction/<id>/report`
    - Teacher: `/admin/issues`, `/admin/issues/<id>`, `/admin/issues/<id>/resolve`, `/admin/issues/<id>/escalate`

### Changed
- Improved `flask create-sysadmin` command to display TOTP secret and QR code during account creation
  - Shows scannable QR code in terminal for easy authenticator app setup
  - Displays plaintext secret for manual entry backup
  - Auto-clears terminal after user confirmation for security
  - Secret remains encrypted in database after initial display
- Issue resolution UI refresh and workflow refinements
- Issue management and reporting refactor
- Standardized UTC timestamp formatting

### Fixed
- **Store Item Creation** - Fixed critical bug where tier, collective_goal_type, collective_goal_target, and redemption_prompt fields were not being saved when creating new store items
  - Added `tier` field assignment to store creation route (app/routes/admin.py:3047)
  - Added `collective_goal_type` and `collective_goal_target` field assignments for collective goal items (app/routes/admin.py:3063-3064)
  - Added `redemption_prompt` field assignment for delayed-use items (app/routes/admin.py:3066)
  - These fields were already present in the form (forms.py) and model (models.py), but were not being passed to the StoreItem constructor
  - Edit functionality uses `populate_obj` rather than manually assigning these fields, so this bug specifically affected the creation route
- **Transaction Issue Reporting** - Added report buttons to all transaction tables in Banking/Finances page (Checking and Savings tabs), allowing students to report issues on any visible transaction (up to 50 most recent), not just the 5 shown on dashboard
- **Issue Resolution Display** - Fixed `developer_resolved` status showing as "Escalated" instead of "Resolved by Developer" in teacher view
- **Issue Context Snapshot** - Fixed incorrect balance calculation in context_snapshot by using Student model's `get_checking_balance()` and `get_savings_balance()` methods instead of non-existent `get_balances()` function
- **Passkey Authentication** - Fixed missing username parameter in passkey authentication start request causing 500 error
- **Passkey Registration** - Fixed credential ID extraction from passwordless.dev SDK response by using correct destructuring pattern `{ token, error }`
- **Content Security Policy** - Added `https://static.cloudflareinsights.com` to `connect-src` directive to allow Cloudflare analytics
- **Content Security Policy** - Added `worker-src 'self' blob:` directive to allow Web Workers used by passwordless.dev library
- Fixed `time.tzset()` Windows compatibility issue in wsgi.py - now only calls tzset() on Unix-like systems
- Fixed admin signup crash when using SQLite - handles datetime fields stored as strings
- System Admin announcements form `ValueError` by adding a custom `coerce` for the `target_teacher` field

### Security
- Enhanced privacy protection in issue resolution system through opaque student references
- Teacher-controlled data disclosure to sysadmins (optional class name sharing)
- **Content Security Policy** - Removed unnecessary `'unsafe-eval'` directive from `script-src` to strengthen XSS protection (passwordless.dev library does not require dynamic code execution)

### Documentation
- Reorganized documentation structure for improved navigation
- **Developer Documentation Updates** - Updated development tracking documentation to reflect current status
  - Updated `DEVELOPMENT.md` to reflect v1.6.0 status (was showing 1.4.0)
  - Added v1.5.0 and v1.6.0 release summaries to Recent Releases section
  - Updated target version from 1.5.0 to 1.7.0
  - Updated `IMPLEMENTATION_PROGRESS.md` to mark sysadmin routes and templates as completed (were incorrectly marked as pending)
  - Added detailed test coverage priorities and recommendations
  - Updated Next Steps with current implementation status (85% complete)
  - Added specific guidance for remaining work (tests, user docs, technical docs)
- **Comprehensive Documentation Accuracy Fixes** - Corrected 10 inaccuracies found in user-facing documentation
  - **Store Items (docs/user-guides/features/store/creating-items.md)**:
    - Fixed tier system documentation to reflect actual implementation (Basic/Standard/Premium/Luxury based on % of CWI, not Tier 1/2/3 with dollar amounts)
    - Corrected default state - items are created as active by default, not inactive
    - Removed non-existent image upload feature documentation
    - Removed non-existent daily purchase limit documentation
    - Updated terminology to match code (Immediate Use/Delayed Use instead of Virtual/Physical)
    - Added missing "Collective Goal" item type to documentation with full explanation
    - Corrected purchase limits documentation to reflect actual behavior (concurrent ownership, not daily limits)
    - Updated scenario examples to use correct field names and remove daily limits
    - Removed confusing "if available" language for collective goals (feature is fully available)
    - Removed misleading "Use images" tip from Tips for Success section (feature doesn't exist)
    - Fixed contradictory troubleshooting text about daily limits (clarified to use inventory and per-student limits)
  - **Payroll (docs/user-guides/features/payroll/running-payroll.md)**:
    - Removed non-existent automatic payroll feature documentation (entire section)
    - Added guidance for manual payroll scheduling and consistency
    - Clarified that break time IS paid (system does not exclude breaks from hours worked)
    - Added Q&A explaining how to handle unpaid breaks if desired
    - Updated all automatic payroll references to reflect manual-only operation
  - **Banking (docs/user-guides/features/banking/transferring-money.md)**:
    - Removed non-existent transfer limits documentation (daily limits, min/max transfer amounts)
    - Simplified to only document actual rules (no negative balances)

### Dependencies
- Bump `requests` from 2.32.4 to 2.32.5
- Bump `markdown` from 3.7 to 3.10
- Bump `webfactory/ssh-agent` from 0.9.0 to 0.9.1

## [1.4.0] - 2025-12-27

### Added
- **Announcement System** - Teachers can create and manage announcements for their class periods
  - Display announcements on student dashboards with dismiss capability
  - Filter announcements by class period
  - Toggle announcement visibility (active/inactive)
  - Create, edit, and delete announcements with rich formatting
  - System admins can create global announcements visible across all classes
  - Announcements link added to admin navigation under Classroom section
- **UI/UX Improvements** - Comprehensive redesign of dashboard and navigation interfaces
  - **Personalized Greetings**:
    - Teacher dashboard displays centered "Hi, [Display Name]" greeting with info icon tooltip linking to settings
    - Student dashboard shows dynamic time-based greeting with first name
    - Mid-day greetings randomize between friendly options: "Howdy", "Good day to you", "Good to see you again", "Great timing", "Let us get started"
    - Morning (5am-12pm): "Good morning"
    - Afternoon (12pm-5pm): Random friendly greeting
    - Evening (5pm-5am): "Good evening"
  - **Enhanced Student Dashboard**:
    - Removed redundant left navigation sidebar for cleaner layout
    - Added side-by-side account balance cards for Checking and Savings accounts
    - Light gray card backgrounds for better visibility
    - Savings account displays projected monthly interest when balance > 0
    - Encouragement message when savings balance is $0 to promote saving habits
    - Fully responsive design (side-by-side on desktop, stacked on mobile)
  - **Accordion-Style Admin Navigation**:
    - Reorganized sidebar navigation into collapsible accordion categories
    - Categories: Classroom, Economy, Bills, Settings
    - Bootstrap accordion ensures only one section open at a time for cleaner interface
    - Consolidated Settings section: Personalization, Passkey, Features, Help & Support
    - Removed non-functional "Mobile Site" link from navigation
    - Custom CSS styling for dark sidebar theme with smooth transitions
  - **Improved Sign Out Button**: Enhanced contrast with red filled button and white text
  - **Streamlined Authentication Flow**:
    - Login forms present two authentication method buttons upfront
    - "Use my authenticator" button reveals TOTP field with Back button
    - "Use my passkey" button triggers WebAuthn flow with automatic fallback to TOTP on failure
    - Applied to both admin and system admin login pages
    - Cleaner, more intuitive authentication experience with proper error handling

### Changed
- **Dependency Updates** - Updated key dependencies for security and stability
  - Updated `click` from 8.1.8 to 8.3.1
  - Updated `beautifulsoup4` from 4.13.4 to 4.14.3
  - Updated `requests` from 2.32.3 to 2.32.4

### Security
- **CodeQL Security Alerts Remediation** - Addressed 62 security alerts identified by CodeQL scanning (#737)
  - **Clear-text Logging of Sensitive Information**:
    - Remove TOTP secret printing from `create_admin.py`, `wsgi.py`, and seed scripts
    - TOTP secrets now encrypted in database with secure access only
    - Prevents TOTP secrets from appearing in logs, console output, or command history
  - **DOM XSS Vulnerabilities**:
    - Fixed `innerHTML` usage in `templates/student_transfer.html`
    - Fixed `innerHTML` usage in `static/js/attendance.js`
    - Replaced with safe DOM manipulation using `createElement` and `textContent`
    - Prevents XSS attacks via user-controlled data
  - **GitHub Actions Workflow Permissions**:
    - Added explicit permissions to `toggle-maintenance.yml`, `check-migrations.yml`, and `deploy.yml`
    - Follows principle of least privilege for workflow security
    - Reduces workflow attack surface
  - **Documentation**: Added `docs/LOGS/AUDITS/SECURITY_FIXES_SUMMARY.md` with complete analysis of all 62 alerts
  - **Summary**: Fixed 23+ real security issues, suppressed 2 false positives, reviewed 37 false positives (already mitigated)
- **Enhanced Open Redirect Protection** - Improved URL validation in student class enrollment redirects
  - Upgraded `_is_safe_url()` function to use same-origin validation
  - Now uses `urljoin()` to resolve relative URLs against application's base URL
  - Validates that redirect targets match the application's scheme and domain
  - Prevents protocol-relative URLs and external redirects
  - Added explicit security annotations (`# nosec`) with justification at all redirect points
  - Addresses all 9 CodeQL security scanner findings for URL redirection vulnerabilities
  - Affects student add-class flow redirect handling (`app/routes/student.py:710-877`)

### Fixed
- **Teacher Invite Code Validation** - Fixed critical bugs preventing teacher signup with invite codes (#738)
  - **Whitespace Handling**: Strip whitespace from invite codes during creation and validation
  - **Timezone Comparison Error**: Fixed TypeError when comparing invite code expiration dates (timezone-aware vs timezone-naive datetimes)
  - **TOTP Form Validation**: Properly handle TOTP confirmation form submission separate from initial signup form
  - **Form Field Population**: Use AdminTOTPConfirmForm for TOTP submissions instead of AdminSignupForm
  - **Date String Handling**: Pass date string instead of integer for dob_sum field in TOTP confirmation
  - Added comprehensive debug logging for invite code creation and validation
  - Added cleanup script (`cleanup_invite_codes.py`) for existing codes with whitespace
  - Ensures consistency between invite code creation and validation across system admin and CLI tools
- **TOTP Setup UI** - Updated TOTP setup page to match new brand theme
  - Replaced hardcoded colors with CSS variables (--primary, --secondary, etc.)
  - Updated gradient and logo to match refreshed brand
  - Added pattern background to match signup page design
  - Improved button hover states for consistency
- **Onboarding Templates** - Updated color scheme and text for better consistency with new brand theme
- **Admin Dashboard**: Removed duplicate greeting that was appearing in both page header and content section
- **Student Dashboard**: Improved account balance cards with clearer styling using light backgrounds instead of semi-transparent overlays for better readability
- **Mobile Responsiveness**: Enhanced responsive behavior with proper Bootstrap column classes (col-12 col-md-6)
- **Grafana Access Issue** - Fixed "connection refused" error when accessing Grafana from system admin dashboard
  - **Root Cause**: Nginx `proxy_pass` had trailing slash that stripped URL path, causing infinite redirects
  - **Dual-Layer Solution** for maximum reliability:
    - **Flask Proxy (Fallback)**: Added `/sysadmin/grafana` route that proxies to Grafana service
      - Works immediately without Nginx configuration changes
      - Maintains system admin authentication via `@system_admin_required`
      - Configurable via `GRAFANA_URL` environment variable (defaults to `http://localhost:3000`)
      - Rate-limit exempt for smooth dashboard operation
      - Graceful error handling with user-friendly messages
      - Added `requests==2.32.3` dependency
    - **Nginx Fix (Production)**: Corrected configuration provided in `nginx-grafana-fix.conf`
      - Remove trailing slash from `proxy_pass http://127.0.0.1:3000/` → `proxy_pass http://127.0.0.1:3000`
      - Nginx intercepts requests before Flask (faster performance)
      - Auto-fallback to Flask proxy if Nginx not configured
  - See `GRAFANA_FIX_GUIDE.md` for detailed implementation guide

## [1.3.0] - 2025-12-25

### Added
- **Passwordless Authentication for Teachers** - Implemented WebAuthn/FIDO2 passkey authentication for teacher admins
  - Supports hardware security keys (YubiKey, Google Titan Key, etc.)
  - Supports platform authenticators (Touch ID, Face ID, Windows Hello)
  - Supports synced passkeys across devices
  - Phishing-resistant authentication (domain-bound credentials)
  - New `/admin/passkey/settings` page for passkey management
  - Backend routes for passkey registration and authentication
  - Database model `AdminCredential` for storing passkey metadata
  - TOTP authentication remains available as backup option
  - Full CSRF protection and rate limiting on all passkey endpoints
  - Passkey settings link added to teacher navigation sidebar
- **Passwordless Authentication for System Admins** - Implemented WebAuthn/FIDO2 passkey authentication using passwordless.dev
  - Supports hardware security keys (YubiKey, Google Titan Key, etc.)
  - Supports platform authenticators (Touch ID, Face ID, Windows Hello)
  - Supports synced passkeys across devices
  - Phishing-resistant authentication (domain-bound credentials)
  - New `/sysadmin/passkey/settings` page for passkey management
  - Backend routes for passkey registration and authentication
  - Frontend integration with passwordless.dev JavaScript SDK
  - Database model `SystemAdminCredential` for storing passkey metadata
  - TOTP authentication remains available alongside passkeys
  - Self-hosted ready: Infrastructure supports future migration to py-webauthn library
  - Requires environment variables: `PASSWORDLESS_API_KEY`, `PASSWORDLESS_API_PUBLIC`
  - Full CSRF protection and rate limiting on all passkey endpoints
  - Tracks credential usage timestamps for security auditing
  - Uses official Bitwarden Passwordless SDK (`passwordless==2.0.0`) for type-safe API interactions
- **Security Remediation Tools and Documentation** - Complete implementation guides and fixed workflow files
  - Step-by-step remediation guide: `docs/security/SECURITY_REMEDIATION_GUIDE.md`
  - Fixed workflow files with SSH host key verification: `.github/workflows/*.FIXED`
  - Automated SSH security setup script: `scripts/setup-ssh-security.sh`
  - Includes fixes for: SSH MITM vulnerability, secrets management hardening, dependency updates
  - Ready-to-use workflow files with improved security posture

### Security
- **Encrypted TOTP Secrets at Rest** - TOTP 2FA secrets now encrypted in database using Fernet (AES-128-CBC)
  - Added `encrypt_totp()` and `decrypt_totp()` helper functions in `app/utils/encryption.py`
  - All new admin/system admin accounts store encrypted TOTP secrets (base64-encoded)
  - Backward compatible: `decrypt_totp()` handles both encrypted and legacy plaintext secrets transparently
  - **MIGRATION REQUIRED**: Column length expanded from VARCHAR(32) to VARCHAR(200) - See `docs/LOGS/AUDITS/MIGRATION_TOTP_ENCRYPTION.md`
  - Defense in depth: Database compromise alone no longer sufficient to generate valid 2FA codes
  - **Note:** Still requires `ENCRYPTION_KEY` security - future migration to AWS Secrets Manager/Vault recommended
  - Files changed: `app/utils/encryption.py`, `app/models.py`, `app/routes/admin.py`, `app/routes/system_admin.py`, `wsgi.py`, `create_admin.py`
- **Removed Sensitive Information from Application Logs** - Eliminated logging of usernames, hashes, and PII
  - Removed username logging from student login, admin login, admin signup, and admin recovery flows
  - Removed partial hash logging from student authentication
  - Removed student name and DOB sum logging from bulk upload process
  - Impact: Prevents accidental exposure of PII in development logs, log files, or screenshots
  - Note: Production deployments should configure `LOG_LEVEL=WARNING` or higher to minimize log output
- **CRITICAL: Fixed PromptPwnd AI Prompt Injection Vulnerability** - Disabled vulnerable `summary.yml` GitHub Actions workflow
  - Workflow used AI inference (`actions/ai-inference@v1`) with untrusted user input from issue titles/bodies
  - Attack vector: Any user could create an issue with malicious prompt injection to leak `GITHUB_TOKEN` or manipulate workflows
  - Remediation: Disabled workflow by renaming to `summary.yml.DISABLED`
  - Impact: No exploitation detected - vulnerability fixed proactively
  - Documentation: See `docs/security/PROMPTPWND_REMEDIATION.md` for full details
  - Reference: [Aikido Security PromptPwnd Disclosure](https://www.aikido.dev/blog/promptpwnd-ai-prompt-injection-in-github-actions) (December 2025)
- **Comprehensive Attack Surface Security Audit Completed** - Full security review of codebase, CI/CD, and infrastructure
  - Audited: GitHub Actions workflows, authentication, authorization, encryption, multi-tenancy, dependencies, and API security
  - Findings: 16 total findings (2 critical, 2 high, 3 medium, 4 low, 5 informational)
  - Critical issues: AI prompt injection (fixed), SSH host key verification disabled (open)
  - Strengths: Excellent CSRF protection, SQL injection prevention, XSS mitigation, PII encryption, multi-tenancy isolation
  - Recommendations: Enable SSH host key verification, update cryptography package, improve secrets management
  - Documentation: See `docs/security/COMPREHENSIVE_ATTACK_SURFACE_AUDIT_2025.md` for complete report

## [1.2.1] - 2025-12-21

### Added
- **Comprehensive Legacy Account Migration Script** - Complete migration tool for transitioning all legacy accounts to new multi-tenancy system
  - Migrates students with `teacher_id` to claim-based enrollment system
  - Creates missing `StudentTeacher` associations and `TeacherBlock` entries
  - Backfills `join_code` for all TeacherBlock entries
  - Backfills `join_code` for transactions, tap events, and related tables with proper multi-tenancy isolation
  - **FIXED:** Transaction backfill now matches on BOTH `student_id` AND `teacher_id` to ensure correct period assignment for students in multiple periods with same teacher
  - **FIXED:** Block names normalized to uppercase for consistency across database
  - **OPTIMIZED:** Phase 5 backfill uses CTE with `DISTINCT ON` instead of correlated subqueries for significantly better performance on large datasets
  - Includes dry-run mode for safe preview before applying changes
  - Provides comprehensive verification and error reporting
  - Located at: `scripts/comprehensive_legacy_migration.py`
- **Comprehensive Test Suite for Legacy Migration** - Full test coverage for migration script
  - Tests all 5 migration phases including Phase 5 (related tables backfill)
  - Tests critical multi-period student scenarios
  - Tests idempotency and error handling
  - Tests block casing normalization
  - Tests rollback on errors
  - Tests CTE performance optimization for Phase 5
  - Tests tables with and without period columns
  - Located at: `tests/test_comprehensive_legacy_migration.py`
- **Legacy Account Migration Documentation** - Complete guide for migration process
  - Historical context and migration strategy
  - Step-by-step deployment instructions
  - Troubleshooting common issues
  - Post-migration verification procedures
  - Roadmap for deprecating `teacher_id` column
  - Located at: `docs/operations/LEGACY_ACCOUNT_MIGRATION.md`
- **Join Code Schema Audit Tool** - `scripts/inspect_join_code_columns.py` lists which tables have or are missing `join_code` to support multi-tenancy audits
- **StudentBlock Join Code Migration** - Added idempotent migration (`a1b2c3d4e5f8`) to create `join_code` column and index on `student_blocks`, with safeguards for partially applied schemas

### Changed
- Preparing for final deprecation of `teacher_id`-based linkage system
- All legacy data now ready for migration to `join_code`-based multi-tenancy
- Hardened migration best practices documentation for avoiding duplicate-column errors in `student_blocks` hotfix scenarios
- Refreshed maintenance page copy and styling for clearer outage messaging

### Fixed
- Closed multi-tenancy gaps by adding `join_code` propagation to overdraft fees, bonus/bulk payroll postings, insurance reimbursements, manual payments, and bug-report rewards
- Improved bonus join_code lookup performance to reduce N+1 queries during mass payouts

## [1.2.0] - 2025-12-18

### Added
- **Progressive Web App (PWA) Support** - Full PWA implementation for improved mobile experience
  - Web app manifest with app metadata and icon configuration
  - Service worker with intelligent caching strategies (cache-first for static assets, network-first for CDN resources)
  - Offline fallback page with user-friendly offline experience
  - PWA installation capability on mobile devices (Add to Home Screen)
  - Multi-tenancy-safe caching that excludes authenticated routes
  - Automatic cache cleanup and version management
- **Mobile Experience Enhancements** - Dedicated mobile templates for student portal with responsive navigation and improved touch targets
- **Accessibility Improvements** - Enhancements following WCAG 2.1 AA guidelines
  - Added ARIA labels to mobile navigation and interactive elements
  - Improved keyboard navigation support
  - Enhanced screen reader compatibility
  - Better color contrast ratios
- **UI Documentation** - Added `docs/PWA_ICON_REQUIREMENTS.md` and `TEMPLATE_REDESIGN_RECOMMENDATIONS.md`
  - PWA icon asset generation instructions
  - UI redesign patterns and guidelines
  - Best practices for accordion/collapsible patterns
  - Color scheme guidelines for consistent visual hierarchy

### Changed
- **Attendance Terminology** - Renamed "Tap In/Out" to "Start Work/Break Done" for clarity
  - Updated user-facing text throughout student portal
  - Updated frontend API actions and documentation
  - Maintained backward compatibility in database actions
- **Admin UI Redesigns** - Modernized admin templates with collapsible accordion sections
  - **Insurance Policy Edit Page** - Eliminated overflow issues with progressive disclosure layout
  - **Store Item Edit Page** - Reduced scrolling with accordion sections for Bundle, Bulk Discount, and Advanced settings
  - **Rent Settings Page** - Better organization with collapsible sections
  - **Feature Settings** - Simplified to single-column, collapsible cards
  - Added visual "Active" badges to accordion headers indicating when sections have configured settings
- **Mobile Dashboard** - Simplified single-column layout with attendance card and tap buttons
- **Mobile Store** - Improved item list layout with larger purchase buttons
- **Theme Consistency** - Aligned mobile templates with main application theme colors

### Fixed
- **Critical: Multi-Tenancy Payroll Bug** - Fixed payroll calculations leaking data across class periods (#664)
  - Ensured all payroll queries properly scoped by join_code
  - Added multi-tenancy tests for payroll system
- **Payroll JSON Error** - Fixed "Run Payroll Now" button returning HTML instead of JSON (#668)
  - Resolved "Unexpected token '<!DOCTYPE'" error
  - Properly returns JSON response for AJAX requests
- **Timezone Handling** - Fixed timezone comparison error in payroll calculation (#666)
  - Corrected UTC normalization for payroll scheduling
  - Fixed edge cases with daylight saving time transitions
- **PWA Icon Rendering** - Fixed Material Symbols icons not loading in PWA mode (#672, #676)
  - Root cause: Service Worker intercepting Google Fonts with incorrect caching strategy
  - Solution: Service Worker now bypasses Google Fonts, letting browser handle natively
  - Added font preload and fallback CSS for Material Symbols
- **Mobile PWA Navigation** - Restored icons and removed horizontal scrolling (#674)
  - Tightened bottom navigation layout for small screens
  - Added overflow-x protection and responsive media queries
- **Desktop PWA Rendering** - Added PWA support to desktop templates for mobile viewing (#675)
  - Added PWA meta tags (theme-color, apple-mobile-web-app-capable)
  - Added mobile bottom navigation when sidebar is hidden
- **Auto Tap-Out Regression** - Fixed test failures due to missing teacher_id context in auto tap-out logic (#670)

### Technical
- Service worker cache bumped to v5 to force updates
- Added comprehensive multi-tenancy tests for payroll
- Improved mobile responsiveness across all admin templates
- Enhanced documentation organization and clarity

## [1.1.1] - 2025-12-15

### Fixed
- Secured teacher recovery verification by hashing date-of-birth sums and migrating existing records to the new salted hash format (#637)
- Hardened student login redirects and UTC-normalized dashboard earnings/spending calculations to prevent redirect abuse and negative totals (#638)
- Applied the green theme to standalone admin/auth pages and corrected admin heading hierarchy to resolve styling regressions (#635, #639)
- Added cache-busting static asset helper defaults and fallback coverage to stop `static_url` undefined errors across templates (#628-633)
- Stopped insurance management and edit screens from crashing when legacy forms lack the tier grouping field (#640)
- Added one-time prompt for legacy insurance policies and supporting script to encourage migration to tiered plans (#641)

## [1.1.0] - 2024-12-13

### Added
- **Student Analytics Dashboard** - Weekly statistics showing days tapped in, minutes attended, earnings, and spending
- **Savings Projection Graph** - Interactive 12-month visualization of savings growth on bank page using Chart.js
- **Long-Term Goal Items** - Option to mark store items that should be exempt from CWI balance checks (for expensive class rewards)
- **Enhanced Economy Health Warnings** - Specific recommended ranges and actionable guidance for all economy settings
- **Weekly Analytics Calculations** - Backend logic to calculate unique days tapped, total minutes, and transaction summaries
- **Savings Projection Algorithm** - Respects simple/compound interest and compounding frequency settings

### Changed
- **Complete UI Redesign** - Modern interface with softer colors, improved navigation, and better layout
- **Color Scheme** - Reduced brightness and contrast for better eye comfort (primary: #1a4d47, secondary: #d4a574)
- **Student Dashboard Layout** - Added sticky left sidebar navigation for quick access to all features
- **Economy Health Messages** - Improved warnings with absolute values and specific dollar recommendations
- **Tab Navigation** - Fixed CSS scoping to restore visibility across 15+ multi-tab pages

### Fixed
- **Critical: Restored Pending Actions section** on admin dashboard (store approvals, hall passes, insurance claims were missing)
- **Critical: Fixed invisible tabs** on Student Management, Store Management, and other multi-tab pages
- **Fixed missing navigation links** on login screens (account setup, recovery, privacy/terms)
- **Fixed CSS scoping issue** where `.nav-link` styles were applied globally instead of scoped to sidebar
- **Added missing Bootstrap Icons CSS** imports to admin and student layouts
- **Added missing utility classes** (`.btn-white`, `.icon-circle`) for redesigned UI

### Technical
- Database migration `a7b8c9d0e1f2` adds `is_long_term_goal` column to `store_items` table
- Updated `economy_balance.py` to skip long-term goal items in CWI validation
- Added Chart.js (v4.4.0) for savings projection visualization
- Improved query performance for weekly analytics calculations
- Updated forms.py with `is_long_term_goal` BooleanField

## [1.0.0] - 2024-11-29

### Milestone
First stable release of Classroom Token Hub! All critical security issues resolved and production-ready.

## [Unreleased] - Version 0.9.0 (Pre-1.0 Candidate)

### Project Status
The project is ready for version 1.0 release. All critical blockers have been resolved:
- ✅ **P0 Critical Data Leak:** Fixed and deployed (2025-11-29) - See [docs/security/CRITICAL_SAME_TEACHER_LEAK.md](docs/SECURITY/INCIDENTS/SEC-INC-013_Critical_Same_Teacher_Leak.md)
- ✅ **P1 Deprecated Patterns:** All updated to Python 3.12+ and SQLAlchemy 2.0+ (2025-12-06)
- 🔄 **Backfill:** Legacy transaction data being backfilled with interactive verification

### Added (2025-12-11)
- **DEVELOPMENT.md** — Unified development priorities document consolidating all TODO files and roadmap
- **docs/technical-reference/economy-specification.md** — Financial system specification (moved from root)
- **docs/development/ECONOMY_BALANCE_CHECKER.md** — CWI implementation guide (moved from root)

### Changed (2025-12-11)
- **Major documentation consolidation:**
  - Merged `DEVELOPMENT.md`, `docs/development/MULTI_TENANCY_TODO.md`, and `ROADMAP_TO_1.0.md` into single `DEVELOPMENT.md`
  - Updated all references to point to new unified documentation structure
  - Updated README.md to reflect v1.0 readiness (all critical blockers resolved)
  - Moved implementation reports to `docs/LOGS/AUDITS/` for historical reference
- **Security documentation updates:**
  - Updated `CRITICAL_SAME_TEACHER_LEAK.md` status to RESOLVED (deployed with backfill in progress)
  - Updated `docs/README.md` to remove "P0 BLOCKER" label

### Removed (2025-12-11)
- `DEVELOPMENT.md` — Consolidated into DEVELOPMENT.md
- `docs/development/MULTI_TENANCY_TODO.md` — Consolidated into DEVELOPMENT.md
- `docs/development/TECHNICAL_DEBT_ISSUES.md` — Superseded by DEPRECATED_CODE_PATTERNS.md
- `ROADMAP_TO_1.0.md` — Consolidated into DEVELOPMENT.md

### Added (2025-12-04)
- **PROJECT_HISTORY.md** — Comprehensive document capturing project philosophy, evolution, and key milestones
- **docs/development/DEPRECATED_CODE_PATTERNS.md** — Technical debt tracking for Python 3.12+ and SQLAlchemy 2.0+ compatibility
- Documentation index updated with new security and archive sections

### Changed (2025-12-04)
- **Major documentation reorganization:**
  - Moved security audits to `docs/security/` (CRITICAL_SAME_TEACHER_LEAK.md, MULTI_TENANCY_AUDIT.md)
  - Moved development guides to `docs/development/` (JULES_SETUP.md, SEEDING_INSTRUCTIONS.md, TESTING_SUMMARY.md, MIGRATION_STATUS_REPORT.md)
  - Moved operations docs to `docs/operations/` (MULTI_TENANCY_FIX_DEPLOYMENT.md)
  - Archived historical fix summaries to `docs/LOGS/AUDITS/` (FIXES_SUMMARY.md, JOIN_CODE_FIX_SUMMARY.md, MIGRATION_FIX_SUMMARY.md, STAGING_MIGRATION_FIX.md)
- Updated `docs/README.md` with comprehensive documentation map including security and archive sections
- Updated main README with version 0.9.0 status and platform-agnostic deployment language
- Removed hardcoded IP addresses from GitHub Actions workflows (now use `secrets.PRODUCTION_SERVER_IP`)

### Removed (2025-12-04)
- **scripts/cleanup_duplicates.py** — Obsolete duplicate cleanup script (superseded by cleanup_duplicates_flask.py)
- Debug print statement in `app/routes/api.py:1198` (replaced with proper logging)

### Fixed (2025-12-04)
- Security: Removed hardcoded production server IP from CI/CD workflows

### Fixed (2025-12-05)
- Student portal: Removed the non-functional class switch button from the class banner and eliminated hover animations to reduce UI confusion.
- Student portal: Scoped payroll attendance and projection data to the currently selected class so multi-class students only see the active class statistics.

### Previous Changes
- Continued repository organization and documentation cleanup
- Moved `PULSETIC_SETUP.md` to `docs/operations/` for better organization
- Moved additional PR-specific reports to `docs/LOGS/AUDITS/pr-reports/`
- Updated `docs/operations/README.md` with comprehensive guide listings
- Added migration to align `rent_settings` schema with application model by including the `block` column
- Added migration to bring the `banking_settings` table in sync with the model by introducing the missing `block` column

---

## [2025-11-25] - Maintenance & Bypass Enhancements

### Added
- Persistent maintenance mode across deploys (`deploy_updates.sh`) with `--end-maintenance` explicit exit flag
- System admin and token-based maintenance bypass with session persistence (`maintenance_global_bypass`)
- System admin login access during maintenance (`/sysadmin/login`) and login link on `maintenance.html`
- Badge icon/text server-side mapping and status description rendering fallback when JS disabled
- Documentation for maintenance variables and operational workflow (see `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md`)

### Changed
- `deploy_updates.sh` now detects existing maintenance state instead of resetting it
- Bypass logic promotes valid sysadmin/token to global session for teacher/student role testing
- Tests expanded for bypass persistence and login accessibility

### Security
- Bypass token now stored only in environment and session flag; recommends rotation post-window

## [2025-11-24] - Repository Housekeeping

### Added
- Archive directory for historical PR reports (`docs/LOGS/AUDITS/pr-reports/`)
- README documentation for scripts directory
- README documentation for archived PR reports
- CLI command `normalize-claim-credentials` to backfill student and roster claim hashes to the canonical format

### Changed
- Moved utility scripts to `scripts/` directory for better organization:
  - `check_migration.py`
  - `check_orphaned_insurance.py`
  - `cleanup_duplicates.py`
  - `cleanup_duplicates_flask.py`
- Updated script references in documentation to reflect new paths
- Removed hardcoded paths from `check_orphaned_insurance.py`
- Repository housekeeping: organized files, removed obsolete files, and updated documentation
- Improved repository structure for better maintainability and navigation

### Removed
- Duplicate file: `SECURITY_AUDIT_INSURANCE_OVERHAUL (1).md`
- Moved PR-specific reports to archive (no longer in root):
  - `PR_DESCRIPTION.md`
  - `PR_DESCRIPTION_SECURITY_FIXES.md`
  - `CODE_REVIEW_SECURITY_FIXES.md`
  - `CODE_REVIEW_TECHNICAL_ANALYSIS.md`
  - `FINAL_CODE_REVIEW_SUMMARY.md`
  - `MIGRATION_REPORT_STAGING.md`
  - `REGRESSION_TEST_REPORT_STAGING.md`
  - `SECURITY_FIXES_CONSOLIDATED.md`
  - `SECURITY_FIX_VERIFICATION.md`
  - `SECURITY_FIX_VERIFICATION_UPDATED.md`
  - `SECURITY_AUDIT_INSURANCE_OVERHAUL.md`
  - `PRODUCTION_DEPLOYMENT_INSTRUCTIONS.md`

## [2025-11-20] - Feature Updates

### Added
- Align tap projected pay with payroll settings (#235)
- Simple vs compound interest options with configurable frequency (#233)

### Fixed
- Savings rate input validation error for hidden fields (#231)
- Normalize tap event actions for payroll counts (#230)
- Hall pass network errors and missing status updates (#229)
- Student template redesign to match admin layout (#225, #227)

## [2025-11-19] - Architecture Refactor

### Added
- Comprehensive system architecture documentation
- System admin portal with error logging
- Custom error pages for all major HTTP errors
- GitHub Actions CI/CD to DigitalOcean

### Changed
- Refactored monolithic app.py to modular blueprint architecture

---

## Documentation Maintenance

This changelog tracks significant changes to the codebase. For:
- **Current development tasks**: See [DEVELOPMENT.md](DEVELOPMENT.md)
- **Planned features**: See [DEVELOPMENT.md](DEVELOPMENT.md) Roadmap section
- **Technical details**: See [docs/technical-reference/architecture.md](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)

## Changelog Guidelines

When adding entries:
- Group changes by type: Added, Changed, Deprecated, Removed, Fixed, Security
- Reference PR/issue numbers where applicable
- Use present tense for entries
- Keep entries concise but informative
- Update the date when moving Unreleased to a version
- For any PR touching templates, shared UI shells/components, template CSS, or template-driven JS, record accessibility issues found and accessibility fixes made

**Last Updated:** 2026-01-09
