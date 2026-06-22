# V2 Temporal Architecture Rebuild Plan

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| V2-TEMP-001      | 1.0     | 2026-04-21     | N/A        | Informational (Build Plan) |

---

## I. Purpose

This document records the intended V2 temporal architecture rewrite for the rebuild lane.

It defines the future authoritative model for:

- canonical class-scoped time
- request-time temporal context construction
- UTC storage with class-time evaluation
- day and period boundary enforcement
- elimination of competing temporal models
- temporal invariant enforcement and reconciliation

This document is not part of the current live-test blocker lane. It is a saved implementation plan for the future post-launch rebuild project.

---

## II. Summary

Implement a V2 temporal model where:

- `TemporalContext` is the only approved source of execution-time temporal truth
- class timezone is immutable and class-scoped
- all persisted timestamps remain UTC
- all temporal evaluation is performed in class timezone
- day and period boundaries are computed as UTC ranges derived from class timezone
- no feature, route, service, model, or template may define an alternate temporal model
- rollout is a hard V2 cutover with canonical class time as the only approved execution path

This plan intentionally does not preserve:

- Pacific-specific behavior
- scalar date shortcuts
- route-local time interpretation

---

## III. Canonical Temporal Model

### III.1 TemporalContext

Create one canonical execution-time temporal object per request.

**Fields:**

- `timestamp_utc`
- `class_timezone`
- `class_time`

**Constraints:**

- constructed once per request
- immutable for the lifetime of the request
- not persisted
- not cached across requests
- not recomputed inside domain logic

### III.2 Canonical Construction

```python
timestamp_utc = now_utc()
class_timezone = ClassConfig.get_timezone(class_id)
class_time = convert(timestamp_utc, class_timezone)

TemporalContext(
    timestamp_utc=timestamp_utc,
    class_timezone=class_timezone,
    class_time=class_time,
)
```

### III.3 Prohibited Patterns

- `datetime.now()` or `datetime.utcnow()` outside approved construction
- hardcoded `America/Los_Angeles`
- UTC scalar date logic (`.date()`)
- session- or template-level timezone overrides

---

## IV. Timezone Authority

### IV.1 Source of Truth

Timezone is owned by the Class Configuration Domain.

### IV.2 Rules

- must be a valid IANA timezone
- set at class creation
- immutable for class lifetime
- changing timezone requires creating a new class

### IV.3 Prohibited

- module-level timezone constants
- device-local timezone logic
- request-local guessing
- feature-level overrides

---

## V. Storage Model

### V.1 Requirements

- all timestamps stored in UTC
- no derived class-time values persisted
- no local-time or offset-time fields

### V.2 Special Handling

- date-only fields must be reviewed or replaced
- no Pacific-specific persistence allowed

---

## VI. Day Boundary Model

### VI.1 Definition

Class day is defined as:

```
[00:00, 24:00) in class timezone
```

### VI.2 Canonical Query Pattern

```python
start_utc, end_utc = local_date_bounds_utc(class_date, class_timezone)

query.filter(
    timestamp >= start_utc,
    timestamp < end_utc,
)
```

### VI.3 Disallowed Patterns

```python
utc_now().date()
func.date(timestamp) == today
utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
```

---

## VII. Period Boundary Model

### VII.1 Shared Utilities

- `local_date_bounds_utc(local_date, tz_name)`
- `claim_period_bounds_utc(period_key, tz_name)`
- `week_bounds_utc(reference_time, tz_name)`
- `month_bounds_utc(reference_time, tz_name)`
- `semester_bounds_utc(reference_time, tz_name)`

### VII.2 Rules

- `.weekday()`, `.month`, `.year`, `.date()` must use class-local time
- duplicate logic must be removed
- all queries must use UTC ranges derived from class time

---

## VIII. Execution Model Integration

### VIII.1 Request Flow

1. Construct TemporalContext
2. Resolve class timezone
3. Freeze `class_time`
4. Pass context into capability checks and commands
5. Derive boundaries
6. Convert to UTC for DB queries
7. Execute and return

### VIII.2 Constraints

- domains MUST NOT compute time
- routes MUST NOT define time logic
- features MUST NOT bypass TemporalContext

---

## IX. Boundary Enforcement

### IX.1 Rules

- operations must remain within a single class day
- cross-boundary operations must be rejected
- no partial execution
- no carryover

### IX.2 Applies To

- attendance
- tap-in/tap-out
- daily limits
- financial logic

---

## X. Application and UI Integration

### X.1 Required Updates

- attendance
- tap-in/out
- insurance
- obligations
- analytics
- admin dashboards

### X.2 UI Rules

- display canonical class time
- never rely on device time
- convert UTC → class timezone at render

### X.3 Example

```
Current Class Time: 12:22 PM Pacific Daylight Time (America/Los_Angeles)
```

---

## XI. Public Interfaces

- `build_temporal_context(class_id, timestamp_utc=None)`
- `local_date_bounds_utc(local_date, tz_name)`
- `claim_period_bounds_utc(period_key, tz_name)`
- `week_bounds_utc(reference_time, tz_name)`
- `month_bounds_utc(reference_time, tz_name)`
- `semester_bounds_utc(reference_time, tz_name)`
- `render_class_time(dt_utc, tz_name)`

---

## XII. Remediation Targets

- remove hardcoded Pacific timezone
- remove UTC `.date()` usage
- remove UTC midnight logic
- remove duplicated period logic
- remove route-local time computation
- remove Pacific persistence assumptions

---

## XIII. Test Plan

### XIII.1 Required Tests

- TemporalContext constructed once
- immutability enforcement
- correct day boundaries
- attendance correctness across UTC boundary
- analytics correctness
- DST transitions

### XIII.2 Rules

- no real system clock
- injected time only

---

## XIV. Assumptions

- V2 is a hard cutover
- class_id defines timezone authority
- UTC remains storage layer
- class-local time defines behavior

---

## XV. Implementation Order

1. TemporalContext
2. Remove hardcoded timezone
3. Replace scalar logic
4. Extract utilities
5. Remove duplicates
6. Refactor features
7. Fix persistence
8. Add enforcement

---

## XVI. Enforcement

- CI blocks forbidden APIs
- runtime enforces TemporalContext
- no timezone mutation
- no alternate models

---

## XVII. Final State

After V2:

- one temporal model
- one timezone authority
- one request-time construction path
- one definition of "today" and all periods

Time becomes:

- class-scoped
- immutable
- UTC-backed
- deterministic
- invariant-compliant