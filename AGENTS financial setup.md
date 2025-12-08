# Classroom Economy Monetary System — Agent Specification

This document defines the **formulas, constraints, ratios, and rules** agents must follow when generating or modifying monetary values in the Classroom Economy App.

This specification ensures consistent, predictable behavior across tools such as:

* price calculators
* inflation engines
* rent generators
* insurance logic
* loan approval systems
* economic simulation events

---

## 1. Core Reference Variable

All monetary outputs must derive from:

### CWI (Classroom Wage Index)

```
CWI = expected week_total_pay for a student who attends all sessions
```

Agents must compute or retrieve CWI before evaluating any cost structure.

---

## 2. Standard Pricing Ratios

Agents must follow the ratios below unless explicitly overridden by a rule or teacher input.

### 2.1 Rent

```
rent_min = 2.0 * CWI
rent_max = 2.5 * CWI
default_rent = 2.25 * CWI
```

### 2.2 Utilities / Property Tax / Fixed Fees

```
utilities_min = 0.20 * CWI
utilities_max = 0.30 * CWI
default_utilities = 0.25 * CWI
```

### 2.3 Store Item Pricing Tiers

Agents must classify item tiers based on requested purpose:

```
BASIC:        0.02–0.05 * CWI
STANDARD:     0.05–0.10 * CWI
PREMIUM:      0.10–0.25 * CWI
LUXURY:       0.25–0.50 * CWI
```

If a teacher does not specify a tier, agents infer based on item description tags.

---

## 3. Insurance Structure

### 3.1 Premium Calculation

```
premium_min = 0.05 * CWI
premium_max = 0.12 * CWI
default_premium = 0.08 * CWI
```

### 3.2 Coverage Boundaries

```
coverage_min = premium * 3
coverage_max = premium * 5
default_coverage = premium * 4
```

If a teacher specifies coverage exceeding 5× premium, agents must warn or request confirmation.

---

## 4. Fines

```
fine_min = 0.05 * CWI
fine_max = 0.15 * CWI
default_fine = 0.10 * CWI
```

Agents must apply proportional scaling across all fines.

---

## 5. Inflation & Economic Events

Agents must implement inflation as a **percentage multiplier** applied to all price categories simultaneously unless selective inflation is intentionally triggered.

### 5.1 Inflation Formula

```
new_price = old_price * (1 + inflation_rate)
```

### Valid inflation ranges

```
mild:      0.01–0.03
moderate:  0.03–0.06
severe:    0.06–0.10
```

Agents must:

* Adjust store, rent, utilities, and insurance premiums uniformly unless instructed otherwise.
* Prevent student insolvency by analyzing affordability thresholds (see section 8).

---

## 6. Loan and APR Rules

### 6.1 Risk Bands

```
low_risk_apr:      0.08–0.15
medium_risk_apr:   0.15–0.35
high_risk_apr:     0.35–0.50
```

### 6.2 Payment Rule

All loans must use:

```
installment_period = teacher_selected_pay_cycle
```

Agents must reject loans where:

* Required installments exceed 40% of expected weekly earnings.
* Student net budget after loan would become negative for >2 consecutive cycles.

---

## 7. Investment Tools

Agents must categorize investments based on risk and lock-in rules:

### 7.1 CDs

```
cd_rate = inflation_rate + 0.01–0.03
lock_in_required = TRUE
```

### 7.2 Bonds

```
bond_rate = inflation_rate + 0.00–0.02
low_variance = TRUE
```

### 7.3 Stocks

```
stock_change ∈ [-0.30, +0.30] random or event-driven
risk_flag = HIGH
```

---

## 8. Affordability Constraints (Global Rule)

Agents must validate economic stability:

### 8.1 Budget Survival Test

A student with perfect attendance must be able to:

```
weekly_savings = CWI - (rent/number_of_weeks_in_month) - utilities - average_store_cost
weekly_savings >= 0.10 * CWI
```

If not, agents must lower rent or fines, or increase wages.

### 8.2 Catastrophe Test

A student experiencing:

* two fines
* loss of insurance
* unexpected store need

…must **not** fall below zero balance for more than one cycle.
Agents adjust or warn as needed.

---

## 9. Output Requirements

All agent-generated values must:

* list **inputs** used
* list **ratios applied**
* show **resulting calculated values**
* include **justification using this specification**
* surface warnings when constraints are violated

Agents should *never* output arbitrary values without referencing this framework.

---

## 10. Non-Negotiable Design Rules

Agents must always enforce:

1. All monetary values scale from CWI.
2. All pricing must follow ratio bands unless overridden.
3. Economic operations must preserve student solvency.
4. Every tool must calculate and surface impacts before applying changes.
5. All inflation, investment, and loan tools must maintain coherent proportionality across categories.
