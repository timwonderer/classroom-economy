# DOM-ECON-000: Economy Governance Foundation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| DOM-ECON-000 | 1.1 | 2026-06-08 | 1.0 | Constitutional |

---

# I. Purpose

This document defines the constitutional economy governance model for Classroom Token Hub (CTH).

This specification establishes:
- the Classroom Wage Index (`CWI`) system,
- policy-mode economic climates,
- pricing proportionality,
- savings and interest semantics,
- solvency constraints,
- analytics philosophy,
- rebalance governance,
- and canonical temporal execution rules.

The purpose of the CTH economy is to reinforce:
- participation,
- delayed gratification,
- planning,
- resilience,
- coordination,
- and bounded economic decision-making.

The economy is not intended to simulate unrestricted real-world capitalism.

---

# II. Scope

This specification applies to:
- economy recommendation systems,
- validation systems,
- pricing calculators,
- banking systems,
- analytics systems,
- rebalance workflows,
- recurring economy operations,
- and all CWI-relative financial modeling.

This specification governs:
- DOM economy systems,
- FEAT economy systems,
- analytics systems,
- and all runtime economy execution semantics.

---

# III. Authority Level

Constitutional (DOM Tier).

Subordinate to:
- `INV-CORE-000`
- `DOM-CORE-000`
- `INV-ARC-015`

No FEAT, SOP, runtime workflow, API surface, or UI behavior may override the invariants established in this document.

---

# IV. Core Principles

---

## 1. Labor Dominance Principle

Attendance-derived participation SHALL remain the dominant economic driver of the classroom economy.

Savings and interest systems MAY accelerate progression but SHALL NOT replace participation as the primary source of economic advancement.

---

## 2. CWI Relativity Principle

All economy calculations SHALL derive proportionally from the Classroom Wage Index (`CWI`).

Absolute economy values are prohibited.

---

## 3. Solvency Preservation Principle

Students with:
- perfect attendance,
- ordinary participation,
- and no savings behavior

SHALL remain economically viable under system-recommended settings.

---

## 4. Aggregate Analytics Principle

Analytics SHALL prioritize:
- classroom-level ecosystem health,
- aggregate participation trends,
- and system drift detection

rather than student ranking or comparative surveillance.

---

## 5. Deterministic Governance Principle

All economy systems SHALL:
- derive from canonical formulas,
- execute deterministically,
- remain replayable,
- and consume shared calculation logic.

Duplicated economy formulas are prohibited.

---

# V. Classroom Wage Index (CWI)

---

## 1. Definition

The Classroom Wage Index (`CWI`) represents the expected weekly income for a student with perfect attendance.

Canonical definition:

```text id="m8i8od"
CWI = expected weekly pay at full attendance
```

---

## 2. Canonical Derivation

### Hourly Payroll Model

```text
CWI =
    hourly_pay_rate *
    expected_hours_per_week
```

### Minute-Based Payroll Model

```text
CWI =
    minute_pay_rate *
    expected_minutes_per_week
```

---

## 3. Expected Work Duration

Expected work duration represents projected instructional participation time for a student with perfect attendance.

This value SHALL exist for:
- economy balancing,
- recommendation generation,
- solvency analysis,
- and analytics normalization.

Expected duration SHALL NOT retroactively mutate payroll history or earned wages.

---

# VI. Canonical Normalization Rules

All economy calculations SHALL normalize values to weekly equivalents before ratio comparison.

---

## 1. Monthly → Weekly

```text id="l8p8p7"
weekly_equivalent =
    monthly_value / 4.345
```

---

## 2. Semester → Weekly

```text id="u9z7wm"
weekly_equivalent =
    semester_value / semester_weeks
```

---

## 3. Daily → Weekly

```text id="n8zqzm"
weekly_equivalent =
    daily_value * instructional_days_per_week
```

---

# VII. Policy Mode Framework

---

## 1. Supported Policy Modes

The economy engine SHALL support exactly three policy modes:

```text
tight
default
comfortable
```

---

## 2. Economic Climate Definitions

### Tight
- survival-oriented
- constrained surplus
- slower savings growth
- higher economic pressure

### Default
- balanced
- moderate progression pacing
- moderate savings acceleration

### Comfortable
- aspirational
- lower economic pressure
- accelerated long-term progression

---

# VIII. Policy-Derived Ratio Bands

---

## 1. Weekly Savings Target

### Tight

```text id="p9v8m3"
weekly_savings_target =
    0.05 * CWI
```

### Default

```text id="lvw4s0"
weekly_savings_target =
    0.10 * CWI
```

### Comfortable

```text id="n5g6so"
weekly_savings_target =
    0.15 * CWI
```

---

## 2. Weekly Rent Ratio

### Tight

```text
recommended range:
    0.70 - 0.80
```

### Default

```text
recommended range:
    0.60 - 0.75
```

### Comfortable

```text
recommended range:
    0.50 - 0.65
```

Canonical formula:

```text
weekly_rent_ratio =
    weekly_rent / CWI
```

---

## 3. Utilities Ratio

Canonical formula:

```text
utilities_ratio =
    weekly_utilities / CWI
```

### Tight

```text
0.07 - 0.12
```

### Default

```text
0.05 - 0.10
```

### Comfortable

```text
0.04 - 0.08
```

---

## 4. Store Tier Ratios

Canonical formula:

```text
item_ratio =
    item_price / CWI
```

### Basic

```text
0.01 - 0.03 * CWI
```

### Standard

```text 
0.02 - 0.05 * CWI
```

### Premium

```text
0.05 - 0.15 * CWI
```

### Luxury

```text
0.15 - 0.30 * CWI
```

---

## 5. Insurance Premium Ratio

Canonical formula:

```text
premium_ratio =
    weekly_premium / CWI
```

### Tight

```text
0.06 - 0.14
```

### Default

```text
0.05 - 0.12
```

### Comfortable

```text 
0.04 - 0.10
```

---

## 6. Fine Ratio

Canonical formula:

```text 
fine_ratio =
    fine / CWI
```

### Tight

```text 
0.07 - 0.18
```

### Default

```text 
0.05 - 0.15
```

### Comfortable

```text
0.04 - 0.12
```

---

# IX. Collective Goals

---

## 1. Purpose

Collective goals exist to reinforce:
- cooperative participation,
- long-term planning,
- delayed gratification,
- and coordinated saving behavior.

---

## 2. Collective Goal Scaling

Canonical formula:

```text 
goal_ratio =
    goal_cost / CWI
```

### Tight

```text
0.75x - 7.0x weekly CWI
```

### Default

```text 
1.0x - 8.0x weekly CWI
```

### Comfortable

```text
1.5x - 10.0x weekly CWI
```

---

## 3. Goal Reachability Projection

```text 
projected_completion_weeks =
    remaining_goal_cost /
    projected_weekly_contribution
```

Projected contribution SHALL consider:
- active contributors,
- participation patterns,
- savings behavior,
- and instructional duration remaining.

---

# X. Savings & Interest System

---

## 1. Savings Philosophy

Savings systems exist to reinforce:
- delayed gratification,
- planning,
- resilience,
- and aspirational progression.

Savings SHALL NOT replace labor participation.

---

## 2. Compound Growth Formula

```text
A = P * (1 + r/n)^(n*t)
```

Where:
- `P` = eligible balance
- `r` = APY
- `n` = compounding periods per year
- `t` = years

---

## 3. Daily Accrual Formula

```text
daily_accrual =
    eligible_balance * (APR / 365)
```

---

## 4. Doubling-Time Constraint

Canonical doubling-time equation:

```text
2 = (1 + r/n)^(n*t)
```

Maximum APY derivation:

```text
r =
    n * (2^(1/(n*t)) - 1)
```

---

## 5. Minimum Doubling-Time Targets

### Tight

```text 
minimum doubling time = 6 years
```

### Default

```text 
minimum doubling time = 4 years
```

### Comfortable

```text 
minimum doubling time = 2 years
```

---

# XI. Solvency Validation

---

## 1. Budget Survival Test

Canonical formula:

```text 
weekly_savings =
    CWI
    - weekly_rent
    - weekly_insurance
    - average_store_cost
```

Constraint:

```text 
weekly_savings >=
    policy_minimum_savings_ratio * CWI
```

---

## 2. Catastrophe Stability Rule

Validators SHALL simulate:
- two fines,
- uninsured loss,
- and discretionary purchase behavior.

Students SHALL remain economically recoverable within one cycle under recommended configurations.

---

# XII. Analytics & Observability

---

## 1. Analytics Philosophy

Analytics SHALL answer:

> “Is the classroom economy behaving as designed?”

Analytics SHALL prioritize:
- aggregate classroom health,
- participation trends,
- and system drift detection.

---

## 2. Aggregation Boundary

The primary analytics aggregation boundary SHALL be:

```text 
class_id
```

Analytics SHALL default to:
- aggregate metrics,
- trend analysis,
- and ecosystem interpretation.

---

## 3. Analytics Categories

The analytics system SHALL support:

- Income & Solvency
- Economic Activity
- Savings & Long-Term Planning
- Resilience & Risk
- Drift & Stability

---

## 4. Canonical Metrics

### Obligation Coverage Ratio

```text 
obligation_coverage_ratio =
    students_meeting_obligations /
    total_students
```

### Savings Participation Rate

```text 
savings_participation_rate =
    students_with_positive_savings /
    total_students
```

### Insurance Adoption Rate

```text 
insurance_adoption_rate =
    insured_students /
    total_students
```

### Passive Income Ratio

```text
passive_income_ratio =
    interest_income /
    labor_income
```

### Money Velocity

```text 
money_velocity =
    total_economic_transactions /
    average_money_supply
```

---

# XIII. Canonical Temporal Rules

---

## 1. Classroom Timezone Authority

Each classroom SHALL possess exactly one authoritative IANA timezone.

Examples:

```text 
America/Los_Angeles
America/New_York
Asia/Tokyo
```

This timezone SHALL govern:
- settlement windows,
- accrual timing,
- analytics aggregation,
- payroll cycles,
- and recurring economy execution.

---

## 2. UTC Storage Rule

All timestamps SHALL:
- store internally in UTC,
- and resolve operational meaning using the classroom timezone.

---

## 3. Canonical Day Boundary

```text
canonical_day_boundary =
    00:00:00 in classroom timezone
```

---

## 4. Savings Accrual Window

```text 
daily_accrual_window =
    previous_class_midnight
    →
    current_class_midnight
```

---

## 5. Forbidden Temporal Patterns

The following are prohibited:
- UTC calendar shortcuts
- browser-local authoritative timing
- hardcoded Pacific Time assumptions
- floating settlement windows
- mixed-timezone economy aggregation

---

# XIV. Validation & Execution Rules

---

## 1. Deterministic Calculation Requirement

All:
- validators,
- recommendation engines,
- analytics systems,
- rebalance workflows,
- and policy previews

SHALL consume the same canonical calculation layer.

Duplicated economy formulas are prohibited.

---

## 2. Teacher Override Constraints

Teacher overrides MAY exceed recommendation bands only when:
- solvency remains preserved,
- savings-growth constraints remain valid,
- and constitutional invariants remain satisfied.

---

## 3. Forbidden Calculation Patterns

The following are prohibited:
- duplicated economy formulas
- hardcoded APY defaults outside policy layer
- non-normalized monthly comparisons
- historical-deposit-only savings eligibility
- direct UI-side authoritative calculations
- hidden economic multipliers
- non-CWI-relative economy derivation

---

# XV. Delegation to DOM-ECON-003

Policy transition governance — including the mechanics of creating, activating, superseding, and cancelling economic policy transitions — is delegated to `DOM-ECON-003_ECONOMIC_POLICY_AND_TRANSITION.md`.

`DOM-ECON-003` supersedes this document with respect to:
- Policy transition creation, activation, and supersession semantics
- Hidden delayed mutation patterns (prohibited)
- Mutable singleton policy truth (prohibited)

This document remains sole authority for:
- Classroom Wage Index (CWI) definition and canonical derivation
- Policy mode ratio bands (tight / default / comfortable)
- Savings and interest formulas and doubling-time constraints
- Solvency validation rules
- Analytics categories and canonical metrics
- Canonical normalization rules

Implementations requiring policy transition behavior MUST consult `DOM-ECON-003`, not this document.

---

# XVI. Amendment

Revisions to this document SHALL:
1. increment the version number,
2. update the Effective Date,
3. preserve constitutional compatibility,
4. maintain consistency with higher-authority invariant documents,
5. maintain consistency with `DOM-ECON-003` for transition governance boundaries,
6. and preserve deterministic economy governance semantics.
