---
# DOM-ECON-002: Economy Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|DOM-ECON-002| 1.1 | 2026-03-08 | 1.0 |Constitutional|

## I. Purpose

This document defines the formulas, constraints, ratios, and rules used by automated tools when generating or modifying monetary values in the Classroom Economy App.

## II. Scope

This specification applies to all economy-related calculations, including price calculators, inflation engines, rent generators, insurance logic, and economic simulation events. In this document, "agents" refers to automated tools and internal workflows.

## III. Authority Level

Constitutional (DOM Tier). Subordinate to INV-CORE-000.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`

## V. Core Reference Variable

All monetary outputs must derive from:

### CWI (Classroom Wage Index)

```
CWI = expected week_total_pay for a student who attends all sessions
```

Agents must compute or retrieve CWI before evaluating any cost structure.

---

## VI. Standard Pricing Ratios

Agents must follow the ratios below unless explicitly overridden by a rule or teacher input.

### 1. Rent

```
rent_min = 2.0 * CWI
rent_max = 2.5 * CWI
default_rent = 2.25 * CWI
```

### 2. Utilities / Property Tax / Fixed Fees

```
utilities_min = 0.20 * CWI
utilities_max = 0.30 * CWI
default_utilities = 0.25 * CWI
```

### 3. Store Item Pricing Tiers

Agents must classify item tiers based on requested purpose:

```
BASIC:        0.02–0.05 * CWI
STANDARD:     0.05–0.10 * CWI
PREMIUM:      0.10–0.25 * CWI
LUXURY:       0.25–0.50 * CWI
```

If a teacher does not specify a tier, agents infer based on item description tags.

---

## VII. Insurance Structure

### 1. Premium Calculation

```
premium_min = 0.05 * CWI
premium_max = 0.12 * CWI
default_premium = 0.08 * CWI
```

### 2. Coverage Boundaries

```
coverage_min = premium * 3
coverage_max = premium * 5
default_coverage = premium * 4
```

If a teacher specifies coverage exceeding 5× premium, agents must warn or request confirmation.

### 3. Period Payout Cap

```
period_cap_min = premium * 6
period_cap_max = premium * 10
default_period_cap = premium * 8
```

If a teacher sets the period cap outside 6–10× premium, agents must warn or request confirmation.

---

## VIII. Fines

```
fine_min = 0.05 * CWI
fine_max = 0.15 * CWI
default_fine = 0.10 * CWI
```

Agents must apply proportional scaling across all fines.

---

## IX. Inflation & Economic Events

Agents must implement inflation as a **percentage multiplier** applied to all price categories simultaneously unless selective inflation is intentionally triggered.

### 1. Inflation Formula

```
new_price = old_price * (1 + inflation_rate)
```

### 2. Valid inflation ranges

```
mild:      0.01–0.03
moderate:  0.03–0.06
severe:    0.06–0.10
```

Agents must:

* Adjust store, rent, utilities, and insurance premiums uniformly unless instructed otherwise.
* Prevent student insolvency by analyzing affordability thresholds (see section 8).

---

## X. Savings Interest Guidance

Savings interest is an engagement incentive, not a CWI-based ratio. Use modest ranges to avoid overpowering wages.

```
apy_min = 0.06
apy_max = 0.18
default_apy = 0.10–0.12

monthly_rate_min = 0.005
monthly_rate_max = 0.015
default_monthly_rate = 0.010
```

If a teacher sets rates outside these ranges, agents should warn or request confirmation.

---

## XI. Affordability Constraints (Global Rule)

Agents must validate economic stability:

### 1. Budget Survival Test

A student with perfect attendance must be able to:

```
weekly_savings = CWI - (rent/number_of_weeks_in_month) - utilities - average_store_cost
weekly_savings >= 0.10 * CWI
```

If not, agents must lower rent or fines, or increase wages.

### 2. Catastrophe Test

A student experiencing:

* two fines
* loss of insurance
* unexpected store need

…must **not** fall below zero balance for more than one cycle.
Agents adjust or warn as needed.

---

## XII. Output Requirements

All agent-generated values must:

* list **inputs** used
* list **ratios applied**
* show **resulting calculated values**
* include **justification using this specification**
* surface warnings when constraints are violated

Agents should *never* output arbitrary values without referencing this framework.

For application runtime behavior, the backend implementation of these recommendation ratios shall be centralized in `app/utils/economy_policy.py`. Routes, templates, APIs, and background jobs must consume that shared helper rather than recreating formulas.

---

## XIII. Non-Negotiable Design Rules

Agents must always enforce:

1. All monetary values scale from CWI.
2. All pricing must follow ratio bands unless overridden.
3. Economic operations must preserve student solvency.
4. Every tool must calculate and surface impacts before applying changes.
5. All inflation and economy tools must maintain coherent proportionality across categories.

## XIV. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `DOM-CORE-000`.
