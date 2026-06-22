---
# FEAT-MET-001: Analytics Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|FEAT-MET-001| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose

This document defines the scope, constraints, metrics, and invariants governing the Analytics feature in the Classroom Economy App.

## II. Scope

The Analytics system exists to observe system health and behavioral patterns, not to grade students, rank individuals, or recreate general-purpose BI tools.

This specification applies to all analytics-related development, including dashboards, computed metrics, alerts and thresholds, projections and simulations, and drill-down views.

## III. Authority Level

Normative (FEAT Tier). Subordinate to INV-CORE-000 and DOM-ECON-002.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-ECON-002_Economy_Specification.md`

## V. Core Purpose (Non-Negotiable)

The Analytics system exists to answer one question:

> “Is the classroom economy behaving as designed?”

Analytics must evaluate:

system stability

model compliance

behavioral divergence

Analytics must not evaluate:

student worth

student morality

comparative ranking between students

## VI. Design Philosophy

Analytics must follow an observability model, not a reporting model.

### 1. Observability Principles

Analytics must:

surface signals, not raw data

highlight anomalies, not totals

favor trends over snapshots

bias toward actionable interpretation

Analytics must never require:

custom formulas

ad-hoc filters

pivot tables

spreadsheet-like manipulation

If a teacher has to “figure out what to look for,” the system has failed.

## VII. Relationship to CWI (Foundational Rule)

All analytics related to money must be interpreted relative to CWI.

### 1. Prohibited Metrics

The following metrics are not allowed as primary analytics:

average student balance

highest / lowest balance

leaderboards

raw wealth rankings

### 2. Required Framing

All monetary analytics must be expressed as one of the following:

deviation from expected CWI trajectory

percentage of students within defined CWI bands

trend relative to CWI over time

CWI is the baseline model.
Analytics measure deviation from the model, not absolute outcomes.

## VIII. Metric Classification

Analytics metrics must belong to exactly one of the following categories.

### 1. System Health Metrics (Always Visible)

These represent the “heartbeat” of the classroom economy.

Examples:

participation rate

money velocity

percentage of students within CWI deviation bands

budget survival test pass rate

Rules:

must be aggregated at class level

must update automatically

must be readable in under 5 seconds

---

### 2. Drift & Anomaly Metrics

These identify divergence from expected behavior.

Examples:

increasing negative CWI deviation

declining purchase frequency after price changes

rising hoarding behavior

prolonged inactivity

Rules:

must be trend-based

must include directionality (improving / worsening)

must never default to blaming students

---

### 3. Diagnostic Drill-Down Metrics

These are available only after user interaction.

Examples:

individual balance vs expected CWI

income source composition

expense category distribution

intervention history

Rules:

must never be shown by default

must be contextualized with CWI expectations

must explain why the metric matters

## IX. Temporal Rules

Analytics must respect time explicitly.

### 1. Time Windows

All analytics must specify:

the time window evaluated (e.g., week, pay cycle, rent cycle)

whether values are cumulative or rolling

Undefined time scopes are prohibited.

### 2. Event Annotations

Analytics must support annotations for:

rent changes

wage changes

inflation events

wildcard constraints

holidays or shortened weeks

Charts without context are considered incomplete.

## X. Thresholds and Alerts

Analytics may surface visual alerts, not notifications, by default.

### 1. Threshold Rules

Thresholds must:

be predefined by the system

be adjustable by teachers within bounded ranges

default to conservative, non-punitive values

Examples:

“>20% of students outside −20% CWI deviation”

“Money velocity dropped >30% week-over-week”

### 2. Alert Behavior

Alerts must:

explain what changed

explain why it might matter

suggest possible interventions

Alerts must never:

shame students

prescribe discipline

trigger automatic penalties

## XI. Projections & Simulations

Analytics may include what-if simulations, subject to strict limits.

### 1. Allowed Inputs

Simulations may vary:

rent (±10%)

base wage rate (bounded by CWI rules)

store pricing tiers

insurance premiums

fines

### 2. Required Outputs

Simulations must report:

projected % solvent students

projected CWI deviation distribution

projected engagement risk

Simulations must never:

directly apply changes

persist results

overwrite live data

Analytics simulate.
Other systems decide.

## XII. Separation from Logs

Analytics and logs are distinct systems.

Analytics answer: “Is something wrong?”

Logs answer: “What exactly happened?”

Analytics must never:

display full transaction lists by default

function as an audit ledger

Logs must be accessible only via intentional navigation.

## XIII. Ethical Constraints

Analytics must preserve student dignity.

Therefore:

individual student names must never appear in default views

comparative ranking is prohibited

visual language must avoid “failure” framing

Analytics are about system behavior, not student character.

## XIV. Performance & Computation Rules

Analytics must be:

precomputed where possible

cached by time window

resilient to partial data

Real-time recalculation of historical metrics is prohibited unless required for correctness.

## XV. Output Requirements (Developer-Facing)

Every analytics metric must document:

inputs used

time window

relation to CWI

interpretation intent

If a metric cannot explain why it exists, it should not exist.

## XVI. Non-Negotiable Rules (Summary)

1. Analytics observe systems, not students.

2. All monetary analytics are CWI-relative.

3. Trends matter more than totals.

4. Alerts guide action, not punishment.

5. Analytics never replace teacher judgment.

6. If it feels like Excel, it’s wrong.

## XVII. Design North Star

A teacher should be able to glance at the Analytics page and say:

> “Something is drifting — and I know what lever to pull.”

If analytics do more than that, they are doing too much.
If they do less than that, they are not worth building.

## XVIII. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
