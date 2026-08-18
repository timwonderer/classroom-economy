# Interpretation Metric Recovery (2026-08-16)

| Field | Value |
|---|---|
| Type | Pre-SPEC Investigation |
| Status | Investigation — no doctrine, no decisions |
| Branch | `codex/v2.0` |
| Reference Commit | `dc5e0efb` |
| Companion | `docs/TRACKING/DOM_ECON_ARCHAEOLOGY_2026-08-16.md` |

## 0. Correction Note (added 2026-08-16, post-review)

The original investigation missed `docs/SPEC/SPEC-ECON-003_ECONOMIC_ENGINE_CALCULATION_AND_REFERENCE_SPECIFICATION.md`. That spec (under DOM-CLASS authority) owns CWI derivation (§4.1), per-mode ratio bands (§4.2–§4.8, §8), doubling-time (§5.2, §5.4), compound growth / daily accrual (§5.3, §5.5), and economic coherence rules including labor-dominance (§7.1) and determinism (§7.3).

Implications for this document:

- **Metric 6 `cwi_value`** — CWI is a CLASS-owned configuration derivative per SPEC-ECON-003 §4.1. ITR *consumes* it as a Structural input; ITR does not *own* the formula. Row's "proposed axis" reasoning stands, but the "Is CWI an Interpretation output at all?" open question is answered: no, it is a Configuration Readout.
- **Metric 4 `budget_survival_pass_rate`** — the config-time formula (`economy_balance.py`, matching DOM-ECON-000 §XI.1) belongs to CLASS via SPEC-ECON-003's coherence and savings-target sections. The observed class-percentage metric (`analytics_engine.py`) remains an ITR candidate but must be renamed to disambiguate.
- **Metric 11 `passive_income_ratio`** — Labor Dominance principle is restored under SPEC-ECON-003 §7.1. An ITR observation that reports on it is a distinct concern from the coherence rule itself.
- **Metrics 8, 9, 10** (`obligation_coverage_ratio`, `savings_participation_rate`, `insurance_adoption_rate`) — SPEC-ECON-003 does not restate these. They remain unimplemented candidates for ITR reclamation.
- **Cross-cutting observation §IV.7** (threshold constants scattered across three layers) — SPEC-ECON-003 §7.3 (Determinism) makes the scattering an active violation of a live rule, not undefined territory.

Metric axis assignments in §III are not changed by this correction; per user ruling #10, axes remain under review pending explicit subject + semantic-question analysis. The correction updates ownership boundaries only.

## I. Purpose

This document is the pre-`SPEC-ITR-001` investigation for the Interpretation Domain. Every axis assignment in `DOM-ITR-001` v1.1 and every metric implemented in current code is treated as **suspect** — the doctrine's Behavioral / Structural examples were written before some of the metrics settled, and the code's assignments were driven by a deleted `DOM-ECON-000 §XII` and an unretrieved `docs/technical-reference/analytics-specification.md`.

The goal here is to answer, per metric, "what does this number actually measure?" before assigning it to Behavioral, Structural, or a new axis. No axis is inherited; every proposed axis in the table below is a fresh hypothesis based on subject + semantic question, argued in the "Proposed axis" column.

This is investigation only. It writes no doctrine.

## II. Axis Definitions (as of DOM-ITR-001 v1.1)

Copied verbatim from `docs/DOMAIN/DOM-ITR-001_INTERPRETATION_DOMAIN.md § IV`. Labelled **current, under review** — not authoritative for this document's conclusions.

**Axis 1: Behavioral Interpretation** (current, under review)
- Question: How are actors behaving within the system?
- Subject: `seat_id`
- Input: Event logs (Ledger, Attendance, Obligations)
- Time Model: Completed payroll cycles only
- Nature: Observational
- Examples: Participation rate, money velocity, engagement level, activity distribution, behavioral drift.

**Axis 2: Structural Interpretation (Economy Health)** (current, under review)
- Question: Is the system configuration coherent relative to its economic model?
- Subject: `class_id`
- Input: Class Configuration + CWI
- Time Model: Current configuration evaluated per completed cycle
- Nature: Model-based evaluation
- Examples: Pricing bounds, affordability ranges, survivability envelope, budget pressure, policy alignment.

Note on inconsistency to flag for the SPEC author: DOM-ITR-001 §IV lists `participation_rate` as Behavioral (subject: `seat_id`) but every current implementation aggregates it to a class-level percentage (subject: `class_id`). This is one of several axis/subject mismatches the table below surfaces.

## III. The Table

Candidates: all metrics found in `app/utils/analytics_engine.py`, `app/services/analytics/builders.py`, `app/utils/economy_balance.py`, plus every metric named in the deleted `DOM-ECON-000 §XII.4`. Metrics that only appear in doctrine (never implemented) are included and marked `<none>` under "Current formula."

---

### Metric 1: `participation_rate`

| Column | Value |
|---|---|
| Metric | `participation_rate` |
| Subject | Class (`class_id`). Numerator counts *distinct enrolled student seats* that had a transaction OR attendance session inside the window; denominator is total enrolled student seats. |
| Semantic question | "What fraction of enrolled seats showed any activity in this window?" |
| Observation window | Arbitrary `(window_start, window_end)` supplied by caller. Not aligned to any payroll cycle. |
| Authoritative inputs | `Transaction.seat_id` in-window (Ledger), `AttendanceSession.target_seat_id` in-window (Attendance), `Seat` enrollment (Identity). |
| Current formula | `analytics_engine.py:172-225`. `active_seat_ids = {seats with transactions in window} ∪ {seats with attendance in window}`; `rate = |active_seat_ids| / |enrolled_seats| × 100`. |
| Historical formula | Unchanged since introduction in `7a21f7a4` (2026-01-06). |
| Config references | None. No policy-mode inputs. |
| Output | Scalar percentage (0.0–100.0). |
| Current axis | Behavioral (per DOM-ITR-001 §IV example list). |
| Proposed axis | **Behavioral, but with subject change to `class_id` (aggregate).** The current doctrine example labels this Behavioral with subject `seat_id`; the code produces a class-level scalar. Either the doctrine's subject line should generalize to "seat-derived → class-aggregated" or a new sub-axis is needed. The metric is a summary of actor behavior; it is not a configuration evaluation, so it does not belong in Structural. |
| Unresolved semantic questions | (a) Should "any transaction" count, or only voluntary student-initiated ones? Payroll credits and rent debits are automatic — do they count as "activity"? (b) Should attendance alone count when the class has no economic activity yet? (c) Is a "seat" the right subject when a student can be dis-enrolled mid-window? (d) What window is canonical — the caller-supplied one, or (per doctrine §VII) the last completed payroll cycle? |

---

### Metric 2: `money_velocity`

| Column | Value |
|---|---|
| Metric | `money_velocity` |
| Subject | Class (`class_id`). Aggregate transaction count normalized by student-days. |
| Semantic question | "How intensely is money moving per capita per day in this window?" |
| Observation window | Arbitrary `(window_start, window_end)`. Uses fractional days from `total_seconds() / 86400`. |
| Authoritative inputs | `Transaction` count where `class_id = self.class_id`, `~is_void`, timestamp in window. Enrollment count from `Seat`. |
| Current formula | `analytics_engine.py:227-259`. `velocity = transaction_count / (total_students × days)`, rounded to 2 decimals. |
| Historical formula | Unchanged since `7a21f7a4`. **Note**: `DOM-ECON-000 §XII.4` defined a completely different formula under the same name: `money_velocity = total_economic_transactions / average_money_supply` — a Fisher-equation-style velocity, not a per-capita rate. The code has never implemented that. |
| Config references | None directly. Thresholds for alerting (`velocity_drop_warning_threshold` = 0.30, `builders.py` thresholds `1.0`/`2.0`) live in Class Configuration. |
| Output | Scalar (transactions per student per day). |
| Current axis | Behavioral (per DOM-ITR-001 §IV example list). |
| Proposed axis | **Behavioral, class-aggregate subject.** The number describes what actors are collectively doing (transacting), not whether config is coherent. Same subject caveat as `participation_rate`. |
| Unresolved semantic questions | (a) Should the name be reclaimed for the Fisher-style formula from `DOM-ECON-000`, or should the current per-capita rate be renamed (e.g., `transaction_intensity`)? (b) Should void, adjustment, and system-originated transactions (payroll disbursement, rent assessment) count, or only student-initiated economic acts? (c) The current formula divides by *all* enrolled seats — should it divide by *active* seats to isolate intensity from participation? |

---

### Metric 3: `cwi_deviation_within_20pct` (a.k.a. "On-Track Students")

| Column | Value |
|---|---|
| Metric | `cwi_deviation_within_20pct` |
| Subject | Class (`class_id`). Percentage of student seats whose checking balance is within a ±20% band of the expected balance for the window's duration under perfect attendance. |
| Semantic question | "Given the current CWI and the elapsed weeks, what fraction of students are within a policy-defined tolerance of the expected trajectory?" |
| Observation window | Arbitrary `(window_start, window_end)`; window duration in *whole days* is used (`.days`) to derive `weeks = days/7`. Note that sub-day windows collapse to `weeks = 0`. |
| Authoritative inputs | CWI from `EconomyBalanceChecker.calculate_cwi(payroll_settings)` (Class Configuration inputs: `PayrollSettings` rate, `EconomicEngine.expected_weekly_hours`). Per-seat current checking balance from `ledger_service.get_available_balance` (Ledger). Band width from `analytics_policy["cwi_deviation_band"]` (Class Configuration default 0.20). |
| Current formula | `analytics_engine.py:261-310`. `expected_balance = cwi × weeks`; for each student, `deviation = |current − expected| / expected`; count if `deviation <= band_width`; percentage = count / total × 100. Edge cases: expected=0 & current=0 counted as within band; other zero-expected cases dropped. |
| Historical formula | Unchanged since `7a21f7a4`. |
| Config references | `PayrollSettings` (for CWI), `EconomicEngine.expected_weekly_hours` (for CWI), `POLICY_MODES[mode]["analytics"]["cwi_deviation_band"]` (band width). |
| Output | Scalar percentage. |
| Current axis | Behavioral (per DOM-ITR-001 §IV — "behavioral drift" is example text). |
| Proposed axis | **Hybrid / genuinely axis-ambiguous.** The metric compares *observed actor state* (balances) against a *model-derived expectation* (CWI × weeks). The "how many students match the model" framing is a Behavioral aggregation. The "does the model correctly predict the outcome" framing is Structural. Under DOM-ITR-001 §VI INV-ITR-012 (Axis Exclusivity), this metric may need to be split into two — a Behavioral aggregate ("what fraction of students hoard/underspend?") and a Structural signal ("is CWI × weeks a plausible expected balance?"). |
| Unresolved semantic questions | (a) Is the model `expected_balance = cwi × weeks` correct? It assumes perfect attendance and zero spending, so any student who paid rent is by construction below expected. Should the model subtract expected obligations? (b) Should the metric use elapsed pay cycles rather than raw weeks? (c) Is ±20% policy-mode-dependent, or a universal Interpretation constant? (d) Per DOM-ITR-001 §VI INV-ITR-013, "students aren't spending → pricing is wrong" is explicitly prohibited as a computed rule — is a low `cwi_deviation_within_20pct` allowed to trigger the `cwi_deviation` alert, which does exactly that? |

---

### Metric 4: `budget_survival_pass_rate`

| Column | Value |
|---|---|
| Metric | `budget_survival_pass_rate` |
| Subject | Class (`class_id`). Percentage of student seats whose current checking balance meets or exceeds the policy-mode minimum weekly savings ratio × CWI. |
| Semantic question | Ambiguous. As-implemented in `analytics_engine.py`, it answers "what fraction of students currently hold at least one week's minimum savings?" The name "budget survival" implies a different question — "under recommended settings, can a student with perfect attendance meet their obligations and still save?" — which is the version implemented in `economy_balance.py`. |
| Observation window | The rate uses point-in-time balances (no window). CWI is computed from current PayrollSettings. |
| Authoritative inputs | CWI (as above). Per-seat balance from `ledger_service.get_available_balance`. Savings ratio from `POLICY_MODES[mode]["ratios"]["savings_weekly"]["min"]` (Class Configuration). |
| Current formula | `analytics_engine.py:312-353`. For each student: `pass = balance >= savings_ratio × cwi`. Percentage passing. Distinct from `economy_balance.py:1140-1199` which implements the DOM-ECON-000 §XI.1 formula (`weekly_savings = cwi − rent − insurance − avg_store_spending`) as a solvency validator. |
| Historical formula | The `analytics_engine.py` variant is unchanged since `7a21f7a4`. The `economy_balance.py` variant matches DOM-ECON-000 §XI.1 verbatim. |
| Config references | `POLICY_MODES[mode]["ratios"]["savings_weekly"]["min"]`. `analytics_engine.py` reads this via `policy_profile`. |
| Output | Scalar percentage. |
| Current axis | Not explicitly listed in DOM-ITR-001 §IV. Docstring says "per DOM-CLASS-002 and economy policy modes." |
| Proposed axis | **Two metrics, two axes.** The `economy_balance.py` per-student solvency test is Structural (evaluates whether config produces viable outcomes under a modeled agent). The `analytics_engine.py` class-percentage is Behavioral aggregated (counts how many actual students happen to hold ≥ one-week's-min-savings right now). These are different metrics that share a name. |
| Unresolved semantic questions | (a) Is "current balance ≥ min savings × CWI" the intended survival test, or is it the DOM-ECON-000 §XI.1 formula? (b) The doctrine formula requires knowing per-student rent, insurance, and estimated store spending; the `analytics_engine` version discards all of that. Which is authoritative for `SPEC-ITR-001`? (c) Should the metric use liquid savings (savings account) or checking? (d) Is "budget survival" the right name if the metric doesn't compare income against obligations? |

---

### Metric 5: `avg_student_balance`

| Column | Value |
|---|---|
| Metric | `avg_student_balance` |
| Subject | Class (`class_id`). Simple arithmetic mean of enrolled students' checking balances. |
| Semantic question | "What is the average student's held liquidity right now?" |
| Observation window | Point-in-time (balance snapshot at `computed_at`); not window-scoped. |
| Authoritative inputs | Per-seat `get_available_balance(seat_id, class_id, 'checking')`. |
| Current formula | `analytics_engine.py:552-559`, `605-617`. `total_balance = sum(get_available_balance(...)) ; avg = total / count`. |
| Historical formula | Unchanged. |
| Config references | None. |
| Output | Scalar dollar-equivalent (float). |
| Current axis | Not listed in DOM-ITR-001 §IV. Emitted in `AnalyticsWindowView` for display. |
| Proposed axis | **Behavioral aggregate.** Describes observed actor state. Not compared against a model, so not Structural. Note tension with INV-ITR-009 ("No rankings, no exposed identities, no hierarchy signals") — the mean itself is fine, but exposing it as a headline number invites comparison logic. |
| Unresolved semantic questions | (a) Does this violate INV-ITR-009 if presented as a "class average balance" leaderboard-adjacent metric? (b) Should it be paired with a spread indicator (stdev, percentiles) to convey distribution rather than centrality? (c) Checking vs. total (checking + savings)? |

---

### Metric 6: `cwi_value`

| Column | Value |
|---|---|
| Metric | `cwi_value` |
| Subject | Class (`class_id`). Currently-active Classroom Wage Index for this class. |
| Semantic question | "What is the expected weekly income at perfect attendance under current config?" |
| Observation window | Not window-scoped; reflects current config. |
| Authoritative inputs | `PayrollSettings.hourly_rate` (or minute-based equivalent) × `EconomicEngine.expected_weekly_hours`. |
| Current formula | `EconomyBalanceChecker.calculate_cwi(payroll_settings)` at `economy_balance.py:245`. Retrieved by `analytics_engine.py:151-170`. |
| Historical formula | Formula unchanged; input source moved from PayrollSettings (both parts) to (PayrollSettings + EconomicEngine) in commit `a7b8141e` (2026-08-08). |
| Config references | `PayrollSettings`, `EconomicEngine`. |
| Output | Scalar dollar-equivalent per week. |
| Current axis | Emitted in both `SystemHealthMetrics` and `AnalyticsWindowView` for context. Not axis-labelled in DOM-ITR-001. |
| Proposed axis | **Structural — foundational input.** CWI is the class economy's calibration constant that every Structural metric normalizes against. It is not really a "metric" in the observational sense; it is a *reported configuration derivative*. It may deserve its own category: **Configuration Readout** (neither behavioral nor structural evaluation — just a computed constant for context). Alternatively it belongs in Class Configuration's presentation surface, not Interpretation. |
| Unresolved semantic questions | (a) Is CWI an Interpretation output at all, or a Class Configuration derived attribute that Interpretation *consumes*? (b) When `expected_weekly_hours` is NULL, `calculate_cwi` returns None; `_get_cwi()` collapses that to 0.0 — is silent collapse acceptable, or should Interpretation refuse to emit until CWI is defined? (c) Should CWI have a version identifier tying it to the `economic_version_id` that produced it, so Interpretation snapshots are replayable per DOM-ITR-001 §VI INV-ITR-003? |

---

### Metric 7: `balance_trend` / `velocity_trend` / `participation_trend`

| Column | Value |
|---|---|
| Metric | Three trend indicators |
| Subject | Class (`class_id`). |
| Semantic question | "Compared to the previous snapshot, is this metric increasing, stable, or decreasing?" |
| Observation window | Requires two snapshots; direction based on percent change vs. previous snapshot. |
| Authoritative inputs | Prior `AnalyticsWindowView` (or `None`, in which case all trends collapse to `stable`). |
| Current formula | `analytics_engine.py:355-386`. `change = (current − previous) / previous`; `|change| < 0.10 → 'stable'`; `> 0.10 → 'increasing'`; `< −0.10 → 'decreasing'`. Threshold is a hard-coded 10% in `calculate_trend`. `balance_trend` compares `cwi_deviation_within_20pct` (a rate), not any actual balance. |
| Historical formula | Docstring notes labels changed from `improving`/`worsening` to neutral `increasing`/`decreasing`. Threshold has been 10% throughout. |
| Config references | None. Threshold not sourced from Class Configuration. |
| Output | Categorical: `increasing` / `stable` / `decreasing`. |
| Current axis | Not listed in DOM-ITR-001 §IV, but DOM-ITR-001 §II lists "Trend detection and drift identification" as Interpretation-owned. |
| Proposed axis | **Same axis as their base metric.** A trend of a Behavioral metric is Behavioral; a trend of a Structural metric is Structural. Naming `balance_trend` for a trend over `cwi_deviation_within_20pct` (which is itself axis-ambiguous, see Metric 3) confuses this. Trend indicators should probably not be named after quantities they don't track (`balance_trend` doesn't track balance). |
| Unresolved semantic questions | (a) `compute_trends` is always called with `previous_snapshot=None` inside `create_snapshot` — so all persisted trend values are literally `stable`. Is this a bug, an unfinished feature, or an intentional "trends live in the viewer, not the snapshot" design? (b) Is 10% a policy constant or a universal Interpretation threshold? (c) Why is `cwi_deviation_within_20pct` labelled `balance_trend`? |

---

### Metric 8: `obligation_coverage_ratio`

| Column | Value |
|---|---|
| Metric | `obligation_coverage_ratio` |
| Subject | Doctrine-declared: class (`class_id`). |
| Semantic question | "What fraction of students met their obligations this cycle?" |
| Observation window | Doctrine-implied per-cycle. |
| Authoritative inputs | Obligations domain (student obligation records + satisfaction events). |
| Current formula | `<none — never implemented>`. Named only in `DOM-ECON-000 §XII.4` (deleted). |
| Historical formula | `obligation_coverage_ratio = students_meeting_obligations / total_students`. |
| Config references | Implied: obligation catalogue from Obligations domain. |
| Output | Scalar ratio. |
| Current axis | Not in DOM-ITR-001 §IV. |
| Proposed axis | **Behavioral (aggregated).** Counts actor outcomes over a cycle. Not a configuration evaluation. |
| Unresolved semantic questions | (a) Should this be recovered as an active metric, or is it obsolete? (b) "Meeting obligations" is ambiguous — every posted, every posted on time, or every satisfied without waiver? (c) Is it distinct from a Behavioral participation metric? |

---

### Metric 9: `savings_participation_rate`

| Column | Value |
|---|---|
| Metric | `savings_participation_rate` |
| Subject | Class (`class_id`). |
| Semantic question | "What fraction of students hold any savings?" |
| Observation window | Point-in-time. |
| Authoritative inputs | Ledger (savings account balances per seat). |
| Current formula | `<none — never implemented>`. |
| Historical formula | `savings_participation_rate = students_with_positive_savings / total_students`. |
| Config references | None. |
| Output | Scalar ratio. |
| Current axis | Not in DOM-ITR-001 §IV. |
| Proposed axis | **Behavioral aggregate.** |
| Unresolved semantic questions | (a) Positive-balance threshold — any positive amount, or above some minimum? (b) Discretionary savings vs. auto-swept? (c) Recover or discard? |

---

### Metric 10: `insurance_adoption_rate`

| Column | Value |
|---|---|
| Metric | `insurance_adoption_rate` |
| Subject | Class (`class_id`). |
| Semantic question | "What fraction of students carry active insurance?" |
| Observation window | Point-in-time. |
| Authoritative inputs | Insurance domain (active policies per seat). |
| Current formula | `<none — never implemented>`. |
| Historical formula | `insurance_adoption_rate = insured_students / total_students`. |
| Config references | Insurance-feature enablement (`ClassFeature`). |
| Output | Scalar ratio. |
| Current axis | Not in DOM-ITR-001 §IV. |
| Proposed axis | **Behavioral aggregate.** |
| Unresolved semantic questions | (a) Recover or discard? (b) Should it condition on insurance being available (feature enabled + policy offered)? |

---

### Metric 11: `passive_income_ratio`

| Column | Value |
|---|---|
| Metric | `passive_income_ratio` |
| Subject | Class (`class_id`). |
| Semantic question | "What share of student income comes from interest vs. labor?" |
| Observation window | Doctrine-implied per-cycle. |
| Authoritative inputs | Ledger transactions typed as interest vs. payroll. |
| Current formula | `<none — never implemented>`. |
| Historical formula | `passive_income_ratio = interest_income / labor_income`. |
| Config references | None directly; interest configuration lives in `EconomicEngine`. |
| Output | Scalar ratio. |
| Current axis | Not in DOM-ITR-001 §IV. |
| Proposed axis | **Behavioral aggregate**, but flagged: this metric directly implicates the Labor Dominance Principle from DOM-ECON-000 §IV.1 (which was deleted). If that principle is reinstated in a SPEC-ECON, `passive_income_ratio` becomes a Structural coherence check ("is the Labor Dominance invariant being satisfied?") as well. |
| Unresolved semantic questions | (a) Recover or discard? (b) Include disbursements from savings interest and treat sim-store rewards as which? (c) Bind to a solvency/interest doctrine. |

---

### Metric 12: `solvency` (and "Solvency Preservation Principle")

| Column | Value |
|---|---|
| Metric | `solvency` |
| Subject | Class-level (aggregate solvency signal) or per-seat (individual solvency check). Ambiguous. |
| Semantic question | "Under current config, do modeled students remain economically viable?" |
| Observation window | Not window-based; evaluated against current config. |
| Authoritative inputs | Class Configuration (rent, insurance, fine, store, savings ratio). CWI. |
| Current formula | `<none as a metric>`. The concept is present as `insolvency` warning text in `app/utils/economy_balance.py:633`, `1058` (fine amount too harsh); and the *test that would produce it* is the Budget Survival Test (Metric 4 / `economy_balance.py:1140`). No dedicated `solvency` scalar or ratio is computed. |
| Historical formula | DOM-ECON-000 §IV.3 stated the principle in prose, not as a formula. §XI.2 (Catastrophe Stability Rule) gave a scenario-based validator: two fines + uninsured loss + discretionary — student must recover within one cycle. Never implemented. |
| Config references | Entire policy-mode ratio grid. |
| Output | Would be categorical (viable / at-risk) or scalar (margin). |
| Current axis | Not in DOM-ITR-001 §IV. |
| Proposed axis | **Structural.** Evaluates whether the configuration produces viable outcomes for a modeled representative agent. Independent of what actual students do. |
| Unresolved semantic questions | (a) Is the Solvency Preservation Principle reinstated, and if so where? (b) What is the canonical modeled agent — perfect attendance + zero discretion, or a specific participation profile? (c) Is Catastrophe Stability a separate metric or a variant of Solvency? (d) Should `insolvency` warning text in `economy_balance.py` be lifted to a formal Structural metric? |

---

### Metric 13: `savings_deviation`

| Column | Value |
|---|---|
| Metric | `savings_deviation` |
| Subject | Unknown. |
| Semantic question | Presumed: "Are student savings tracking the expected trajectory?" |
| Observation window | Unknown. |
| Authoritative inputs | Presumed: Ledger (savings balances) + policy-mode savings target. |
| Current formula | `<none — no code implementation, no doctrine reference found>`. `git log -S "savings_deviation"` returns zero commits. The user prompt mentioned it as "referenced in older docs" but no such reference exists in current git history under that exact string. |
| Historical formula | None found. |
| Config references | Would be `savings_weekly` ratio. |
| Output | Would be scalar. |
| Current axis | N/A. |
| Proposed axis | If ever recovered, likely **Behavioral aggregate** (analogous to `cwi_deviation_within_20pct` but for savings). |
| Unresolved semantic questions | (a) Confirm this metric was ever named — the string is not present in git history. May be a misremembered variant of `cwi_deviation`. (b) If desired, define it de novo. |

---

### Metric 14: `avg_student_balance` (already listed as Metric 5)

Included above.

---

### Metric 15: Alerts (`participation_low`, `cwi_deviation`, `velocity_drop`, `budget_survival_low`)

| Column | Value |
|---|---|
| Metric | Four alert types emitted by `AnalyticsEngine.generate_alerts()` |
| Subject | Class (`class_id`). |
| Semantic question | "Should the teacher be shown a warning card about this condition?" |
| Observation window | Same as the metric each alert wraps. |
| Authoritative inputs | Metrics 1, 3, 7 (velocity direction), 4; thresholds from `POLICY_MODES[mode]["analytics"]` (via `ANALYTICS_POLICY_DEFAULTS`). |
| Current formula | `analytics_engine.py:468-526`. Threshold comparisons — `participation < participation_warning_threshold × 100`; `on_track < 100 × (1 − cwi_deviation_warning_threshold)`; `velocity_trend == 'decreasing'`; `budget_survival_pass_rate < 50` (hard-coded 50, not policy-driven). |
| Historical formula | Unchanged since `7a21f7a4`. |
| Config references | `ANALYTICS_POLICY_DEFAULTS`. Also hard-coded 50 for `budget_survival_low`. |
| Output | List of alert dicts (severity, what_changed, why_it_matters, suggested_action). |
| Current axis | Not axis-labelled. |
| Proposed axis | **Behavioral or Structural depending on the underlying metric**, but any alert that suggests changing config (e.g., `cwi_deviation` says "Review: Are wages appropriate for attendance patterns?") crosses into what INV-ITR-013 explicitly prohibits: "students aren't spending → pricing is wrong" as a computed rule. This is a doctrine/code conflict, not an axis assignment. |
| Unresolved semantic questions | (a) Are Interpretation-generated policy suggestions inside alert text a violation of INV-ITR-010 (no policy authority) and INV-ITR-013 (no cross-axis authority)? (b) Is `budget_survival_low`'s hard-coded 50% a policy or an Interpretation constant? (c) Should alerts be an Interpretation output at all, or a separate "Advisory" layer? |

## IV. Cross-cutting Observations

1. **Subject mismatch is systemic.** DOM-ITR-001 §IV pins Behavioral to `seat_id`, but every implemented Behavioral metric emits a class-level scalar. The doctrine's subject line reads as if per-seat outputs were the norm; the reality is that every output is class-aggregated. The SPEC should either widen the subject definition to "seat-derived, class-aggregated" or introduce a `subject_aggregation` field so a metric can declare both its unit of observation and its unit of output.

2. **Three of the four active class-health metrics read Class Configuration inputs at compute time.** `cwi_deviation_within_20pct`, `budget_survival_pass_rate`, and every alert threshold consult `POLICY_MODES` / `ANALYTICS_POLICY_DEFAULTS`. This crosses the Interpretation/Class-Configuration boundary in a way DOM-ITR-001 does not explicitly authorize (it says inputs may be "Class Configuration + CWI" for Structural, but does not address Behavioral metrics that use policy-mode-varying thresholds).

3. **The doctrine-only metrics from DOM-ECON-000 §XII (`obligation_coverage_ratio`, `savings_participation_rate`, `insurance_adoption_rate`, `passive_income_ratio`) are all Behavioral-aggregate by shape.** If Interpretation reclaims them, the Behavioral axis' example list should expand to include them.

4. **The current axis binary (Behavioral / Structural) does not cleanly hold three concepts:** (a) `cwi_value` — a reported configuration derivative, neither observation nor evaluation; (b) `cwi_deviation_within_20pct` — genuinely comparing observation to model, straddling both axes; (c) Trend indicators — inheriting an axis from their base metric rather than being intrinsically one or the other. A third axis ("Diagnostic" or "Configuration Readout") or a metadata field (`derived_from_axis`) may be needed.

5. **`create_snapshot` is FEAT-guarded but performs no mutation.** Either it should mutate (materialize `interpretation_snapshots` per DOM-ITR-001 §IX) or the FEAT decorator is overkill for an Interpretation read.

6. **Two `budget_survival` implementations under one name.** `economy_balance.py`'s per-student solvency test (matches DOM-ECON-000 §XI.1) and `analytics_engine.py`'s class-percentage-holding-≥-one-week's-savings. These are different metrics; the shared name is a hazard.

7. **Threshold constants are scattered across three layers.** `ANALYTICS_POLICY_DEFAULTS` (Class Configuration), `analytics_engine.py::generate_alerts` (uses those + hard-coded 50%), `builders.py` view models (independent hard-coded 50/70, 60/80, 1.0/2.0, plus "Placeholder thresholds — adjust based on actual business rules" for CWI status). No single authority.

## V. Recommended Next Step for User

Before `SPEC-ITR-001` can be drafted, the user needs to decide (or defer with a reason):

1. **Axis model.** Keep binary Behavioral/Structural, or introduce a third axis / metadata field for the ambiguous cases (`cwi_deviation`, `cwi_value`, trends, alerts)?
2. **Subject model.** Is the canonical subject `seat_id` with declared aggregation to `class_id`, or `class_id` with implicit source of `seat_id`? Same question for metric-level output.
3. **Metric roster.** Which of the four DOM-ECON-000 §XII metrics (`obligation_coverage_ratio`, `savings_participation_rate`, `insurance_adoption_rate`, `passive_income_ratio`) does Interpretation reclaim? Which stay dropped?
4. **`budget_survival` split.** Two metrics with distinct names, or one canonical implementation?
5. **`money_velocity` definition.** Per-capita-per-day rate (current code) or Fisher-style transactions/money-supply (DOM-ECON-000)?
6. **Threshold ownership.** Are alert thresholds Interpretation constants (baked into SPEC-ITR-001) or Class Configuration knobs (surfaced to teachers)?
7. **Snapshot persistence.** Materialize `interpretation_snapshots` and `interpretation_annotations` per DOM-ITR-001 §IX, or keep in-memory and revise the doctrine?
8. **Time model.** Do metrics enforce completed-payroll-cycle windows (per DOM-ITR-001 §VII), or accept arbitrary caller windows?
9. **Alert content.** Are policy-directive suggestions inside alerts (`Review: Are wages appropriate…`) compatible with INV-ITR-010 and INV-ITR-013? If not, either the alerts move to a non-Interpretation domain or the invariants relax.
10. **Solvency reinstatement.** Recover Solvency Preservation Principle + Catastrophe Stability Rule as Structural metrics, delegate to a SPEC-ECON-*, or drop permanently?
11. **CWI's home.** Is CWI an Interpretation output, a Class Configuration derived attribute Interpretation consumes, or both?
12. **`variable_monetary_risk_factor` and any other orphaned constants** — remove or wire up?
