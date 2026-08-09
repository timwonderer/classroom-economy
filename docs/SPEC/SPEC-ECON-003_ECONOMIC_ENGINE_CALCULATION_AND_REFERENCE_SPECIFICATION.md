# SPEC-ECON-003: Economic Engine Calculation and Reference Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-ECON-003    |  1.0    |     2026-08-09 |       None |       Normative |

---

## 1. Purpose

This specification is the single canonical technical source for the Economic Engine's calculations and reference values.

The Economic Engine exists to remove pricing guesswork from classroom economy setup by deriving coherent numbers from class context instead of requiring teachers to invent them manually.

This document defines the canonical calculations, ratios, bands, and constraints used by the engine.

---

## 2. Scope

This specification governs:

- CWI derivation,
- policy-mode ratio bands,
- Store pricing tiers,
- weekly savings targets,
- interest doubling-time constraints,
- interest-growth formulas,
- economic solvency and coherence checks,
- deterministic reference values used by the engine.

This specification does NOT govern:

- class identity,
- class existence,
- policy lineage,
- FEAT orchestration,
- ledger posting,
- execution timing,
- or feature activation mechanics.

Those responsibilities remain with the relevant `DOM-*`, `SPEC-*`, and `FEAT-*` documents.

---

## 3. Governing Authority

This specification is subordinate to:

- `INV-CORE-000`
- `INV-CORE-001`
- `INV-ARC-009`
- `INV-ARC-015`
- `DOM-CORE-001`
- `DOM-CLASS-001`
- `DOM-CLASS-002`
- `DOM-CLASS-003`
- `SPEC-ECON-001`
- `SPEC-ECON-002`

This specification is authoritative over:

- the Economic Engine's calculation model,
- the canonical economic reference values,
- the banding rules used for class-economic recommendations,
- the derivation constraints for teacher-facing output.

---

## 4. Core Calculations

### 4.1 Classroom Wage Index

The Classroom Wage Index (`CWI`) is the base weekly economic reference for a class.

`CWI` SHALL be derived from expected weekly earning capacity.

Canonical definition:

```text
CWI = hourly_pay_rate × expected_weekly_hours
```

Where:

- `hourly_pay_rate` is the canonical pay rate for the class configuration.
- `expected_weekly_hours` is the expected number of earning hours available in a typical week.

`CWI` is the normalization base for all ratio-based economic outputs in this specification.

---

### 4.2 Weekly Savings Target

The engine SHALL provide a canonical weekly savings target as a percentage of `CWI`.

| Economic Mode | Weekly Savings Target |
| --- | ---: |
| `tight` | 5% of CWI |
| `default` | 10% of CWI |
| `comfortable` | 15% of CWI |

Formula:

```text
weekly_savings_target = CWI × savings_rate
```

---

### 4.3 Weekly Rent

The engine SHALL provide a canonical weekly rent band as a percentage of `CWI`.

| Economic Mode | Weekly Rent Band |
| --- | ---: |
| `tight` | 70% to 80% of CWI |
| `default` | 60% to 75% of CWI |
| `comfortable` | 50% to 65% of CWI |

Formula:

```text
weekly_rent = CWI × rent_rate
```

with `rent_rate` constrained to the mode-specific band.

---

### 4.4 Utilities

The engine SHALL provide a canonical utilities band as a percentage of `CWI`.

| Economic Mode | Utilities Band |
| --- | ---: |
| `tight` | 7% to 12% of CWI |
| `default` | 5% to 10% of CWI |
| `comfortable` | 4% to 8% of CWI |

Formula:

```text
utilities = CWI × utilities_rate
```

---

### 4.5 Insurance Premium

The engine SHALL provide a canonical insurance premium band as a percentage of `CWI`.

| Economic Mode | Insurance Premium Band |
| --- | ---: |
| `tight` | 6% to 14% of CWI |
| `default` | 5% to 12% of CWI |
| `comfortable` | 4% to 10% of CWI |

Formula:

```text
insurance_premium = CWI × premium_rate
```

---

### 4.6 Fines

The engine SHALL provide a canonical fine band as a percentage of `CWI`.

| Economic Mode | Fine Band |
| --- | ---: |
| `tight` | 7% to 18% of CWI |
| `default` | 5% to 15% of CWI |
| `comfortable` | 4% to 12% of CWI |

Formula:

```text
fine = CWI × fine_rate
```

---

### 4.7 Collective Goals

The engine SHALL provide a canonical collective-goal band as a multiple of `CWI`.

| Economic Mode | Collective Goal Band |
| --- | ---: |
| `tight` | 0.75× to 7× CWI |
| `default` | 1× to 8× CWI |
| `comfortable` | 1.5× to 10× CWI |

Formula:

```text
collective_goal = CWI × goal_multiple
```

---

### 4.8 Store Pricing Tiers

Store pricing is tier-based rather than policy-mode-based.

| Store Tier | Recommended Price Band |
| --- | ---: |
| Basic | 1% to 3% of CWI |
| Standard | 2% to 5% of CWI |
| Premium | 5% to 15% of CWI |
| Luxury | 15% to 30% of CWI |

Formula:

```text
store_price = CWI × tier_rate
```

where `tier_rate` is constrained by the selected store tier.

---

## 5. Interest Calculations

### 5.1 Purpose of Interest Constraints

Interest MUST remain meaningful without becoming a passive-income money printer.

The canonical constraint is not an arbitrary APY cap. It is a minimum doubling-time rule.

### 5.2 Doubling-Time Rule

The engine SHALL enforce the following minimum doubling times:

| Economic Mode | Minimum Doubling Time |
| --- | ---: |
| `tight` | 6 years |
| `default` | 4 years |
| `comfortable` | 2 years |

Interest rates and compounding settings MUST NOT allow savings to double faster than the configured mode permits.

### 5.3 Compound Growth Formula

Canonical compound growth:

```text
A = P × (1 + r/n)^(n×t)
```

Where:

- `A` is the future amount,
- `P` is the principal,
- `r` is the annual rate,
- `n` is the compounding frequency per year,
- `t` is time in years.

### 5.4 Doubling-Time Rearrangement

To calculate the maximum lawful rate for a given doubling-time target:

```text
2 = (1 + r/n)^(n×t)
```

Therefore:

```text
r = n × (2^(1/(n×t)) - 1)
```

Where:

- `t` is the minimum allowed doubling time in years,
- `n` is the compounding frequency per year.

### 5.5 Daily Accrual

For daily accrual, the engine SHALL use a daily rate derived from the annual rate.

Canonical form:

```text
daily_accrual = eligible_balance × (APR / 365)
```

Equivalent formulations MAY be used only if they are mathematically identical and deterministic.

### 5.6 Compound Frequency Persistence

The `EconomicEngine.compound_frequency` field persists the compound frequency choice per SPEC-ECON-001 § 6.1.

Supported values:

| Value | Semantics | Persistence |
| --- | --- | --- |
| `never` | Simple interest; accrued interest never participates | `compound_frequency = 'never'` |
| `daily` | Compounds daily | `compound_frequency = 'daily'` |
| `weekly` | Compounds weekly | `compound_frequency = 'weekly'` |
| `monthly` | Compounds monthly | `compound_frequency = 'monthly'` |
| `NULL` | No compounding configured (engine not initialized for interest) | `compound_frequency IS NULL` |

Implementations that consume this field MUST validate against the persisted enum constraint:

```sql
CHECK (compound_frequency IS NULL OR compound_frequency IN ('never', 'daily', 'weekly', 'monthly'))
```

---

## 6. Normalization Rules

### 6.1 Weekly Basis

All ratio comparisons in this specification SHALL normalize to a weekly comparison basis unless explicitly stated otherwise.

### 6.2 Class-Relative Comparison

All values SHALL be derived relative to `CWI`.

Absolute economy values with no class-relative basis are prohibited as canonical reference values.

---

## 7. Economic Coherence Rules

### 7.1 Relational Values

The engine MUST keep values proportional to one another.

Examples:

- rent must not be so high that routine savings become impossible,
- store prices must preserve multiple tiers of affordability,
- insurance must create a meaningful tradeoff,
- goals must require sustained effort,
- interest must reward savings without overtaking labor as the dominant money source.

### 7.2 Rebalance Consistency

If the class economy changes, affected outputs MUST be recalculated together.

The engine MUST NOT allow related values to drift independently.

### 7.3 Determinism

The same authoritative inputs MUST produce the same outputs.

Duplicated formulas, hidden overrides, and implementation-specific recalculation paths are prohibited.

---

## 8. Canonical Economic Reference Table

The following table is the canonical reference set for the Economic Engine.

| Measure | Tight | Default | Comfortable |
| --- | ---: | ---: | ---: |
| Weekly savings target | 5% CWI | 10% CWI | 15% CWI |
| Weekly rent | 70% to 80% CWI | 60% to 75% CWI | 50% to 65% CWI |
| Utilities | 7% to 12% CWI | 5% to 10% CWI | 4% to 8% CWI |
| Insurance premium | 6% to 14% CWI | 5% to 12% CWI | 4% to 10% CWI |
| Fine | 7% to 18% CWI | 5% to 15% CWI | 4% to 12% CWI |
| Collective goal | 0.75x to 7x CWI | 1x to 8x CWI | 1.5x to 10x CWI |

Store tier reference:

| Tier | Price Band |
| --- | ---: |
| Basic | 1% to 3% CWI |
| Standard | 2% to 5% CWI |
| Premium | 5% to 15% CWI |
| Luxury | 15% to 30% CWI |

Interest reference:

| Mode | Maximum Growth Behavior |
| --- | --- |
| `tight` | money cannot double faster than 6 years |
| `default` | money cannot double faster than 4 years |
| `comfortable` | money cannot double faster than 2 years |

---

## 9. Prohibited Patterns

The engine MUST NOT:

- use arbitrary fixed prices unrelated to `CWI`,
- recompute one value without updating dependent values,
- mix store tier pricing with policy-mode pricing,
- let interest exceed the doubling-time constraint,
- allow hidden or undocumented formulas to become canonical,
- duplicate these calculations in consuming code as alternate authority.

---

## 10. Relationship to Other Documents

`DOM-CLASS-001` owns the class boundary and the `economic-engine` table.

`DOM-CLASS-002` owns the class-economy posture and supported modes.

`DOM-CLASS-003` owns economics policy lineage and activation legality.

`SPEC-ECON-001` owns savings-interest runtime semantics.

`SPEC-ECON-002` owns disclosure and visibility requirements.

This document owns the technical calculations and reference values used by the Economic Engine.

---

## 11. Amendment

Revisions to this document must:

1. preserve the recovered calculation set,
2. keep the table and formulas deterministic,
3. remain consistent with the class-economy authority chain.
