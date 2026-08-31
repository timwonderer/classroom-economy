# SPEC-ECON-003: Economic Engine Calculation and Reference Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-ECON-003    |  1.4    |     2026-08-30 |        1.3 |       Normative |

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
- the insurance **premium pricing envelope** and the separation of premium pricing (economic-mode axis) from coverage contract (insurance-tier axis) for the three canonical insurance products,
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

### 4.5 Insurance

Insurance is not a single product. `FEAT-STOR-003` defines three canonical insurance
products, each with a distinct claim lifecycle and therefore a distinct economic
reference model:

- `TRANSACTION`
- `PRODUCTIVITY`
- `NON_MONETARY`

This section is referenced to `FEAT-STOR-003` **only** to establish why the Economic
Engine must model these three products separately. `FEAT-STOR-003` remains authoritative
over claim submission, validation, approval, and compensation execution. This
specification is authoritative only over the CWI-relative economic reference values used
to price and bound insurance.

#### 4.5.1 Two Independent Axes

Insurance economics are governed by two axes that MUST be kept separate:

1. **Insurance tier (coverage axis).** For products that use tiers, `Basic`, `Mid`, and
   `Premium` define the insurance **contract / benefit** — what the policy covers and its
   coverage limits. Tier is the coverage axis.

2. **Economic policy mode (pricing axis).** `tight`, `default`, and `comfortable` affect
   the recommended **premium** — what the coverage costs. Economic mode is the pricing
   axis.

**Axis-separation rule (normative).** Economic mode governs **pricing recommendations**
only. Product and tier configuration govern **coverage parameters** only. Economic mode
MUST NOT silently change any configured coverage parameter — reimbursement percentage,
payout multiple, claim allowance, maximum claimed basis, waiting period, or coverage
boundary. For example, if a `Premium PRODUCTIVITY` definition reimburses X% of validated
lost wages, X% is identical in `tight`, `default`, and `comfortable`.

**Derived monetary exposure is not a coverage parameter.** For monetary products whose
ceiling is derived as `maximum_policy_payout = premium × payout_multiple`, economic mode
legitimately changes the resulting dollar ceiling **because it changed the premium**, which
is an economic input. This is intentional and is not a violation of the axis-separation
rule. What mode MUST NOT change is the configured `payout_multiple` (or reimbursement %,
claim allowance, etc.) itself. Consequently, this specification does **not** claim that a
given tier yields the same dollar benefit across modes — only the same *coverage
parameters*.

Depending on product type, tier-controlled (coverage-axis) values MAY include:

- reimbursement percentage;
- payout multiple (where the ceiling is derived as `premium × payout_multiple`);
- claim allowance;
- maximum claim basis;
- maximum payout;
- waiting period;
- other product-specific coverage limits.

The exact numerical coverage values for each tier are defined per product in the canonical
preset tables (§ 4.5.3–§ 4.5.5), selected deterministically per § 4.5.8. Implementations MUST
source them from this document and MUST NOT invent or override them.

#### 4.5.2 Premium Pricing Envelope (economic-mode axis)

The engine SHALL price insurance premiums CWI-relative, within the canonical mode-specific
premium envelope:

| Economic Mode | Insurance Premium Band |
| --- | ---: |
| `tight` | 6% to 14% of CWI |
| `default` | 5% to 12% of CWI |
| `comfortable` | 4% to 10% of CWI |

These bands are the recommended pricing envelope for insurance premium recommendations
across all three products and all tiers. Teachers MAY configure a premium outside the
recommended band; the band is engine guidance, not a hard cap.

Constraints on premium derivation:

- premium pricing MUST be CWI-relative;
- economic mode determines the lawful/recommended premium envelope;
- product and tier coverage determine the benefit contract, never the premium envelope;
- the recommended premium MUST be deterministic;
- the premium is an economic **input** that MAY, for monetary products, feed a derived
  payout ceiling (`maximum_policy_payout = premium × payout_multiple`).

The envelope is **not independently immutable**. It is contingent on the coverage models it
prices, and it MUST be re-evaluated as each product's coverage economics are settled:

- `PRODUCTIVITY` — coverage model is now sufficiently settled (§ 4.5.4) that the envelope
  can be tested against real exposure. The hard weekly boundaries in § 4.5.4 bound exposure
  independently of the premium.
- `TRANSACTION` — coverage economics remain unresolved (§ 4.5.6); the envelope is
  provisional for this product until they are settled.
- `NON_MONETARY` — the envelope is **affordability guidance only**, not an exposure-based
  price (§ 4.5.5).

The deterministic premium-selection rule for the canonical presets is defined in § 4.5.8.
No `risk_factor`, `premium = liability × risk_factor`, or equivalent exposure-multiplier
formula is canonical under this specification; the preset premium is selected directly from
the mode band by tier (band bottom / midpoint / top).

**Coverage period normalization (all period-priced products).** The premium envelope above
is expressed per canonical week. When a policy's coverage period is longer than one week,
period-level economic values scale by the **actual** duration of the coverage interval, not
by a fixed constant.

Monthly coverage MUST NOT be defined as a fixed 4-week economic period. A monthly policy
runs from one canonical renewal boundary to the next; its economic week-equivalent is
derived from the actual number of class-local calendar days in that interval:

```text
coverage_week_equivalent = covered_class_local_calendar_days / 7
```

The coverage interval is **half-open**: `[coverage_start, next_renewal)`. The start day is
covered; the next renewal boundary belongs to the following cycle and is not double-counted.
For the Aug 25 → Sep 25 example this yields 31 covered class-local calendar days (Aug 25
through Sep 24 inclusive), with Sep 25 opening the next cycle.

Weekly coverage has a `coverage_week_equivalent` of exactly `1`.

Period-normalized values then derive from the actual duration, e.g.:

```text
period_premium        = weekly_equivalent_premium × coverage_week_equivalent
maximum_policy_payout = period_premium × payout_multiple      # where applicable
```

Example: a policy renewing August 25 → September 25 covers 31 class-local days, so
`coverage_week_equivalent = 31 / 7 ≈ 4.4286`.

Covered-day derivation and renewal boundaries MUST use canonical class-local temporal
resolution — never elapsed seconds — so that DST or timezone transitions do not distort the
economic period.

The upcoming renewal period MUST be calculable before renewal. Student-facing insurance UI
SHALL surface the next coverage interval, the next premium, and other derived renewal values
ahead of the charge so students can plan for renewal.

#### 4.5.3 `TRANSACTION` Insurance

`TRANSACTION` insurance reimburses part of a single posted Ledger transaction. Consistent
with `FEAT-STOR-003`, one claim covers exactly one canonical Ledger transaction. Its
monetary model mirrors `PRODUCTIVITY`: reimbursement is a percentage of the covered
transaction loss, the period ceiling is `period_premium × payout_multiple`, and premiums are
selected from the mode band per § 4.5.8.

Canonical preset values (per week-equivalent; scale monthly per § 4.5.2):

| Parameter | Single | Basic | Mid | Premium | Teacher recommended range |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reimbursement % | 60% | 40% | 60% | 80% | 30–90% |
| Payout multiple | 4× | 3× | 4× | 5× | 2×–7× |
| Claims / week-equivalent | 2 | 1 | 2 | 3 | 1–3 |
| Claim window | 7 days | 3 days | 7 days | 14 days | 1–14 days |
| Tight premium | 10% CWI | 6% | 10% | 14% | 6–14% CWI |
| Default premium | 8.5% CWI | 5% | 8.5% | 12% | 5–12% CWI |
| Comfortable premium | 7% CWI | 4% | 7% | 10% | 4–10% CWI |

**Eligibility hard contract (non-overridable).** Independent of the tier/coverage values,
a `TRANSACTION` claim is eligible only when the referenced transaction is:

- a negative (debit) transaction;
- inside the configured filing window;
- not on CTH's global disallowed list;
- not previously claimed;
- not obligation-related;
- not collective-goal-related;
- not a transfer;
- and, when item-related, tied to an item/entitlement that was actually purchased **and
  used**, but **not revoked or expired**.

These are mechanical eligibility gates only; the teacher retains approval authority per
`FEAT-STOR-003`.

#### 4.5.4 `PRODUCTIVITY` Insurance

`PRODUCTIVITY` is the canonical product name for attendance / lost-wage insurance.

Its purpose is to reimburse some portion of wages the covered student could potentially
have earned on eligible class-local dates where the student had **no clock-in /
productivity session**. It compensates the economic consequence of lost productivity; it
does **not** assert that the student actually worked the claimed hours.

Intended claim model (economic reference view; execution semantics remain in
`FEAT-STOR-003`):

1. Student selects an otherwise eligible class-local date with **no clock-in / productivity
   session**.
2. Student enters the number of hours being claimed for that date.
3. Backend validates the claim against the configured insurance contract and authoritative
   Productivity / Payroll facts.
4. The teacher retains approval / rejection authority as defined by `FEAT-STOR-003`.
5. Approval compensates through the canonical `MANUAL_CREDIT` lifecycle.
6. Historical attendance, productivity sessions, worked minutes, and ordinary payroll
   remain unchanged.

**Loss and reimbursement basis.** CTH does **not** derive a daily wage and does **not**
divide CWI across an assumed number of school days. Validated loss is computed directly
from the student's own claimed hours:

```text
validated_claimed_loss = validated_claimed_hours × hourly_pay_rate
reimbursement          = validated_claimed_loss × reimbursement_percentage
```

**Payout ceiling.** The policy's payout ceiling is derived from the premium:

```text
maximum_policy_payout = premium × payout_multiple
```

**Effective payout (period capacity is the monetary ceiling).** A single approval's actual
payout is bounded by the insurance-contract period ceiling:

```text
actual_payout = min(
    gross_reimbursement,               # validated_claimed_loss × reimbursement_percentage
    remaining_period_payout_capacity   # insurance-contract ceiling (period)
)
```

The **period** capacity is the insurance-contract ceiling (derived from
`maximum_policy_payout`, period-normalized per § 4.5.2) and is the monetary ceiling on any
single approval's payout. Approval-time payout bounding — including the two-resource rule
(remaining claim allowance and remaining period payout capacity) — is execution semantics
owned by `FEAT-STOR-003` per the scope boundary in § 4.5; this specification states the
CWI-relative economic reference values only and does not impose an additional approval-time
weekly payout clamp.

**Engine-recommended, teacher-configurable.** The Engine recommends ranges for the
reimbursement percentage, payout multiple, premium, and other applicable limits. Teachers
MAY configure values outside the recommended ranges.

**Economic-coherence guidance (advisory).** The following are CWI-relative economic
reference comparisons. They are advisory guidance — surfaced to inform the teacher and the
student, not enforced as approval-time or submission-time denials by this specification:

- comparing `total_validated_PRODUCTIVITY_claimed_hours_week` against `expected_weekly_hours`
  within a canonical class-local week yields a non-blocking guidance signal when exceeded;
- comparing cumulative `PRODUCTIVITY` payout against `CWI` within a canonical class-local
  week is an economic-coherence reference, not a payout clamp;
- unused weekly guidance capacity does **not** carry forward.

The mechanical submission-time hours ceiling is the configured daily payroll limit, applied
at submission per `FEAT-STOR-003`. The monetary ceiling on payout is the remaining period
payout capacity (above). The `expected_weekly_hours` / `CWI` comparisons above do not add a
further mechanical cap.

**Actual worked hours do NOT invalidate a claim.** `expected_weekly_hours` is an
Economic Engine input and economic-coherence guidance. It is **not** proof that a student
could not have earned additional hours in a given week. CTH SHALL NOT automatically compute
`actual_worked_hours + claimed_lost_hours <= expected_weekly_hours` and reject or reduce a
claim on that basis. The weekly comparison against `expected_weekly_hours` is advisory
guidance surfaced to the deciding teacher, not a mechanical cap; recorded worked hours are
separate authoritative facts that inform adjudication.

Example: a student with 4 recorded worked hours this week, `expected_weekly_hours = 5`, who
selects an eligible no-session date and claims 3 lost hours, MUST NOT be auto-rejected
merely because `4 + 3 > 5`. Instead CTH surfaces authoritative context to the deciding
teacher — claimed lost hours, recorded worked hours for the canonical week, configured
`expected_weekly_hours`, requested/derived reimbursement, and applicable policy limits — and
the teacher decides whether the counterfactual lost-hour claim is credible. This is
consistent with the lifecycle rule that mechanical eligibility lets a claim be considered
but never mandates approval. CTH enforces objective limits and surfaces evidence; it does
not convert an economic modeling input into an automated judgment about whether the claimed
lost opportunity actually existed.

**Coverage period.** Coverage may be weekly or monthly. Monthly period pricing follows the
week-equivalent normalization in § 4.5.2. A monthly policy's total ceiling is expected to
exceed `1× CWI` because the interval spans multiple week-equivalents; this is valid. The
weekly economic-coherence guidance above is evaluated **independently within each canonical
class-local week** — a larger monthly ceiling does not change the per-week `expected_weekly_hours`
or weekly `CWI` reference comparisons, which remain advisory in any individual week.

**Tiering is optional.** A teacher MAY offer a single `PRODUCTIVITY` configuration or a
`Basic` / `Mid` / `Premium` set. `payout_multiple` belongs **exclusively** to the
product/tier coverage axis: a single offering configures one multiple; a tiered offering
gives each tier its own recommended/configured multiple. Economic mode SHALL NOT derive,
alter, or select `payout_multiple`. Economic mode affects only the premium recommendation;
the derived monetary ceiling (`premium × payout_multiple`) may therefore change with mode
because the premium changed — this is intentional and is not a change to the coverage
parameter.

**Recommendation coherence.** The Engine SHOULD avoid internally nonsensical
recommendations, distinguishing the policy-period ceiling from the weekly `CWI` economic
reference:

- **Weekly coverage** — a recommended premium/multiple combination SHOULD NOT normally imply
  a policy ceiling above the weekly `CWI` payout reference.
- **Monthly coverage** — a total ceiling above `1× CWI` is expected and valid; the weekly
  `CWI` reference is still evaluated independently inside the period.

Teachers MAY configure outside Engine recommendations. If a teacher's selected
premium/multiple yields a nominal policy ceiling above what the remaining period payout
capacity could actually pay, CTH MUST NOT silently rewrite the configuration; it MUST
surface both the calculated dollar policy ceiling and the applicable weekly `CWI` reference
clearly.

Canonical preset values (per week-equivalent; scale monthly per § 4.5.2):

| Parameter | Single | Basic | Mid | Premium | Teacher recommended range | Mechanical bound |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Reimbursement % | 60% | 40% | 60% | 80% | 30–90% | ≤ 100% |
| Payout multiple | 4× | 3× | 4× | 5× | 2×–7× | payout ≤ remaining period payout capacity |
| Claimable days / week-equivalent | 2 | 1 | 2 | 3 | 1–3 | claim count ≤ remaining claim allowance |
| Tight premium | 10% CWI | 6% | 10% | 14% | 6–14% CWI | — |
| Default premium | 8.5% CWI | 5% | 8.5% | 12% | 5–12% CWI | — |
| Comfortable premium | 7% CWI | 4% | 7% | 10% | 4–10% CWI | — |

`premium × payout_multiple` yields the period ceiling; a single approval's payout is bounded
by the remaining period payout capacity (`actual_payout` above), and submission is bounded by
the configured daily payroll limit and remaining claim allowance per `FEAT-STOR-003`. The
weekly `1 CWI` and `expected_weekly_hours` figures are advisory economic-coherence guidance,
not mechanical caps. These preset values are settled; only the monthly allowance rounding
convention was flagged for confirmation and is fixed in § 4.5.8.

#### 4.5.5 `NON_MONETARY` Insurance

`NON_MONETARY` is the external-benefit insurance product. CTH records the lawful claim
decision but does not own, price the reimbursement of, or verify the external benefit
itself.

**Premium band is affordability guidance only.** Because this product has no economic
payout and CTH cannot value the external benefit, the generic CWI-relative premium envelope
of § 4.5.2 is applied here as **affordability guidance**, not as an exposure-based price.
The Engine's recommendation is of the form:

> Suggested premium: $X–$Y based on your configured class economy. Because this benefit
> occurs outside CTH, CTH cannot estimate its monetary value. Consider the value of the
> external benefit when selecting the final premium.

The teacher remains free to set the premium outside that recommendation.

**Mechanically governable contract.** CTH MAY govern only what it can actually enforce:

- premium;
- weekly or monthly coverage period;
- claim allowance;
- timing / waiting restrictions where applicable;
- the teacher-defined external benefit descriptor.

`NON_MONETARY` MUST have **no**:

- reimbursement percentage;
- payout multiple;
- monetary payout ceiling;
- actuarial / risk calculation.

Canonical preset values (per week-equivalent; scale monthly per § 4.5.2):

| Parameter | Single | Basic | Mid | Premium | Teacher recommended range |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claims / week-equivalent | 1 | 1 | 2 | 3 | 1–3 |
| Waiting period | 3 days | 7 days | 3 days | 0 days | 0–7 days |
| Tight premium guidance | 10% CWI | 6% | 10% | 14% | 6–14% CWI |
| Default premium guidance | 8.5% CWI | 5% | 8.5% | 12% | 5–12% CWI |
| Comfortable premium guidance | 7% CWI | 4% | 7% | 10% | 4–10% CWI |

The premium figures are **affordability guidance**, not calculated fair value; CTH cannot
value the external benefit. The `Single` column uses the mode-band midpoint (equivalent to
`Mid`) per § 4.5.8. All other coverage numbers here are mechanical limits only.

#### 4.5.6 Resolution Status

As of v1.2 the insurance economic model is numerically complete. The canonical preset tables
for all three products (§ 4.5.3, § 4.5.4, § 4.5.5), the deterministic premium-selection rule,
and the monthly allowance rounding convention (§ 4.5.8) are **settled**.

No insurance numerical value remains intentionally TBD. Any future change to these values is
a normative amendment to this specification, not an implementation choice. Implementations
MUST source these values from this document and MUST NOT invent or override them in code.

#### 4.5.7 Presentation of Economic Values

CWI percentages and multiples are the Engine's internal normalization and calculation
mechanism. Teacher-facing surfaces SHALL present the **consequences** of a configuration
primarily in classroom currency, with CWI-relative figures as secondary context.

For example, given a `$40` premium and a teacher-selected `7×` payout multiple, the surface
SHALL present `$280 maximum policy payout` as the primary result, and MAY show `56% CWI` as
secondary context. This presentation rule does not change any calculation; it governs how
results are displayed.

#### 4.5.8 Deterministic Premium Selection and Period Scaling

For the canonical presets, the premium is selected directly from the mode band by tier — no
`risk_factor` or exposure-multiplier formula is used:

- **Basic** → bottom of the mode premium band;
- **Mid** → midpoint of the mode premium band;
- **Premium** → top of the mode premium band;
- **Single** → midpoint (equivalent to `Mid`).

```text
recommended_premium_rate(mode, tier) ∈ { band_lower_bound, band_midpoint, band_upper_bound }

coverage_week_equivalent = covered_class_local_calendar_days / 7   # half-open [start, next_renewal)

period_premium = CWI × recommended_premium_rate × coverage_week_equivalent
```

For monetary products (`TRANSACTION`, `PRODUCTIVITY`):

```text
maximum_policy_payout = period_premium × payout_multiple
```

**Allowance rounding (settled).** Integer per-period allowances (claims per week-equivalent,
claimable days per week-equivalent) scale to the coverage interval by rounding **up**:

```text
period_allowance = ceil(weekly_allowance × coverage_week_equivalent)
```

`ceil` is chosen deliberately: it keeps monthly allowances at least proportional to the
weekly value, and — because every individual approval is still bounded by the remaining
period payout capacity (§ 4.5.4) — a slightly generous **claim count** cannot inflate total
economic exposure. Rounding governs how many separate claims may be filed, never how much
may be paid.

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
#### 4.6.1 Internal Fines

Fines such as overdraft or non-sufficient funds (NSF) fees and late fees shall use the same formula as generic classroom fines recommendations. These recommendations shall surface the recommended price range of the fines, not a single recommended price.

Economic engine table shall persist the chosen overdraft fee under `flat_overdraft_fee` or persist the precomputed `progressive_overdraft_fee` as json object with the following fine schedule

| Economic Mode | Tier 1 | Tier 2 | Tier 3|
| --- | --- | --- | --- |
| `tight` | 7% CWI | 12.5% CWI | 18% CWI |
| `default` | 5% CWI | 10% CWI | 15% CWI|
| `comfortable` | 4% CWI | 8% CWI | 12% CWI |

Internal fines are only active if their value is not `NULL` for the economic policy being enforced. When disabling fines, the backend shall create a new economic policy with the value set to `NULL`

##### 4.6.1.1 Overdraft / NSF Fee Applicability

An overdraft / non-sufficient-funds (NSF) fee is a fine charged for a **failed
agreement**: a transaction that was meant to fulfill an **intended purchase**
(a Store purchase) or an **existing obligation** (e.g. rent, insurance premium)
and could not be covered by the seat's spendable funds.

An NSF fee SHALL NOT be charged for:

- **Transfers** — a transfer is a lateral movement between the seat's OWN
  accounts (e.g. checking↔savings). It is not spending and not an agreement. On
  insufficient funds a transfer is simply **invalid**: it does not proceed and
  incurs no fee.
- **Penalties** — a teacher-applied deduction (an admin adjustment / fine) is
  itself a penalty, neither a purchase nor an obligation. A penalty **cannot
  generate a fine**; it posts as a direct debit (settling below zero if the
  balance cannot cover it) and does not draw on savings to cover itself.

Recording and layering (informative): the fee amount is resolved from the
Economic Engine (`flat_overdraft_fee` / `progressive_overdraft_fee`) and posted
by the Ledger domain, which stays domain-blind (`DOM-LED-001` §II). Because the
NSF fee is a fine, it is also an obligation (`DOM-OBL-001` §II.C, immediate
charge), recorded by the **originating business FEAT's** cross-domain
orchestration — never by the Ledger resolution primitive. This resolves the
overdraft/NSF ownership question previously open in `DOM-ITR-001` §XIII.c.

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

The `Insurance premium` row is the **premium pricing envelope only** (the economic-mode / cost axis of § 4.5), and is engine guidance rather than a hard cap. It does not define any coverage, reimbursement percentage, payout cap, or claim allowance. Those belong to the insurance-tier / coverage axis and are defined by the canonical preset tables in § 4.5.3–§ 4.5.5 with the deterministic selection rule in § 4.5.8; this table MUST NOT be read as a complete insurance economic model. For `NON_MONETARY` this band is affordability guidance only (§ 4.5.5). For `PRODUCTIVITY` the settled mechanical bounds in § 4.5.4 (remaining period payout capacity and remaining claim allowance, with the configured daily payroll limit as the submission-time hours ceiling) bound exposure independently of this row; the weekly `expected_weekly_hours` and `CWI` figures are advisory economic-coherence guidance.

System-defined fines such as rent late fees and overdraft fees shall use the above table for reference when making recommendations. Actual configured fine amount shall persist on `economic_engine` for overdraft fines and `rent_settings` for rent late fees.

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

### Revision history

- **1.4 (2026-08-30)** — Clarifies overdraft/NSF fee applicability. Adds § 4.6.1.1: an NSF
  fee is a fine charged only for a **failed agreement** — a transaction meant to fulfill an
  intended purchase (Store) or an existing obligation (rent, insurance) that funds cannot
  cover. It is NOT charged for transfers (lateral movement between the seat's own accounts;
  invalid on insufficient funds, no fee) or for penalties (a teacher admin adjustment is
  itself a penalty and cannot generate a fine; it posts as a direct debit and does not draw
  on savings). Records the layering: the Ledger domain posts the fee and stays domain-blind
  (`DOM-LED-001` §II), while the fine, being an immediate obligation (`DOM-OBL-001` §II.C), is
  recorded by the originating business FEAT — resolving the overdraft/NSF ownership question
  previously open in `DOM-ITR-001` §XIII.c. Codifies landed behavior; no change to fee amounts.
- **1.3 (2026-08-29)** — Scope/authority correction, not a runtime-behavior change. § 4.5.4
  previously carried PRODUCTIVITY approval- and submission-time execution semantics that the
  section's own scope boundary (§ 4.5) assigns to `FEAT-STOR-003`. This revision: (a) removes
  `remaining_weekly_CWI_capacity` from the approval-time `actual_payout` composition, leaving
  the two-term `min(gross_reimbursement, remaining_period_payout_capacity)`; (b) reclassifies
  the weekly `CWI` payout comparison and the weekly `expected_weekly_hours` comparison from
  non-overridable hard boundaries to advisory economic-coherence guidance; (c) identifies the
  configured daily payroll limit as the mechanical submission-time hours ceiling; and (d)
  updates all dependent references (hard-boundary list, preset "Mechanical bound" column,
  composition and rounding notes, and the premium-envelope note). The landed implementation
  (`FEAT-STOR-003` v1.1 and the PRODUCTIVITY claim-approval code) already implements this
  contract; runtime behavior is unchanged. Governed downstream by the INV → DOM → FEAT
  hierarchy (`INV-CORE-001`); the resulting monetary rule remains deterministic and traceable
  per `INV-CORE-000`.
