# SPEC-ITR-001: Interpretation Observation Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-ITR-001     |  1.3    |     2026-08-30 |        1.2 |       Normative |

---

## 1. Purpose

This specification is the single canonical technical source for the observation questions and candidate quantities that the Interpretation Domain answers.

`DOM-ITR-001` v1.2 authorizes Interpretation to produce descriptive observations and interpretive signals about participation, economic activity, obligation outcomes, savings behavior, income composition, resource distribution, and resilience. `DOM-ITR-001` does not name specific observations, formulas, or thresholds. This specification does.

This document defines:

- the observation questions Interpretation is required to answer,
- the candidate quantities that answer each question,
- the authoritative source domains each candidate consumes,
- the declared output properties (Semantic Kind, Subject / Observation Basis / Aggregation, Reference Dependency) per `DOM-ITR-001` INV-ITR-012,
- what each candidate legitimately supports and what it does not,
- the observation gaps that must be closed elsewhere before a candidate can lawfully be built,
- the canonical serialized shape of the `observations_json` materialization payload, including its required candidate manifest and completeness gate (§15).

This document does not define:

- axis assignments (the Behavioral / Structural frame is retired by `DOM-ITR-001` v1.2 §IV),
- alert content, alert thresholds, or prescriptive teacher-facing text (`DOM-ITR-001` §III, §XI, INV-ITR-010 prohibit these),
- persistence schemas or lifecycle contracts (`DOM-ITR-001` §VIII, §IX, §X.9 — future Materialize FEAT scope),
- numeric thresholds for any candidate (each threshold requires an owner per `DOM-ITR-001` INV-ITR-017; owners are declared here only where they exist).

---

## 2. Governing Authority

This specification's authority derives from and is subordinate to:

- `DOM-ITR-001` — Interpretation Domain (semantic authority). The output-property and invariant rules restated here derive from the v1.2 semantic model (§IV, INV-ITR-012–017), which v1.4 preserves. v1.4 additionally specifies cycle-bound materialization (`interpretation_cycle_record`, §VII–§IX); v1.1 of this specification aligns to it.
- `DOM-PROD-001` — Productivity and Payroll Domain (payroll-cycle boundary, `payroll_cycle_id`)
- `FEAT-PROD-004` — Complete Payroll Cycle (canonical materialization orchestrator)
- `DOM-CORE-000` — Domain Foundation
- `INV-ARC-009` — Domain Authority for State

Cross-domain source-of-truth dependencies (per `DOM-ITR-001` INV-ITR-002 and INV-ITR-016):

- `DOM-LED-001` — Ledger Domain (monetary movement and provenance)
- `DOM-OBL-001` — Obligations Domain (assessment / payment / waiver events)
- `DOM-PROD-001` — Productivity and Payroll Domain (attendance sessions, payroll events)
- `DOM-STORE-001` — Store and Entitlements Domain (entitlement events)
- `DOM-CLASS-001`, `DOM-CLASS-002`, `DOM-CLASS-003` — Class Configuration domains
- `SPEC-ECON-003` — Economic Engine Calculation and Reference Specification (CWI, per-mode bands)
- `SPEC-TIME-001` — Canonical Temporal Resolver

This specification does not create, modify, or invalidate authority in any of the above.

---

## 3. Foundational Rules Inherited from DOM-ITR-001 v1.2

The following are restated for engineering convenience. They are not created here; the authoritative source is `DOM-ITR-001` v1.2.

- Every output declares exactly one Semantic Kind: **Descriptive observation** or **Interpretive signal** (§IV.1).
- Every output declares Subject, Observation Basis, and Aggregation using authoritative identifiers of the owning domain (§IV.2).
- Every output declares Reference Dependency: **None**, **Class Configuration observational reference**, or **Interpretation-declared reference** (§IV.3).
- Configuration input ranges are not observational references (INV-ITR-014).
- Descriptive observations are not silently promoted to interpretive conclusions (INV-ITR-013).
- Ledger provenance is classified via `mechanism`, `feat_code`, `correlation_id`, reversal linkage, and authoritative source-domain event tables. `Transaction.type` is not authoritative (INV-ITR-015).
- Authoritative facts are consumed from the owning domain, not reconstructed from Ledger rows (INV-ITR-016).
- Every threshold has an explicit semantic owner (INV-ITR-017).
- Only completed economic cycles are evaluated (§VII).
- Interpretation does not prescribe teacher action (§III, §XI, INV-ITR-010).

### 3.1 Optional Computation Metadata: Normalization Dependency

`DOM-ITR-001` §IV / INV-ITR-012 defines exactly three required output-property declarations (Semantic Kind, Subject / Observation Basis / Aggregation, Reference Dependency). This specification does not add a fourth required declaration.

For outputs that rescale their result by a class-configuration derivative, this specification defines a piece of **optional computation metadata**, sitting alongside — not among — the three required properties:

- **Normalization dependency** — the configuration derivative (if any) used to rescale the output's units. Declared with its authoritative source. `CWI` per `SPEC-ECON-003 §4.1` is the only value used in v1.0. Applicable only when an output reports the same underlying observation in configuration-derived units.

Normalization is distinct from Reference Dependency. A normalized output does not compare an observation to an expectation; it reports the same observation in different units. An output MAY declare a Normalization dependency; its Reference Dependency is declared independently and remains one of the three DOM-required values. Per INV-ITR-014, a normalization value SHALL NOT be treated as an observational expectation.

Absence of a Normalization dependency is not a compliance defect. Implementations MUST NOT treat Normalization dependency as a fourth mandatory declaration.

---

## 4. Observation Questions

This specification defines nine observation questions. Q7 is a boundary rule, not a quantity. Q8 is intentionally not included.

| ID | Question |
|---|---|
| Q1a | To what extent did students actually participate through attendance-derived labor during the completed window? |
| Q1b | To what extent did students exercise economic agency through student-initiated economic interaction during the completed window? |
| Q2 | How much economic activity occurred, restricted to student-initiated events? |
| Q3 | To what extent were assessed obligations satisfied during the completed window? |
| Q4 | To what extent are students holding and contributing to savings? |
| Q5 | What proportion of observed income came from each meaningful origin category? |
| Q6 | How are economic resources distributed across the class? |
| Q7 | Boundary rule — configured-vs-observed comparisons (see §12). |
| Q9 | Are students remaining economically capable of participating in the classroom economy, or are some showing persistent difficulty meeting ordinary economic requirements despite continued participation? |

Insurance adoption is intentionally excluded from Economy Health scope. It is neither a required observation of `DOM-ITR-001` v1.2 nor authorized by this specification. Any future addition requires a defensible semantic question and a separate SPEC revision.

Trend indicators (period-over-period comparisons) are out of scope for v1.0 because no prior cycle-record source exists yet (`DOM-ITR-001` §XIII.a); one accrues only as `interpretation_cycle_record` rows are materialized cycle-over-cycle.

---

## 5. Q1a — Labor Participation

### 5.1 Question

To what extent did students actually participate through attendance-derived labor during the completed window?

### 5.2 Authoritative Source

`DOM-PROD-001` — `attendance_sessions` table. `AttendanceSession` is the authoritative persisted fact for labor participation. Interpretation SHALL NOT consult Ledger to establish that labor participation occurred. Consequences of labor (payroll monetary flow) are addressed in Q5; the participation fact itself is Attendance-authoritative per INV-ITR-016.

### 5.3 Minimum Raw Observations

Per enrolled seat in the completed window:

- Presence of ≥1 `AttendanceSession` row where `class_id` matches, `target_seat_id` matches, and `timestamp` falls inside the window.
- Count of qualifying attendance sessions (for distributional reporting).
- Enrollment status during the window (Identity domain).

### 5.4 Candidate Quantities

**Q1a-C1: Labor-participation fraction (aggregate)**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `seat_id`
- **Aggregation:** `class_aggregate_from_seat_observations`
- **Reference Dependency:** None
- **Definition:** fraction of enrolled seats with ≥1 `AttendanceSession` in the window.
- **Legitimately supports:** statement of how many enrolled seats registered any attendance in the window.
- **Cannot support:** engagement quality, learning outcomes, statements about non-attending students beyond their absence from the observation.

**Q1a-C2: Attendance-session count distribution**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `seat_id` (per-seat attendance-session counts are the intermediate observation basis; they are not themselves the externally exposed Interpretation output)
- **Aggregation:** `class_distribution_from_seat_observations` — per-seat counts of `AttendanceSession` rows in the window are combined into a class-level distribution summary. The summary SHALL use the pinned `distribution` value-kind core defined in §15.6 (`count`, `p10`, `p25`, `p50`, `p75`, `p90`, `iqr`); `mean` MAY be reported as the optional secondary statistic. This candidate does not use the `n_at_or_below_zero` extension (attendance-session counts have no meaningful zero-crossing tail). The previously permitted "percentile decomposition, inter-quartile range, or equivalent per the implementing FEAT" latitude is withdrawn as of v1.3: immutable records from different cycles SHALL speak the same statistical language. Per-seat counts SHALL NOT be exposed externally as Interpretation outputs.
- **Reference Dependency:** None
- **Legitimately supports:** distribution of how much attendance occurred across the class.
- **Cannot support:** individual-seat ranking or per-seat identification (INV-ITR-009); comparison against a configured or reference expectation without a declared observational reference (INV-ITR-014).

### 5.5 Preconditions and Gaps

None. Q1a is fully specifiable against the current source domain.

---

## 6. Q1b — Student-Initiated Economic Interaction

### 6.1 Question

To what extent did students exercise economic agency (voluntary transfers, purchases, obligation self-payment, savings contributions) during the completed window?

### 6.2 Authoritative Sources

- `DOM-LED-001` — `Transaction` rows with `mechanism = SELF` and non-reversal, filtered by `feat_code` to exclude system-originated FEATs.
- `DOM-STORE-001` — `EntitlementEvent` rows with `acquisition_type = 'PURCHASE'`, `event_type = 'GRANTED'`.
- `DOM-OBL-001` — `AssessmentEvent` rows with `event_type = 'PAYMENT'` where the referenced Ledger row has `mechanism = SELF`.

Per INV-ITR-016, when the same act is recorded both by a source domain (EntitlementEvent, AssessmentEvent) and by Ledger, the source-domain fact takes precedence.

### 6.3 Provenance Classifier

The event-origin classifier used throughout §6, §7, and §9 is:

- **Student-originated:** `Transaction.mechanism = SELF` AND `Transaction.original_transaction_id IS NULL` AND `Transaction.is_void = FALSE` AND `Transaction.feat_code` is not in the system-FEAT set (payroll accrual, interest accrual, obligation assessment, admin adjustment, ledger resolution).
- **Teacher-originated:** `Transaction.mechanism = TEACHER`.
- **System-originated:** `Transaction.mechanism = SYSTEM`.
- **Reversal:** `Transaction.original_transaction_id IS NOT NULL` (per `DOM-LED-001` INV-LED-003).
- **Void:** `Transaction.is_void = TRUE` on the original.

Per INV-ITR-015, `Transaction.type` is not consulted for this classification.

### 6.4 Minimum Raw Observations

Per enrolled seat in the completed window:

- Presence of ≥1 student-originated Ledger transaction (per §6.3), OR
- Presence of ≥1 STORE `EntitlementEvent` with `acquisition_type='PURCHASE'`, OR
- Presence of ≥1 OBLIGATIONS `PAYMENT` event whose referenced Ledger row is student-originated.

### 6.5 Candidate Quantities

**Q1b-C1: Student-initiated interaction fraction**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `seat_id`
- **Aggregation:** `class_aggregate_from_seat_observations`
- **Reference Dependency:** None
- **Definition:** fraction of enrolled seats with at least one student-initiated economic act (per §6.4) in the window.
- **Legitimately supports:** statement of how many enrolled seats exercised student-initiated economic agency in the window.
- **Cannot support:** conclusions about students who had no opportunity to act (feature disabled, no store items offered); ranking of students by agency; comparison against configured expectations without a declared observational reference.

### 6.6 Preconditions and Gaps

None blocking. The system-FEAT set in §6.3 is enumerable from `app/feats/base.py` and stable enough to specify; SPEC-ITR-001 defers the concrete enumeration to the implementing FEAT.

---

## 7. Q2 — Student-Initiated Economic Activity Level

### 7.1 Question

How much economic activity occurred, restricted to student-initiated events?

### 7.2 Rule of Separation

Frequency and monetary volume SHALL be reported as separate quantities. This specification prohibits combining them into a single "activity" scalar.

### 7.3 Candidate Quantities

**Q2-C1: Student-initiated transaction frequency (per active seat per day)**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `Transaction.id` (student-originated per §6.3), plus `seat_id` for the active-seat denominator
- **Aggregation:** `class_rate_from_seat_observations` — total student-initiated Ledger transactions in the window ÷ (count of seats with ≥1 student-initiated act in the window × completed-cycle days in the window). Denominator uses active seats, not enrolled seats, so participation and intensity remain independent quantities.
- **Reference Dependency:** None
- **Legitimately supports:** statement of transaction intensity per active seat per day; period-over-period comparison across cycles (once such comparison is a supported operation).
- **Cannot support:** "healthy" or "unhealthy" verdicts; comparison against any threshold in the absence of an explicitly owned threshold per INV-ITR-017; the historical `money_velocity` (Fisher-style) semantics — that is a distinct candidate (Q2-C3).

**Q2-C2: Student-initiated transaction monetary volume**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `Transaction.id` (student-originated per §6.3)
- **Aggregation:** `class_sum` — sum of absolute monetary amounts of student-initiated Ledger transactions in the window.
- **Reference Dependency:** None.
- **Normalization dependency:** None if reported in raw units; `CWI` per `SPEC-ECON-003 §4.1` if reported CWI-normalized. Normalization changes the unit of the output; it is not an observational expectation and does not authorize comparison against a policy-mode band (INV-ITR-014).
- **Legitimately supports:** statement of the monetary magnitude of student-initiated economic movement in the window.
- **Cannot support:** monetary velocity claims (see Q2-C3); assumptions about money supply.

**Q2-C3: Monetary velocity (Fisher-style) — RESERVED**

- **Semantic Kind:** Interpretive signal (would be, if defined)
- **Status:** NOT DEFINED IN v1.0.
- **Reason:** Historical `DOM-ECON-000 §XII.4` defined `money_velocity = total_economic_transactions / average_money_supply`. Neither `total_economic_transactions` nor `average_money_supply` was defined in that doctrine. `SPEC-ECON-003` does not restate the formula. A defensible class-economy definition of "money supply" is a prerequisite that this specification does not attempt to invent. If future SPEC-ITR-001 revisions include this candidate, it will be defined against a class-economy money-supply reference supplied by CLASS or SPEC-ECON-003, not by Interpretation.

### 7.4 Preconditions and Gaps

None blocking Q2-C1 and Q2-C2. Q2-C3 is explicitly reserved and unimplementable in v1.

---

## 8. Q3 — Obligation Observation

### 8.1 Question

To what extent were assessed obligations satisfied during the completed window?

### 8.2 Authoritative Source

`DOM-OBL-001` — `assessment_events` table. Three-state discriminator: `ASSESSMENT`, `PAYMENT`, `WAIVED` (`DOM-OBL-001` §V). Satisfaction logic per `DOM-OBL-001` §V.6. Interpretation consumes this event stream directly per INV-ITR-016.

### 8.3 Rule of Separation

Count-based and amount-based observations SHALL be reported separately. Waived obligations SHALL be reported as a distinct outcome category, not merged with paid.

### 8.4 Candidate Quantities

**Q3-C1: Obligation satisfaction fraction — count-based**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`, per obligation type
- **Observation basis:** `AssessmentEvent.correlation_id` (each obligation is identified by its `ASSESSMENT` event's correlation)
- **Aggregation:** `class_fraction_over_obligations` — for each obligation assessed in the window, its final status (`SATISFIED via PAYMENT only`, `SATISFIED via WAIVED`, `SATISFIED via mix of PAYMENT + WAIVED`, `UNSATISFIED at window end`) is reported as one of four disjoint categories. Fractions reported per category.
- **Reference Dependency:** None
- **Legitimately supports:** statement of how many obligations reached each satisfaction state, by count.
- **Cannot support:** verdicts about student effort or economic health from status alone; treatment of `WAIVED` as equivalent to `PAYMENT` for economic-effort observation.

**Q3-C2: Obligation coverage fraction — amount-based**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`, per obligation type
- **Observation basis:** `AssessmentEvent.amount` on `ASSESSMENT` events and referenced Ledger amounts on `PAYMENT` events
- **Aggregation:** `class_ratio` — total assessed dollars in the window against total paid dollars (via `PAYMENT` events referencing student-originated Ledger rows per §6.3) and total waived dollars (via `WAIVED` events) reported as separate numerators against the assessed denominator.
- **Reference Dependency:** None
- **Legitimately supports:** statement of the monetary fraction of assessed obligations covered by student payment vs waiver vs unmet.
- **Cannot support:** conflation of student-paid and admin-injected funds — see §8.5 for the composite-payment limit.

**Q3-C3: Waiver-distinct outcome breakdown**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`, per obligation type
- **Observation basis:** `AssessmentEvent` rows
- **Aggregation:** `class_counts` — raw counts of `ASSESSMENT`, `PAYMENT`, `WAIVED`, and unsatisfied assessments in the window.
- **Reference Dependency:** None
- **Legitimately supports:** statement of raw counts of each event kind for reporting transparency.
- **Cannot support:** verdicts on teacher generosity or student distress from waiver counts alone.

### 8.5 Composite Payment Limit

An `AssessmentEvent.PAYMENT` whose referenced Ledger row is student-originated (`mechanism=SELF`) is treated as student-covered. Where a teacher-injected credit prior to the `PAYMENT` event funded the student's account, this specification does not attempt to attribute that funding to the teacher. This is a fundamental limitation of the persisted provenance (no per-seat funds-source lineage), not a specification omission.

### 8.6 Overdraft / NSF Obligation Outcomes

**Overdraft / NSF fees are admitted into Q3 as of v1.1.** The ownership question is resolved: per `SPEC-ECON-003` §4.6.1.1 and `DOM-ITR-001` §XIII.c, OBLIGATIONS owns the NSF fee as an immediate obligation, LEDGER executes the fee debit and stays domain-blind, and the originating business FEAT's cross-domain orchestration produces an `AssessmentEvent` (an `NSF_FEE` `ASSESSMENT` and a corresponding `PAYMENT` settled by the fee debit).

Consequently:

- An NSF-fee obligation is an ordinary obligation for Q3 purposes and participates in Q3-C1 (count-based satisfaction), Q3-C2 (amount-based coverage), and Q3-C3 (waiver-distinct breakdown), consumed from `assessment_events` per INV-ITR-016 — never reconstructed from a Ledger `type` string.
- Q3 outputs SHALL identify the NSF-fee obligation type distinctly (per-obligation-type subject, §8.4) so a reader can see obligation outcomes with and without the NSF-fee contribution.
- **Scope boundary (mirrors the assessment scope).** An NSF fee exists only for a failed purchase or a failed obligation payment (a failed *agreement*). It is never assessed for transfers (lateral movement) or penalties (admin adjustments). Q3 SHALL NOT synthesize an NSF obligation for any event that did not produce an `NSF_FEE` `AssessmentEvent`.

**Coverage gap.** Only NSF fees recorded through the resolved orchestration (producing an `AssessmentEvent`) are observable. Any legacy overdraft rows written before that orchestration exists as bare Ledger `type="overdraft_fee"` rows with no `AssessmentEvent`; those are not observable by Q3 and MUST NOT be reconstructed from Ledger, per INV-ITR-016 and INV-ITR-015. This is a transitional coverage gap tracked toward zero, not an ownership question.

---

## 9. Q4 — Savings Behavior

### 9.1 Question

To what extent are students able and choosing to hold and contribute to savings?

### 9.2 Rule of Separation

**Stock** (balance held at window end) and **flow** (contributions during the window) SHALL be reported as separate quantities.

### 9.3 Authoritative Sources

- `DOM-LED-001` — per-seat savings-account balance at window end; `Transaction` rows with student-originated transfers to savings during the window.
- `DOM-CLASS-*` — feature enablement (savings feature must be enabled for Q4 to be meaningful).

### 9.4 Candidate Quantities

**Q4-C1: Savings-holding fraction (stock)**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `seat_id`
- **Aggregation:** `class_fraction_from_seat_observations`
- **Reference Dependency:** None
- **Definition:** fraction of enrolled seats with `savings` balance strictly greater than zero at window end.
- **Legitimately supports:** statement of how many students hold any savings at window end.
- **Cannot support:** conclusions when savings feature is disabled (see §9.6); "healthy" verdicts from adoption alone.

**Q4-C2: Savings-contribution fraction (flow)**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `seat_id`, with per-seat presence of ≥1 qualifying `Transaction.id` — student-originated transfers with `account_type='savings'` on the deposit side of a correlated transfer pair (per `DOM-LED-001` INV-LED-007). Transactions are the intermediate evidence; the underlying observation is per-seat.
- **Aggregation:** `class_fraction_from_seat_observations` — fraction of enrolled seats with ≥1 qualifying contribution in the window.
- **Reference Dependency:** None
- **Legitimately supports:** statement of how many students contributed to savings during the window.
- **Cannot support:** magnitude of savings behavior — the count is contribution-event-based, not amount-based; magnitude is Q4-C3.

**Q4-C3: Savings-contribution volume (flow)**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `Transaction.id`, same filter as Q4-C2
- **Aggregation:** `class_sum` — sum of absolute deposit-side amounts in the window.
- **Reference Dependency:** None.
- **Normalization dependency:** None if reported in raw units; `CWI` per `SPEC-ECON-003 §4.1` if reported CWI-normalized. Normalization changes the unit of the output; it is not an observational expectation.
- **Legitimately supports:** statement of the total monetary volume of student-initiated savings contributions in the window.
- **Cannot support:** comparison against a policy-mode savings target as an observational expectation (INV-ITR-014); `SPEC-ECON-003` §4.2 declares the savings target as a configuration input, not an observational reference.

### 9.5 Distribution View

Per-seat savings balance distribution (percentile summary) is scoped under Q6 (Resource Distribution), not Q4.

### 9.6 Preconditions and Gaps

When the savings feature is disabled for a class, all Q4 outputs SHALL be reported as `not_applicable`, not zero. Feature enablement is a CLASS-owned fact consumed by Interpretation.

---

## 10. Q5 — Income Composition

### 10.1 Question

What proportion of observed income came from each meaningful origin category?

### 10.2 Origin Categories

Per prior ruling: use only economically meaningful origin categories that current provenance can substantiate. The categories are:

1. **Labor-derived** — Ledger inflows produced by `FEAT-PROD-003` (payroll). Corroborated by presence of a `PayrollEvent` row sharing the Ledger row's `correlation_id`. Excludes `payroll_event_type='manual_credit'` and `payroll_event_type='reversal'`.
2. **Interest / passive** — Ledger inflows to `savings` account with `mechanism=SYSTEM` produced by the interest-accrual FEAT (`SPEC-ECON-001` owner).
3. **Teacher / admin-injected** — Ledger inflows produced by `FEAT-ADMIN-ADJUSTMENT` with `mechanism=TEACHER`, plus payroll rows with `payroll_event_type='manual_credit'`. This category is not further subdivided by v1.0; per prior ruling, no bonus / award / correction taxonomy is invented for Interpretation.
4. **System-originated non-labor** — Ledger inflows with `mechanism=SYSTEM` that are neither interest accrual nor payroll. This category includes any system-generated credit that is not labor or interest.
5. **Deterministically identifiable reversals / refunds** — Ledger rows with `original_transaction_id IS NOT NULL` (per `DOM-LED-001` INV-LED-003). Sign of the amount determines whether the reversal is inbound or outbound relative to the seat.
6. **Other / unclassified** — Ledger inflows that do not match categories 1–5. Per prior ruling, "other / unclassified" is an acceptable observational result when canonical provenance cannot support a narrower claim.

### 10.3 Candidate Quantities

**Q5-C1: Income composition — share by category**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `Transaction.id` for inbound-to-seat Ledger rows in the window
- **Aggregation:** `class_share_by_category` — for each of the six categories, the fraction of total inbound monetary volume in the window belonging to that category.
- **Reference Dependency:** None
- **Legitimately supports:** statement of the observed composition of student income by origin category.
- **Cannot support:** verdict on `SPEC-ECON-003` §7.1 Labor Dominance coherence — that verdict is CLASS authority; Q5-C1 may inform it but does not resolve it (per INV-ITR-010 and INV-ITR-014).

**Q5-C2: Labor-share observation**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `Transaction.id` for labor-derived rows (§10.2 category 1)
- **Aggregation:** `class_ratio` — labor-derived inbound volume ÷ total inbound volume in the window.
- **Reference Dependency:** None
- **Legitimately supports:** statement of what share of observed inbound money originated from labor.
- **Cannot support:** any claim that this share satisfies or violates the Labor Dominance principle declared in `SPEC-ECON-003` §7.1. Such a claim would require a Class Configuration observational reference explicitly declaring a labor-share expectation; `SPEC-ECON-003` currently declares Labor Dominance as a coherence rule on interest, not as an observational expectation on income composition.

### 10.4 Preconditions and Gaps

**Interest accrual has no dedicated event model.** Interest is currently produced as a direct Ledger row (`type="Interest"`, `mechanism=SYSTEM`, `account_type="savings"`) with no `InterestAccrualEvent` table. Category 2 in §10.2 depends on `feat_code` matching the interest-accrual FEAT (`SPEC-ECON-001` scope) rather than a domain event. This is deterministic today but is a weaker provenance surface than the other categories. Documented as an implementation observation, not a blocker.

---

## 11. Q6 — Resource Distribution

### 11.1 Question

How are economic resources distributed across the class?

### 11.2 Rule of Separation

Distribution SHALL be reported separately for **checking**, **savings**, and **total resources** (checking + savings). This specification prohibits collapsing them into a single number.

### 11.3 Rule of Distribution First

Mean-first reporting is prohibited. Distribution summaries (percentile decomposition, inter-quartile range, tail counts) are the primary output. Mean MAY be reported as a secondary statistic only alongside a distribution summary.

### 11.4 Authoritative Sources

- `DOM-LED-001` — per-seat balances by account type at window end.

### 11.5 Candidate Quantities

**Q6-C1: Balance distribution — checking**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`
- **Observation basis:** `seat_id`
- **Aggregation:** `class_distribution_from_seat_observations` — the pinned `distribution` value-kind defined in §15.6: core (`count`, `p10`, `p25`, `p50`, `p75`, `p90`, `iqr`) plus the balance-distribution extension `n_at_or_below_zero` (count of seats at or below zero); `mean` MAY be reported as the optional secondary statistic. No other distribution statistics are admitted, so that balance distributions from different cycles remain directly comparable.
- **Reference Dependency:** None
- **Legitimately supports:** statement of how concentrated or spread checking balances are across the class; count of seats in the low tail.
- **Cannot support:** naming individual seats; ranking; verdicts on fairness or dysfunction from spread alone.

**Q6-C2: Balance distribution — savings**

- Same structure as Q6-C1 with `savings` account.
- Reported as `not_applicable` when savings feature is disabled.

**Q6-C3: Balance distribution — total resources**

- Same structure as Q6-C1 with sum of `checking` + `savings` per seat.
- Reported per Q6-C2's feature-enablement rule when savings is disabled: falls back to checking-only report with a declared basis note.

### 11.6 Presentation Constraints

Per `DOM-ITR-001` INV-ITR-009 (Actor Dignity Constraint), no ranking, no exposed identities, no hierarchy signals. Distribution summaries (aggregate statistics) are permitted; per-seat exposure is not. Implementation-level presentation surfaces SHALL enforce this at the view-model layer.

Class-relative percentile thresholds are **not** a solvency or distress boundary. They belong to Q6 as distribution summaries only. See §13 for the Q9 boundary rule that prohibits using percentiles as viability references.

---

## 12. Q7 — Configured-vs-Observed Boundary Rule

### 12.1 Purpose

This section is not a quantity. It is a boundary rule governing when any Interpretation output MAY reference a Class Configuration value.

### 12.2 Rule

Interpretation MAY compare an observation to a Class Configuration or `SPEC-ECON-*` value only when that value is explicitly declared as an **observational reference** by the owning domain. Interpretation SHALL NOT infer an observational reference from a permissible-input range, a policy-mode band, or a configured recommendation range.

Per `DOM-ITR-001` INV-ITR-014, configuration inputs are not observational references. Per `DOM-ITR-001` §II reference-scope constraint, an Interpretation-declared reference may frame analysis but cannot manufacture expectations that properly belong to another domain.

### 12.3 Current State

As of v1.0 of this specification, `SPEC-ECON-003` declares configuration bands and coherence rules but does not declare observational expectations for individual student outcomes. **No candidate quantity in this specification uses a Class Configuration observational reference.** Every candidate declares Reference Dependency as `None`.

CWI-normalized reporting on Q2-C2 and Q4-C3 is Normalization dependency (§3.1), not Reference Dependency. Normalization rescales the output's units; it does not compare an observation to an expectation. Reporting the same quantity in CWI units instead of raw units does not authorize any comparison against a policy-mode band or configured recommendation range (INV-ITR-014).

Any future candidate that requires a Class Configuration observational reference MUST wait for that reference to be explicitly declared as observational by the owning domain. Interpretation MUST NOT proceed without it.

---

## 13. Q9 — Resilience Observation

### 13.1 Question

Are students remaining economically capable of participating in the classroom economy, or are some showing persistent difficulty meeting ordinary economic requirements despite continued participation?

**v1.0 does not answer this question conclusively.** The question is interpretive but v1.0's answer is deliberately descriptive: Q9 exposes the independent descriptive observations relevant to the question. Concluding that a class or a subset of students is or is not economically capable requires a viability reference that no owning domain currently declares (see §13.5). Q9 outputs SHALL NOT themselves be presented as answers to the motivating question.

### 13.2 Design Rules for v1.0

- **No composite classifier.** This specification does not define a state ladder, severity taxonomy, or single "solvency score." Q9 exposes independent signals that a teacher can inspect.
- **No low-balance threshold.** The quantitative boundary for "economic difficulty" or "depletion" is explicitly unresolved. It requires a defensible economy-relative reference that neither `DOM-CLASS-*` nor `SPEC-ECON-003` currently declares. Class-relative percentiles are not that reference (they belong to Q6).
- **No prediction.** Recovery-feasibility modeling is out of scope for v1.0. Q9 is descriptive observation only.
- **No recovery/reset gating.** Recovery or reset eligibility, triggering, execution, and gating are not Interpretation-owned per `DOM-ITR-001` §II. Interpretation observations may later inform such a decision but SHALL NOT reference, specify, or gate it.
- **Overdraft / NSF admitted (v1.1).** The ownership question is resolved (§8.6): OBLIGATIONS owns the NSF fee, which surfaces as an `AssessmentEvent`. Q9's obligation-outcome signals (§13.3.b) therefore include NSF-fee obligations, consumed from `assessment_events` per INV-ITR-016. NSF-fee obligations remain descriptive observations only; they do not authorize any viability verdict (§13.5).

### 13.3 Independent Observation Groups

The five groups below are reported as independent signals. This specification prohibits collapsing them into a single scalar.

#### 13.3.a Resource signals

- Per-seat checking balance at window end.
- Per-seat savings balance at window end.
- Per-seat total resources at window end.
- Duration observations: count of days in the window where the seat's checking balance was ≤ 0.

Reported per Q6's distribution rules. No per-seat exposure without INV-ITR-009 compliance at the presentation layer.

#### 13.3.b Obligation outcome signals

- Per-seat count of obligations in the window that were: satisfied by student PAYMENT only, satisfied by WAIVED, satisfied by mix, unsatisfied at window end.

Reported as a class-level distribution over these four outcomes. Sourced from `AssessmentEvent` per §8 rules.

#### 13.3.c Teacher-support signals

- Per-seat count of `WAIVED` events in the window.
- Per-seat count of teacher-originated (`mechanism=TEACHER`, non-reversal) Ledger inflows in the window.

Reported as class-level distributions. Interpretation does not judge whether these represent generosity, distress, or normal operation.

#### 13.3.d Labor participation signals

- Per-seat attendance session count in the window (from Q1a).
- Whether the seat had any attendance in the window (inactive vs active).

An inactive seat is not observed as economically distressed under Q9; it is observed as outside the economy for the window. This distinction is explicit in the output.

#### 13.3.e Persistence signals

- Whether the observations above hold across ≥1 completed economic cycle vs across multiple consecutive completed cycles.

Persistence is not defined numerically in v1.0. Reporting states persistence in terms of "single completed cycle" or "consecutive completed cycles" as observed, without invoking a fixed duration.

**Persistence is not a trend.** Persistence answers only whether the same qualifying descriptive observation is present in independently evaluated consecutive completed cycles. It SHALL NOT calculate direction, magnitude of change, slope, improvement, deterioration, or any comparison between cycle values. Period-over-period trend computation remains out of scope for v1.0 (§4) and requires a prior cycle-record source that does not currently exist (`DOM-ITR-001` §XIII.a).

### 13.4 Candidate Quantity

**Q9-C1: Resilience observation set**

- **Semantic Kind:** Descriptive observation
- **Subject:** `class_id`, with per-seat observations underneath
- **Observation basis:** `seat_id`, `AssessmentEvent`, `Transaction` (per §6.3 provenance classifier), `AttendanceSession`
- **Aggregation:** `class_distribution_from_seat_observations` across each of the five signal groups in §13.3, reported independently.
- **Reference Dependency:** None. Q9 in v1.0 uses no CLASS observational reference and no Interpretation-declared reference.
- **Legitimately supports:** teacher inspection of class-level resilience patterns and distributions that may motivate further investigation through the authoritative source domains.
- **Cannot support:** identification of which specific seats constitute the observed population — Interpretation is bound by `DOM-ITR-001` INV-ITR-009 (no exposed identities, no hierarchy signals) and MUST NOT surface per-seat identifiers as part of a Q9 output; teachers investigating specific students SHALL do so through the authoritative source domains (Ledger, Obligations, Attendance) using those domains' own access surfaces. Q9-C1 also cannot support: any composite resilience verdict; any statement that a seat "needs recovery"; any low-balance threshold claim; any recovery / reset eligibility signal; any prediction of recovery time.

### 13.5 Preconditions and Gaps

- **Viability reference undefined.** Q9 cannot presently declare "students in economic difficulty" as an interpretive signal because no observational reference exists that would authorize such a comparison. Adding such an interpretive signal in a future revision requires either (a) `DOM-CLASS-*` or `SPEC-ECON-*` declaring a viability reference explicitly, or (b) an Interpretation-declared reference that satisfies the §II reference-scope constraint (frames analysis without manufacturing an expectation owned by another domain).
- **Overdraft / NSF admitted (§8.6).** Q9's obligation-outcome signals include NSF-fee obligations sourced from `assessment_events`, subject to the transitional coverage gap for legacy pre-orchestration overdraft rows described in §8.6.
- **Historical Configuration Binding resolved for cycle records (`DOM-ITR-001` §VII).** When Q9 is materialized as part of an `interpretation_cycle_record` at payroll completion (`FEAT-PROD-004`), it is bound to the closed cycle and its versioned `reference_configuration` projection, so it is not reinterpreted under later configuration. Pre-contract cycles have no such projection and are therefore explicitly **not reinterpreted or replayable** — they do not become replayable merely because the table now exists. Ad-hoc caller-supplied windows spanning a configuration change are likewise not replayable; callers SHALL be advised in that transitional case.

---

## 14. Cross-Cutting Rules

### 14.1 Feature Enablement

Every candidate whose input domain can be disabled (savings, insurance, obligations by type) SHALL report `not_applicable` when the required feature is disabled, not zero. Feature enablement is a CLASS-owned fact consumed by Interpretation per INV-ITR-016.

### 14.2 Small Classes

Candidate quantities reported as fractions or percentages SHALL always be paired with the underlying counts (`n / N`). This specification defines no small-N suppression threshold in v1.0. Suppressing percentages below a class-size threshold is a decision governed by INV-ITR-017 (Threshold Ownership) and requires an explicitly owned contract; that contract is deferred. Until it exists, presentation surfaces SHALL neither invent nor apply a suppression threshold — the paired-counts rule is the sole v1.0 protection against the small-class-percentage misreading trap.

### 14.3 Void and Reversal Handling

Per `DOM-LED-001` INV-LED-003 and INV-LED-010:

- Rows with `is_void = TRUE` are excluded from all counts and volumes.
- Rows with `original_transaction_id IS NOT NULL` are classified as reversals per §10.2 category 5 and are excluded from other categories.

Per `DOM-ITR-001` INV-ITR-005, all reversals must be reflected in every downstream output.

### 14.4 Threshold Ownership

No candidate quantity in this specification declares a numeric threshold. Where an implementing FEAT requires a threshold for presentation (e.g., color banding, alert triggering), the threshold requires an explicit semantic owner per `DOM-ITR-001` INV-ITR-017. The implementing FEAT's specification SHALL declare the owner. Absent such a declaration, presentation surfaces SHALL NOT invent thresholds locally.

### 14.5 Alert Content

Per `DOM-ITR-001` §III, §XI, and INV-ITR-010, Interpretation does not prescribe teacher action. This specification does not define alert content, alert thresholds, or prescriptive `suggested_action` text. Any teacher-facing surface that consumes Interpretation outputs SHALL frame those outputs descriptively; prescriptive text is a non-Interpretation concern.

Existing runtime `suggested_action` content in `analytics_engine.py::generate_alerts` violates this constraint. Per `DOM-ITR-001` §XIII.c, its disposition is a runtime remediation matter, not a specification question.

### 14.6 Time Model

Per `DOM-ITR-001` §VII, only completed economic cycles are evaluated. The canonical economic cycle is defined by payroll completion (`DOM-PROD-001` §XV): a cycle closes when a class-level payroll run completes, and its `payroll_cycle_id` identifies the completed window. The authoritative Interpretation of a completed cycle is materialized once, as an `interpretation_cycle_record`, via `FEAT-PROD-004`.

Where the implementing FEAT accepts an ad-hoc caller-supplied window (outside the materialization path), it SHALL either reject non-cycle-aligned windows or coerce them to the nearest fully completed cycle boundary, and SHALL declare which behavior was chosen in its output metadata.

Per `SPEC-TIME-001`, all time logic uses the canonical temporal resolver. Interpretation SHALL NOT compute time semantics directly.

---

## 15. Observation Serialization Contract (`observations_json`)

This section defines the canonical serialized shape of the `observations_json` payload persisted in an `interpretation_cycle_record` (`DOM-ITR-001` §IX). It is the contract that the slice 8.2b compute core produces and the slice 8.2c materialization writer validates before writing an immutable cycle record. It defines structure, vocabulary, and determinism only; it does not define computation (the per-candidate definitions in §§5–13 remain the semantic authority) and it does not define the table (`DOM-ITR-001` §IX / migration `b3d7f1a9c2e4`).

This contract governs the materialization path only. It does not constrain the shape of ad-hoc, non-materialized read-only Interpretation output (§14.6), which is not persisted and carries no immutability obligation.

### 15.1 Contract versioning

- `schema_version` (integer) identifies the envelope structure defined by this section. v1.3 defines `schema_version = 1`.
- `spec.ref` / `spec.version` record the SPEC-ITR-001 revision whose candidate definitions the payload was computed against (`"SPEC-ITR-001"`, `"1.3"`).
- `coverage.required_set_version` (integer) identifies the required candidate manifest (§15.2) the payload was validated against. v1.3 defines `required_set_version = 1`.

The required manifest is fully determined by the pair `(spec.version, coverage.required_set_version)`. A historical row therefore does not restate the manifest; the manifest is recovered from this specification at that version.

### 15.2 Required v1 candidate manifest (`required-set-v1`)

`required-set-v1` is exactly the following 17 candidate identifiers:

```
Q1a-C1  Q1a-C2
Q1b-C1
Q2-C1   Q2-C2
Q3-C1   Q3-C2   Q3-C3
Q4-C1   Q4-C2   Q4-C3
Q5-C1   Q5-C2
Q6-C1   Q6-C2   Q6-C3
Q9-C1
```

A materialized `observations_json` SHALL contain exactly one observation entry per identifier in `required-set-v1`: no missing identifiers, no duplicates, no identifiers outside the set. This exact-set-equality condition is the completeness rule enforced in §15.8.

### 15.3 Applicability model

Every observation entry declares `applicability`, which is a closed two-state enum:

- `computed` — the candidate was computed for this cycle; a `value` is present.
- `not_applicable` — the candidate's required input feature is disabled for the class this cycle (per §14.1); no `value` is present and `not_applicable_reason` is populated.

There is no `unavailable`, `not_implemented`, `pending`, `deferred`, or equivalent third state. Immutability (`DOM-ITR-001` §IX) forbids a materialized record from declaring an intent to fill a candidate in later. A candidate that cannot be truthfully emitted as either `computed` or `not_applicable` blocks materialization (§15.8); it does not get a placeholder.

`not_applicable` is a truthful observation of feature state, never a substitute for zero (§14.1). A candidate whose feature is enabled but whose observed quantity is zero is `computed` with a zero-bearing `value`, not `not_applicable`.

### 15.4 Envelope structure

The top-level payload is a JSON object:

```json
{
  "schema_version": 1,
  "spec": { "ref": "SPEC-ITR-001", "version": "1.3" },
  "coverage": { "required_set_version": 1, "complete": true },
  "observations": [ /* observation entries, §15.5 */ ]
}
```

`coverage` is deliberately lean. It carries `required_set_version` (which manifest) and `complete` (the serializer-derived boolean of §15.8). It SHALL NOT restate the 17 identifiers, and it SHALL NOT carry compute-supplied `candidates_present` / `candidates_missing` arrays — those are recomputed on demand from `observations[]` and the manifest, never trusted from the payload.

### 15.5 Observation entry structure

Each element of `observations[]` is a JSON object:

| Field | Requiredness | Meaning |
|---|---|---|
| `candidate_id` | always | one identifier from `required-set-v1` (§15.2) |
| `semantic_kind` | always | `descriptive_observation` or `interpretive_signal`, per the candidate's §§5–13 declaration |
| `subject` | always | the candidate's declared Subject (e.g. `class_id`) |
| `observation_basis` | always | the candidate's declared Observation Basis (e.g. `seat_id`) |
| `aggregation` | always | the candidate's declared Aggregation identifier |
| `reference_dependency` | always | `none`, `class_configuration_observational_reference`, or `interpretation_declared_reference` (§3, INV-ITR-012). All v1 candidates declare `none` (§12.3). |
| `normalization_dependency` | nullable | optional computation metadata (§3.1); `null` when the candidate does not rescale by a configuration derivative. `"cwi"` where declared (Q2-C2, Q4-C3). Never promoted to a required property. |
| `applicability` | always | `computed` or `not_applicable` (§15.3) |
| `not_applicable_reason` | conditional | populated iff `applicability = not_applicable`; a structured reason (e.g. `{ "feature": "savings", "state": "disabled" }`). `null` when `computed`. |
| `qualifiers` | nullable | structured basis notes (§15.7); `null` when the candidate carries none |
| `value` | conditional | present iff `applicability = computed`; one of the value-kinds in §15.6. `null` when `not_applicable`. |

The three DOM-required output properties (Semantic Kind; Subject / Observation Basis / Aggregation; Reference Dependency) are carried as first-class fields on every entry so that each materialized observation is self-describing per INV-ITR-012, independent of this specification.

### 15.6 Value-kind vocabulary (closed for v1)

`value` is a JSON object carrying a `kind` discriminator drawn from this closed set. No other `kind` is admitted in `schema_version = 1`. Fraction and count provenance lives **inside** the relevant value shape (the paired counts of §14.2); there is no generic top-level counts field on the entry.

- **`fraction`** — `{ "kind": "fraction", "numerator": <int>, "denominator": <int>, "value": "<decimal>" }`. The paired `n / N` counts of §14.2 are the `numerator` / `denominator`.
- **`category_fractions`** — `{ "kind": "category_fractions", "categories": [ { "category": "<id>", "numerator": <int>, "denominator": <int>, "value": "<decimal>" }, ... ] }`. Used by composition candidates (e.g. Q5-C1 income-origin shares). Each category carries its own paired counts.
- **`ratio`** — `{ "kind": "ratio", "antecedent": <number>, "consequent": <number>, "value": "<decimal>" }`. Used where the quantity is a ratio of two observed magnitudes rather than a subset fraction.
- **`rate`** — `{ "kind": "rate", "numerator": <number>, "denominator": <number>, "unit": "<unit-id>", "value": "<decimal>" }`. A per-unit rate (e.g. per active seat).
- **`amount`** — `{ "kind": "amount", "value": "<decimal>", "unit": "<unit-id>" }`. A single scalar magnitude (`unit` is `"tokens"` or `"cwi"` where CWI-normalized).
- **`distribution`** — pinned in §15.6.1.
- **`counts`** — `{ "kind": "counts", "items": [ { "label": "<id>", "count": <int> }, ... ], "total": <int> }`. A categorical count vector (e.g. Q3 obligation-outcome breakdown, Q9 outcome distributions). This is a value shape, not the entry-level provenance field prohibited above.
- **`signal_set`** — `{ "kind": "signal_set", "signals": [ { "signal_id": "<id>", "value": { <any value-kind above> }, "applicability": "computed|not_applicable", "not_applicable_reason": <structured|null> } ] }`. Used only by Q9-C1, whose §13.3 mandates independent, non-collapsed signal groups. Each member signal nests one of the value-kinds above and carries its own applicability so a disabled input disables one signal without invalidating the set.

#### 15.6.1 Pinned `distribution` vocabulary

A `distribution` value is:

```json
{
  "kind": "distribution",
  "count": <int>,
  "p10": "<decimal>", "p25": "<decimal>", "p50": "<decimal>",
  "p75": "<decimal>", "p90": "<decimal>",
  "iqr": "<decimal>"
}
```

- **Core (required on every `distribution`):** `count`, `p10`, `p25`, `p50`, `p75`, `p90`, `iqr`.
- **Candidate-specific extension:** `n_at_or_below_zero` (`<int>`) — required on the balance distributions **Q6-C1, Q6-C2, Q6-C3** (and the Q9-C1 resource signals that reuse the balance-distribution shape). Not emitted by distributions where a zero-crossing tail is not meaningful (e.g. Q1a-C2 attendance-session counts).
- **Optional:** `mean` (`<decimal>`) — MAY be reported as a secondary statistic alongside the core, per the mean-second rule (§11.3). Never a substitute for the distribution core.

No distribution admits statistics outside this vocabulary in `schema_version = 1`. This is a normative tightening over the pre-v1.3 "or equivalent" latitude: every materialized distribution, across every cycle, speaks the same statistical language.

### 15.7 Qualifiers (structured basis notes)

`qualifiers` is a nullable structured field that records a truthful narrowing of an entry's observation basis, so the narrowing is preserved in the immutable record rather than lost. Its canonical use is Q6-C3: when savings is disabled, Q6-C3 falls back to a checking-only total-resources report and §11.5 **requires a declared basis note**. That basis note is recorded here:

```json
"qualifiers": { "basis_note": { "code": "checking_only_savings_disabled", "excluded_component": "savings" } }
```

`qualifiers` SHALL NOT carry prescriptive text, thresholds, or alert content (§14.4, §14.5). It records what was observed and on what narrowed basis, nothing more. Entries with no qualifier set `qualifiers` to `null`.

### 15.8 Completeness and the materialization gate

`coverage.complete` is **serializer-derived**, never a compute-supplied assertion. The serializer computes it — and the slice 8.2c writer independently re-validates it before writing — by verifying exact set equality between the candidate identifiers actually present in `observations[]` and `required-set-v1` (§15.2):

```
{ candidate_id for each entry in observations }  ==  required-set-v1
```

`complete` is `true` iff **all** of the following hold:

1. every identifier in `required-set-v1` appears in `observations[]`;
2. no identifier appears more than once (no duplicates);
3. no entry carries an identifier outside `required-set-v1` (no extras);
4. every entry has a lawful `applicability` (§15.3), and every `computed` entry carries a `value` of an admitted kind (§15.6) while every `not_applicable` entry carries a `not_applicable_reason` and no `value`.

The writer treats a compute-supplied `coverage.complete` as untrusted input: it recomputes the condition from `observations[]` and the manifest and **fails closed** if the recomputed result is not `true`, regardless of what the payload claimed. This is the governance gate: the materialization side effect of `FEAT-PROD-004` is not lawfully reachable until the compute core produces a payload that satisfies exact-set-equality with lawful applicability for all 17 candidates. A partial payload cannot be materialized, and immutability therefore guarantees no "fill in the rest later" record can exist.

### 15.9 Determinism and canonical serialization

Per INV-ITR-003 (deterministic reproducibility), the serialized payload SHALL be deterministic for a given cycle input:

- **Observation ordering:** `observations[]` SHALL be sorted ascending by `candidate_id` (byte-wise on the identifier string). `category_fractions.categories[]`, `counts.items[]`, and `signal_set.signals[]` SHALL each be sorted ascending by their own identifier field (`category`, `label`, `signal_id`).
- **Decimal representation:** every non-integer quantity (fractions, percentiles, ratios, rates, amounts, means) SHALL be serialized as a canonical decimal **string**, not a floating-point number, to preserve exact value across round-trips. Counts (`count`, `numerator`, `denominator`, `n_at_or_below_zero`, `items[].count`, `total`) are JSON integers.
- **No object-key ordering requirement:** determinism does **not** depend on JSON object key order. PostgreSQL `jsonb` does not preserve insertion order of object keys, so key order is not a meaningful serialization property and SHALL NOT be relied upon. Determinism is carried by array ordering and canonical decimal strings, both of which survive `jsonb` normalization.
- **No wall-clock content:** `observations_json` SHALL NOT embed computation timestamps or other non-reproducible runtime values. Cycle timing lives in the record's own `cycle_started_at` / `cycle_completed_at` / `computed_at` columns (`DOM-ITR-001` §IX), not in the observation payload.

---

## 16. What This Specification Does Not Define

For clarity, and to prevent implementations from over-reaching:

- No numeric thresholds for any candidate (§14.4).
- No alert content or `suggested_action` text (§14.5).
- No persistence schema for Interpretation outputs. `DOM-ITR-001` §IX now specifies the durable, immutable `interpretation_cycle_record` (cycle-bound, self-describing via a versioned `reference_configuration` projection), materialized only as a declared side effect of `FEAT-PROD-004` at payroll completion. Its schema, migration, and schema certification are now delivered (migration `b3d7f1a9c2e4`, slice 8.1) — the persistence surface is implemented; the materialization writer that populates a row is not yet built. This specification defines the observations that populate `observations_json` (§§5–13) and, as of v1.3, the canonical serialized shape of that payload (§15) — but not the table build itself.
- FEAT registry rename in code — landed. `FEAT-ITR-001` is now the canonical name in `app/feats/base.py` per `DOM-ITR-001` §VIII; the previous `FEAT-ANLY-001` alias has been removed. Consumer sites (`app/utils/analytics_engine.py`, `app/routes/analytics.py`) updated in the same slice.
- No axis assignments — the Behavioral / Structural frame is retired by `DOM-ITR-001` v1.2 §IV.
- No trend indicators — no prior cycle-record source exists yet per `DOM-ITR-001` §XIII.a.
- No composite scores, no state ladders, no severity taxonomies (Q9 §13.2).
- No recovery / reset eligibility, references, or gating (Q9 §13.2). Per `DOM-ITR-001` §II, recovery / reset is not Interpretation-owned; Q9 outputs SHALL NOT name, reference, or gate any specific recovery mechanism.
- (Resolved in v1.1) Overdraft / NSF observation is admitted via the OBLIGATIONS `AssessmentEvent` surface (§8.6, §13.5).
- No monetary velocity (Fisher-style) formula (Q2-C3).
- No admin-adjustment subtype taxonomy (Q5 §10.2 category 3).
- No configuration-band-as-expectation comparisons (§12, INV-ITR-014).

---

## 17. Implementation Preconditions Summary

The following are preconditions to lawful implementation of the candidates in this specification. Failure of any precondition does not invalidate the specification but does bound what a compliant implementation can produce.

| # | Precondition | Owner | Status |
|---|---|---|---|
| P1 | `DOM-ITR-001` v1.2 is the governing authority | Interpretation | **Satisfied** |
| P2 | Ledger provenance available via `mechanism`, `feat_code`, `correlation_id`, reversal linkage | Ledger | **Satisfied** |
| P3 | Authoritative source-domain event tables consulted before Ledger reconstruction (INV-ITR-016) | Interpretation | Runtime noncompliance per `DOM-ITR-001` §XIII.b — must be closed by implementing FEAT |
| P4 | System-FEAT set enumerable (for §6.3 classifier) | Interpretation FEAT | Enumerable from `app/feats/base.py` |
| P5 | Overdraft / NSF ownership resolved between LEDGER and OBLIGATIONS | Cross-domain (not Interpretation) | **Resolved** (`SPEC-ECON-003` §4.6.1.1, `DOM-ITR-001` §XIII.c) — OBLIGATIONS owns the NSF fee, surfaced as an `AssessmentEvent`; Q3 and Q9 admit it (§8.6, §13.5). Transitional coverage gap for legacy pre-orchestration overdraft rows only. |
| P6 | Historical Configuration Binding schema and provenance surface | Interpretation + PROD + CLASS | **Resolved by contract** (`DOM-ITR-001` §VII, §IX) — cycle-bound `interpretation_cycle_record` persists the governing `reference_configuration` projection at payroll completion (`FEAT-PROD-004`), so cycles under the contract are self-describing and never reinterpreted. Table build is a downstream slice. Pre-contract cycles have no frozen configuration projection and are therefore explicitly **not reinterpreted or replayable**; they do not become replayable merely because the table now exists. |
| P7 | Threshold owners declared for any implementing FEAT that needs thresholds | Implementing FEAT | Deferred to FEAT specification |
| P8 | Class Configuration observational references (if any future candidate ever requires one) | CLASS / SPEC-ECON | Not required by v1.0 candidates. CWI usage in v1.0 is Normalization dependency (§3.1), not Reference Dependency. |

---

## 18. Amendment

Amendments to this specification require review against `DOM-ITR-001` v1.2 or its successor. Amendments that add a candidate quantity SHALL declare the candidate's Semantic Kind, Subject / Observation Basis / Aggregation, and Reference Dependency per `DOM-ITR-001` §IV. Amendments that add a Reference Dependency of type `Class Configuration observational reference` SHALL cite the owning-domain declaration that authorizes it.
