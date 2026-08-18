# DOM-ECON Archaeology (2026-08-16)

| Field | Value |
|---|---|
| Type | Investigation / History Reconstruction |
| Status | Descriptive — not doctrine |
| Branch | `codex/v2.0` |
| Reference Commit | `dc5e0efb` |

## 0. Correction Note (added 2026-08-16, post-review)

The original investigation missed `docs/SPEC/SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md`, which derives its authority from `DOM-CLASS-001 / 002 / 003` and is the modern successor authority for most of the "stranded" formulas catalogued in §IV and §V. Findings below are preserved as archaeological evidence; the following rows have since been resolved:

- **§V.1 CWI derivation** — restored under SPEC-ECON-003 §4.1 (verbatim formula).
- **§V.2 Per-mode weekly savings target** — restored under SPEC-ECON-003 §4.2 and §8.
- **§V.3 Per-mode rent/utilities/insurance/fine/store ratios** — restored under SPEC-ECON-003 §4.3–§4.8 and §8. Store tier reference table matches the "unattributed default" flagged in §VI.11.
- **§V.4 Collective goal scaling** — pricing bands restored under SPEC-ECON-003 §4.7. Mechanic ownership: STORE domain.
- **§V.5–§V.6 Savings compound growth + daily accrual** — restored under SPEC-ECON-003 §5.3, §5.5.
- **§V.7 Doubling-time constraint** — restored under SPEC-ECON-003 §5.2 (table) and §5.4 (rearrangement).
- **§V.12 Deterministic calculation requirement** — restored under SPEC-ECON-003 §7.3.
- **§IV.1 Solvency Preservation Principle** — *partially* covered by SPEC-ECON-003 §7.1 coherence intent; the DOM-ECON-000-named principle is not restated by name. Naming/citation gap, not doctrine gap.
- **Labor Dominance** (implicit in §IV.1 of DOM-ECON-000, tied to `passive_income_ratio`) — restored under SPEC-ECON-003 §7.1: *"interest must reward savings without overtaking labor as the dominant money source."*

Still genuinely open after this correction: **§IV.3 Catastrophe Stability Rule** (no SPEC-ECON-003 coverage), **§V.9 same**, **§IV.8 `variable_monetary_risk_factor`** (orphan), the ambiguous ITR-vs-CLASS split for **§IV.9 analytics thresholds** and **§IV.10 view-model thresholds**, and the persistence / temporal / axis questions in §VI.6–§VI.10.

Also: `docs/technical-reference/analytics-specification.md` (§IV.12) remains a dangling reference — SPEC-ECON-003 is not its successor for the analytics side.

## I. Scope

This document reconstructs the history of the "Economic Engine" / "Economic Policy" concept in the CTH codebase, from its original monolithic form (`DOM-ECON-000`) through the "ECON → CLASS" split that moved economic *configuration* authority into `DOM-CLASS-002` / `DOM-CLASS-003` while leaving economic *interpretation* nominally under `DOM-ITR-001`. It is a history reconstruction only. It writes no doctrine, makes no normative claims, and is not authoritative for anything. Its purpose is to give the author of `SPEC-ITR-001` (and reviewers of the current Interpretation Domain) visibility into (a) formulas and semantics that still live in code without a clear owning doctrine, (b) doctrine language that never landed in code, and (c) concepts that were named in constitutional docs, then dropped without a stated successor.

## II. Timeline

Dates are from `git log --date=short`.

| Date | Commit | Event |
|---|---|---|
| 2026-01-06 | `7a21f7a4` | Analytics feature landed (PR #807). Creates `app/utils/analytics_engine.py` with `AnalyticsEngine`, `SystemHealthMetrics`, `TrendMetrics`, and metric implementations for participation, money velocity, CWI deviation, and budget survival pass rate. Docstring points to `docs/technical-reference/analytics-specification.md`. |
| 2026-03-01 | `26f60578` | `docs/technical-reference/analytics-specification.md` deleted as part of "add foundational architectural and operational documentation". `analytics_engine.py`'s module docstring reference becomes dangling from this date forward. |
| 2026-03-07 / 2026-03-08 | `589d6ba7`, `6bb0733a` | `app/utils/economy_policy.py` created. Introduces `POLICY_MODES` (`tight` / `default` / `comfortable`), ratio bands for rent/utilities/insurance/fine/store tiers, `get_price_recommendation_context()`, and rebalancer helpers. |
| 2026-04-22 | (see 60471b6e path) | `DOM-ITR-001` (Interpretation Domain) authored at v1.1 with Behavioral / Structural axes. |
| 2026-04-23 | `60471b6e` | Domain documentation structure standardized; `DOM-ITR-001` added to `docs/DOMAIN/`. |
| 2026-06-14 | `da40d77d` | Docs reorganized for v2 default branch. `DOM-ECON-000_ECONOMY_GOVERNANCE_FOUNDATION.md`, `DOM-ECON-003_ECONOMIC_POLICY_AND_TRANSITION.md`, and `DOM-ITR-001` all touched. `DOM-ECON-000` still present at this point (v1.1, effective 2026-06-08). |
| 2026-07-11 / 2026-07-12 | `68e08abe`, `8901bdc7` | v2 canonical migration waves. Multiple economy-adjacent files touched. |
| 2026-07-14 | `99b217d5` | Cleanup pass in v2. |
| 2026-08-07 | `05498b52` / `0509b425` | Analytics domain view models introduced. Creates `app/services/analytics/builders.py` with `MetricSnapshotView`, `AnalyticsDashboardView`, `build_analytics_dashboard_view()`. Establishes the view-model boundary between `analytics_engine.py` (computation) and templates (display). |
| 2026-08-08 | `251b0693` | `feature_settings` renamed to `economic-engine` for clarity (schema/doc rename). |
| 2026-08-08 | `abb49d75` | **PR #1321 "establish class configuration domain foundations."** This is the ECON→CLASS boundary event. In one commit: `DOM-ECON-000_ECONOMY_GOVERNANCE_FOUNDATION.md` (819 lines) is **deleted**; `DOM-ECON-003_ECONOMIC_POLICY_AND_TRANSITION.md` is **renamed** to `DOM-CLASS-003_ECONOMIC_POLICY.md`; `DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md` is **created** (91 lines); `DOM-CLASS-001` gets 54 lines added. `SPEC-ECON-001` / `SPEC-ECON-002` renamed/updated. No successor doc is created for the analytics, solvency, or CWI-derivation content that lived in `DOM-ECON-000`. |
| 2026-08-08 | `d0c8b371` | Phase 2 persistence layer. `EconomicEngine` model materialized as versioned, immutable rows; `ClassFeature` composite PK `(class_id, feature, effective_at)`. |
| 2026-08-08 | `1d0d6934` | Phase C & D: consumer migration from `FeatureSettings` to `ClassFeature` / `EconomicEngine`. |
| 2026-08-08 | `a7b8141e` | `expected_weekly_hours` moved from `PayrollSettings` to `EconomicEngine`. This makes CWI derivation partially depend on `EconomicEngine` (rate on PayrollSettings, hours on EconomicEngine). |
| 2026-08-08 | `ebff5767` / `55d652a3` | `ClassEconomy.user_id` → `teacher_user_id` completion. |
| 2026-08-16 | `dc5e0efb` (HEAD) | Current WIP: FEAT context correction full sweep. |

Two files bracket the ECON→CLASS boundary and never received matching updates:
- `app/utils/analytics_engine.py` — module docstring still references a spec deleted five months prior; still comments "per DOM-CLASS-002 and economy policy modes" without pointing to a specific section.
- `app/utils/economy_policy.py` — comment still points to `docs/DOMAIN/DOM-CLASS-003_ECONOMIC_POLICY.md` and `docs/FEATURES/ECONOMY/FEAT-ECON-001_Policy_Mode_and_Rebalancer.md` (the second path is under a non-existent directory tree — the current FEAT layout is `docs/FEATURE-EXECUTION/`).

## III. Surviving Artifacts

### `app/utils/analytics_engine.py` (638 lines)

What it does now:
- Exposes `AnalyticsEngine(class_id)` bound to a single class.
- Computes: participation rate, money velocity, CWI deviation distribution, budget survival pass rate.
- Computes trend direction (`increasing` / `stable` / `decreasing`) with a 10% threshold.
- Emits alerts (`participation_low`, `cwi_deviation`, `velocity_drop`, `budget_survival_low`).
- Returns an in-memory `AnalyticsWindowView` snapshot via `create_snapshot()`, `get_or_create_snapshot()`, `get_snapshot_read_only()`.
- The mutating entry point (`create_snapshot`) is guarded by `@requires_feat_context("FEAT-ANLY-001")`.

Owning doctrine in current tree: none named directly. The nearest constitutional home is `DOM-ITR-001` (Interpretation Domain), which enumerates "participation rate, money velocity" as Behavioral examples and "affordability ranges, budget pressure" as Structural examples — the code mixes both.

Match with authority: partial. Code is nominally Interpretation, but:
- CWI-band width (`0.20`) comes from `ANALYTICS_POLICY_DEFAULTS` in `economy_policy.py`, i.e., from Class Configuration authority reached into an Interpretation module.
- Budget survival pass rate uses `policy_profile["ratios"]["savings_weekly"]["min"]` — reading Class Configuration policy semantics inside an Interpretation compute path.
- FEAT registration (`app/feats/base.py:121`) labels domain as `"Analytics"`. The word "Analytics" is not a canonical domain in the current DOM inventory.

### `app/utils/economy_policy.py` (680 lines)

What it does now:
- Declares `POLICY_MODES` (`tight` / `default` / `comfortable`) with per-mode ratio bands for `rent_weekly`, `utilities_weekly`, `insurance_weekly`, `insurance_coverage_multiplier`, `insurance_period_cap_multiplier`, `insurance_waiting_period_days`, `fine_weekly`, `store_tiers`, `savings_weekly`, plus per-mode `insurance_transaction_defaults` and `analytics` block (via `ANALYTICS_POLICY_DEFAULTS`).
- `get_price_recommendation_context(mode, cwi)` — central price recommendation.
- `get_insurance_premium_recommendation`, `get_transaction_tier_defaults`, `get_recommended_insurance_weekly_premium`.
- `get_variable_monetary_risk_factor(mode)` — returns a per-mode risk factor (`0.20 / 0.15 / 0.12`).
- Class-scope resolution helpers (`resolve_class_scope`, `resolve_feature_class`, `get_class_feature_settings`).
- `replace_enabled_class_features(class_id, enabled_features)` — mutates `class_features` timeline; ensures payroll is always enabled.
- `get_active_policy_mode_for_class(class_id)` — reads latest `EconomicEngine` row for that class.
- `get_analytics_policy(mode)` — returns per-mode analytics thresholds (`cwi_deviation_band`, `cwi_deviation_warning_threshold`, `velocity_drop_warning_threshold`, `participation_warning_threshold`).

Owning doctrine: `DOM-CLASS-003_ECONOMIC_POLICY.md` (v2.1). The doctrine declares policy versions immutable; the code path `replace_enabled_class_features` appends `ClassFeature` rows without materializing a new `EconomicEngine` version, and reuses the current `economic_version_id`. Whether that satisfies `ECON-CONST-001` (append-only evolution) is not obvious from the doctrine text.

Match with authority: mostly. The one place where authority is ambiguous is `ANALYTICS_POLICY_DEFAULTS` + `get_analytics_policy()` — these are analytics thresholds (a semantic concern) living inside the policy-mode dictionary (a Class Configuration surface). See §VI question 5.

### `app/models.py::EconomicEngine` (lines 361-410)

Materializes the append-only, versioned economics config table (`economic_engine`). Primary key: `economic_version_id` (UUID). Columns include `expected_weekly_hours`, `interest_rate` and full interest configuration group, `economy_policy_mode`. Composite unique on `(class_id, economic_version_id)`. Composite FK for `previous_version_id` chained to same class. CHECK constraint restricts `economy_policy_mode` to `{tight, default, comfortable}`.

Owning doctrine: `DOM-CLASS-001` (owns the `economic-engine` table per `DOM-CLASS-002.V`) and `DOM-CLASS-003` (owns policy lineage semantics). Match: aligned.

### `app/models.py::ClassFeature` (~ line 1552)

Composite PK `(class_id, feature, effective_at)`. Column `economic_version_id` (nullable → disabled). Rows are append-only. `enabled_names_for_class(class_id)` derives the current enabled set.

Owning doctrine: `DOM-CLASS-001`. Match: aligned.

### `app/utils/economy_balance.py` (1356 lines)

What it does now: `EconomyBalanceChecker`. Holds:
- CWI calculation (`calculate_cwi`) — currently the only implementation of the DOM-ECON-000 canonical CWI formula.
- Rent / insurance / fines / store-item balance checks against policy-mode ratio bands.
- `calculate_budget_survival(cwi, rent_settings, insurance_policies, average_store_spending)` — this is the DOM-ECON-000 "Budget Survival Test" formula: `weekly_savings = CWI − rent − insurance − average_store_cost`; passes if `>= min_savings_ratio * CWI`.
- `analyze_economy(...)` — composite report bundling warnings and recommendations.

Owning doctrine: no direct owner. Docstrings say "per AGENTS spec" (an `AGENTS.md` file is not present in `docs/`) and "per DOM-CLASS-002 and economy policy modes." DOM-CLASS-002 explicitly disclaims formula ownership: "This document does not govern: interest formulas, compounding formulas, accrual timing, solvency math, analytics metrics, visibility behavior, or other execution semantics." The formulas are therefore stranded.

### `app/services/analytics/builders.py` (552 lines)

View-model layer between `analytics_engine.py` and templates. Uses `AnalyticsWindowView` snapshot to build `AnalyticsDashboardView`. Applies threshold-based color/status labels (`participation` thresholds `50` / `70`, `money_velocity` thresholds `1.0` / `2.0`, `on-track students` `60` / `80`, `budget_survival` `60` / `80`) that are hard-coded here, not sourced from `ANALYTICS_POLICY_DEFAULTS`. CWI status thresholds (`50` / `30`) are commented as "Placeholder thresholds — adjust based on actual business rules".

Owning doctrine: view-model layer is presentation. Thresholds are semantic and unowned.

### Schema/tables that were doctrine-specified but never created

`docs/DOMAIN/DOM-ITR-001_INTERPRETATION_DOMAIN.md § IX` declares two tables:
- `interpretation_snapshots(id, class_id, axis, cycle_id, metric_type, window_start, window_end, computed_at, value_payload jsonb)`
- `interpretation_annotations(id, class_id, event_type, timestamp, payload jsonb)`

Neither table exists in `app/models.py` or in `migrations/versions/`. `migrations/versions/7c3d4e5f6a7b_drop_all_unauthorized_tables.py` contains comments noting the intended replacement (analytics_snapshots → interpretation_snapshots) but does not create the successor tables. Runtime returns in-memory `AnalyticsWindowView` dataclasses instead.

### `FEAT-ANLY-001` registration

`app/feats/base.py:121`:
```
"FEAT-ANLY-001": {"domain": "Analytics", "blast_radius": "LOW", "desc": "Analytics Alert Acknowledgement"}
```
The registered domain string `"Analytics"` is not a canonical domain in the DOM inventory. The FEAT is used to guard `AnalyticsEngine.create_snapshot()`. No corresponding `docs/FEATURE-EXECUTION/FEAT-ANLY-*` file exists. (Rename decision is deferred; noted for §VI.)

## IV. Stranded Concepts

Concepts referenced in surviving code, comments, or doctrine that have no live owning doctrine section right now.

1. **Solvency Preservation Principle** — Named in `DOM-ECON-000 §IV.3` (deleted). Referenced obliquely in `economy_balance.py` via `insolvency` warning strings and via the Budget Survival Test which was its enforcement mechanism. No successor principle statement in `DOM-CLASS-002`, `DOM-CLASS-003`, or `DOM-ITR-001`. Best-guess owning domain: could be split — the *policy claim* ("students with perfect attendance must remain viable") is Class Configuration policy; the *test* ("current settings pass survival") is Interpretation Structural.

2. **Budget Survival Test** — Formula lives in `app/utils/economy_balance.py:1140-1199` and in `app/utils/analytics_engine.py::calculate_budget_survival_pass_rate` (a class-aggregated variant). Docstring in `analytics_engine.py` cites "DOM-CLASS-002 and economy policy modes" but DOM-CLASS-002 §II disclaims solvency math ownership. Best-guess owning domain: Interpretation (Structural axis) for the aggregated pass rate; Class Configuration for the per-student single-shot check when used as a recommendation-time solvency validator.

3. **Catastrophe Stability Rule** — Named in `DOM-ECON-000 §XI.2` (deleted). No implementation in current code (`git log -S "Catastrophe"` finds only doctrine hits). Truly dropped — no successor and no runtime behavior.

4. **Doubling-Time Constraint** — `DOM-ECON-000 §X.4` — formula `r = n * (2^(1/(n*t)) - 1)` with per-mode targets (6 / 4 / 2 years). No current implementation; `SPEC-ECON-001` was named as the successor authority for savings interest, but the constraint form is not restated in the surviving files listed in `DOM-CLASS-003.V`. Best-guess owning domain: `SPEC-ECON-001` (savings interest accrual and disbursement).

5. **Collective Goals** — `DOM-ECON-000 §IX`. Ratio bands and reachability projection formula defined. No live implementation found via keyword grep. Truly dropped in the current tree.

6. **CWI Reset Trigger** (`DOM-ITR-001 §VII` "Interpretation MUST reset when CWI changes") — No live enforcement. Snapshots are computed on demand; there is no reset/invalidation path keyed on CWI changes. Owning domain per doctrine: Interpretation.

7. **Payroll-Cycle Time Model** — `DOM-ITR-001 §VII` mandates "only completed payroll cycles." Current `analytics_engine.py` accepts arbitrary `(window_start, window_end)` from callers; no cycle boundary enforcement. Owning domain per doctrine: Interpretation.

8. **`variable_monetary_risk_factor`** — `economy_policy.py:62`, `get_variable_monetary_risk_factor()`. Per-mode factors `0.20 / 0.15 / 0.12`. No doctrine mentions this factor by name; no code call site consumes it (grep for `get_variable_monetary_risk_factor` finds only the definition). Best-guess owning domain: Class Configuration (if it is a config), but currently orphaned.

9. **Analytics thresholds (`participation_warning_threshold`, `velocity_drop_warning_threshold`, `cwi_deviation_warning_threshold`, `cwi_deviation_band`)** — Live in `ANALYTICS_POLICY_DEFAULTS` in `economy_policy.py` and referenced by `analytics_engine.generate_alerts()`. Whether "when to raise an alert" is Class Configuration policy or Interpretation semantics is not answered by any current doctrine. Best-guess owning domain: Interpretation (per doctrine intent), but source-of-truth for the numbers lives in Class Configuration.

10. **View-model thresholds in `builders.py`** — Duplicate/parallel thresholds (`50/70`, `1.0/2.0`, `60/80`) hard-coded in `build_analytics_dashboard_view`, plus a "Placeholder thresholds" comment for CWI status color. No doctrine home. Best-guess owning domain: Interpretation, but currently they diverge from `ANALYTICS_POLICY_DEFAULTS`.

11. **"AGENTS spec"** — Referenced in `economy_balance.py` docstrings ("per AGENTS spec"). No file named `AGENTS.md` in `docs/`. Reference is dangling.

12. **`docs/technical-reference/analytics-specification.md`** — Referenced in `analytics_engine.py`'s module docstring. Deleted `2026-03-01` in commit `26f60578`. Reference is dangling; the "core principles" and "spec section" citations in the docstring have no live source.

## V. Deleted Formulas / Config

Extracted from `DOM-ECON-000` at commit `abb49d75^` (the last commit before deletion). Deletion commit: `abb49d75` (2026-08-08). For each formula, notes whether a live implementation exists.

### 1. CWI derivation

`DOM-ECON-000 §V.2`:
```
CWI = hourly_pay_rate * expected_hours_per_week
CWI = minute_pay_rate * expected_minutes_per_week
```
Live implementation: `EconomyBalanceChecker.calculate_cwi()` in `app/utils/economy_balance.py:245`. Reads `expected_weekly_hours` from `EconomicEngine` (post-commit `a7b8141e`), rate from `PayrollSettings`. Formula preserved. Owning doctrine now: none (DOM-CLASS-002 §II explicitly disclaims). SPEC-ITR-001 or a SPEC-ECON-* would be candidates.

### 2. Per-mode weekly savings target

`DOM-ECON-000 §VIII.1`: `weekly_savings_target = {0.05, 0.10, 0.15} * CWI` for tight/default/comfortable.
Live implementation: `POLICY_MODES[mode]["ratios"]["savings_weekly"]` in `economy_policy.py` (matches: `0.05` / `0.10` / `0.15`). Used by `EconomyBalanceChecker.calculate_budget_survival` and `AnalyticsEngine.calculate_budget_survival_pass_rate`. Formula preserved; owning doctrine now Class Configuration (values), but the *test using them* has no owning doctrine.

### 3. Per-mode rent / utilities / insurance / fine / store-tier ratios

Full grid from `DOM-ECON-000 §VIII.2–VIII.6` and §XII.4. Values match `POLICY_MODES` in `economy_policy.py` exactly (`rent_weekly` tight `0.70–0.80` etc.). Preserved; owning doctrine `DOM-CLASS-003` via `get_price_recommendation_context`.

### 4. Collective goal scaling

`DOM-ECON-000 §IX.2`: goal_ratio bands (tight `0.75x–7.0x`, default `1.0x–8.0x`, comfortable `1.5x–10.0x`) and reachability projection formula. No live implementation. Truly dropped.

### 5. Savings compound growth

`DOM-ECON-000 §X.2`: `A = P * (1 + r/n)^(n*t)`. Live implementation: not in the files inspected here; per DOM-CLASS-003.V, ownership delegated to `SPEC-ECON-001` (savings interest accrual).

### 6. Daily accrual formula

`DOM-ECON-000 §X.3`: `daily_accrual = eligible_balance * (APR / 365)`. Same as above; delegated to `SPEC-ECON-001`.

### 7. Doubling-time constraint

`DOM-ECON-000 §X.4–X.5`: `r = n * (2^(1/(n*t)) - 1)`, targets `6 / 4 / 2` years. No live implementation found. Owning doctrine per delegation: `SPEC-ECON-001`, but not stated in surviving text.

### 8. Budget Survival Test

`DOM-ECON-000 §XI.1`:
```
weekly_savings = CWI − weekly_rent − weekly_insurance − average_store_cost
weekly_savings >= policy_minimum_savings_ratio * CWI
```
Live implementation: `economy_balance.py::calculate_budget_survival` — matches formula. Preserved without owning doctrine.

### 9. Catastrophe Stability Rule

`DOM-ECON-000 §XI.2`: validators SHALL simulate two fines + uninsured loss + discretionary purchases; recovery in one cycle. No live implementation. Truly dropped.

### 10. Analytics canonical metrics

`DOM-ECON-000 §XII.4` defined:
- `obligation_coverage_ratio = students_meeting_obligations / total_students`
- `savings_participation_rate = students_with_positive_savings / total_students`
- `insurance_adoption_rate = insured_students / total_students`
- `passive_income_ratio = interest_income / labor_income`
- `money_velocity = total_economic_transactions / average_money_supply`

`git log -S` for each metric name confirms **none of these were ever implemented** in application code — matches are only in doctrine files (`DOM-ECON-000` and forward-references). The live `AnalyticsEngine` implements a *different* set (participation rate, money velocity as a `transactions / (students * days)` rate, CWI deviation distribution, budget survival pass rate) — `money_velocity` shares the name but the formula is completely different from `DOM-ECON-000`'s definition. Truly dropped: obligation_coverage_ratio, savings_participation_rate, insurance_adoption_rate, passive_income_ratio. Formula-replaced under same name: money_velocity.

### 11. Canonical temporal rules

`DOM-ECON-000 §XIII`: class timezone authority, UTC storage rule, canonical day boundary, savings accrual window, forbidden temporal patterns. Superseded by `SPEC-TIME-001` (canonical temporal resolver) and `INV-ITR-006` (timezone integrity in Interpretation). Preserved under new authority.

### 12. Deterministic calculation requirement

`DOM-ECON-000 §XIV.1`: single canonical calculation layer, no duplicated formulas. Not directly restated in `DOM-CLASS-002` or `DOM-CLASS-003`. Partially satisfied in practice by `economy_policy.py` centralization, contradicted by the parallel threshold constants in `builders.py`.

## VI. Open Semantic Questions

1. **Whose formula is CWI?** The definition (`hourly_rate × expected_weekly_hours`) lives in `economy_balance.py::calculate_cwi`, reads inputs from two different domains (`PayrollSettings`, `EconomicEngine`), and has no owning doctrine after `DOM-ECON-000` was deleted. Is it `DOM-CLASS-002` (economic facts), `DOM-CLASS-003` (economic policy), a new `SPEC-ECON-CWI-*`, or does it belong under the Interpretation Domain as a Structural derivation?

2. **Whose formula is Budget Survival?** Currently implemented in both `economy_balance.py` (per-student, recommendation-time) and `analytics_engine.py` (per-class, snapshot-time), reading policy inputs from `economy_policy.py`. Is this one concept with two callers, or two concepts sharing a name? Whichever domain owns it must define the observation subject unambiguously.

3. **What is `money_velocity`?** The doctrine that named it (`DOM-ECON-000`) defined it as `total_economic_transactions / average_money_supply`. The code that implements it uses `transaction_count / (student_count × days)`. Which is authoritative for `SPEC-ITR-001`?

4. **What happens to Catastrophe Stability Rule, Collective Goals, Doubling-Time Constraint?** Are these intentionally dropped, waiting for `SPEC-ECON-001` / `SPEC-ECON-*` to reinstate them, or forgotten?

5. **Where do analytics thresholds live?** `ANALYTICS_POLICY_DEFAULTS` (band width, warning thresholds) is nested inside `economy_policy.py` (Class Configuration). Alert generation reads them from Interpretation. Are these Class Configuration knobs (teacher-configurable) or Interpretation constants (system-defined)? If the former, no teacher-facing surface currently exposes them.

6. **What replaces `interpretation_snapshots` and `interpretation_annotations`?** DOM-ITR-001 §IX declares them; no migration creates them; runtime returns in-memory `AnalyticsWindowView`. Is the doctrine ahead of implementation, or has the storage decision changed?

7. **What are the canonical Interpretation reset triggers?** DOM-ITR-001 §VII says reset on CWI change or policy change. Neither is wired to any invalidation path. If snapshots are in-memory only, is "reset on change" satisfied trivially, or does this doctrine mandate a persistent cache that must be invalidated?

8. **Does `AnalyticsEngine.create_snapshot()` mutate anything?** It is decorated `@requires_feat_context("FEAT-ANLY-001")` but returns a dataclass without a DB write. If Interpretation is truly read-only (`INV-ITR-001`), why is a FEAT context required? Is a persisted snapshot planned but not yet implemented?

9. **Is `replace_enabled_class_features` policy-append-legal?** ECON-CONST-001 requires append-only policy evolution. The helper appends `ClassFeature` rows but reuses the current `economic_version_id` rather than creating a new `EconomicEngine` version. Whether a feature toggle counts as a "policy change" requiring a new version is not addressed by DOM-CLASS-003.

10. **What is the canonical domain name for `FEAT-ANLY-001`?** Registered as `"Analytics"`, which is not a canonical DOM. Should this be `"Interpretation"` (matching DOM-ITR-001)? Deferred; noted for the SPEC review.

11. **Are the per-mode `store_tiers` in `economy_policy.py` congruent with the four-tier scheme (`basic / standard / premium / luxury`) in `DOM-ECON-000 §VIII.4`?** Comparing: the code has `basic / standard / premium / luxury` bands — matches. But `store_tiers()` in `get_price_recommendation_context` also carries a separate default (also four tiers, different bands: `0.02–0.05 / 0.05–0.10 / 0.10–0.25 / 0.25–0.50`) that only applies when a tier is missing from the mode profile. This default set does not match any published band. What is its provenance?

12. **What is `variable_monetary_risk_factor` for?** Defined but not called. Should be either wired up or removed; either way, ownership is undecided.
