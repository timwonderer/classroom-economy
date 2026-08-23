# SPEC-TIME-001: Canonical Temporal Resolver

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-TIME-001 | 1.0 | 2026-07-20 | `V2_Temporal_Architecture_Rebuild_Plan.md` | Implementation Spec |

---

## I. Purpose

This document is the normative build specification for `canonical_temporal_resolver`, the single Canonical Temporal Evaluation tool required by `INV-ARC-015`.

It defines the runtime object, public primitives, inputs, return contract, fail-closed behavior, and browser-facing timezone contract for all temporal evaluation in Classroom Token Hub.

This specification replaces the historical temporal rebuild plan. The old plan described a broad target architecture; this document defines the concrete resolver that all DOM specifications, FEAT specifications, runtime services, scheduled jobs, route handlers, and tests must use.

`canonical_temporal_resolver` is the only public temporal evaluation helper. Older helper names are deprecated and must not be used as new domain or FEAT dependencies.

---

## II. Authority

This specification is subordinate to:

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`

If this document conflicts with `INV-ARC-015`, `INV-ARC-015` prevails.

---

## III. Core Principle

`canonical_temporal_resolver` measures and evaluates time. Domains interpret the resulting temporal truth according to their own business rules.

Examples:

- PROD decides which productivity intervals are compensable; the resolver measures the exact elapsed seconds.
- OBL decides which assessment boundary applies; the resolver resolves whether the boundary has passed.
- The browser displays time in the canonical timezone supplied by the resolver; the browser does not make authoritative temporal decisions.

The resolver must remain business-blind. It must not contain payroll, obligation, hall-pass, store, banking, insurance, or attendance-specific logic.

---

## IV. Evaluation Types

Every resolver call must declare one evaluation type.

| Type | Name | Temporal Authority | Required Context |
| --- | --- | --- | --- |
| `SLE` | System-Level Evaluation | UTC | None |
| `CLE` | Class-Level Evaluation | Canonical Class Timezone | `CanonicalContext` with `class_id` |

### SLE

System-Level Evaluations are platform/user-system evaluations whose authority is UTC.

Examples:

- session expiry
- observability
- account inactivity
- system logs

### CLE

Class-Level Evaluations are class-scoped evaluations whose authority is the class's Canonical Class Timezone.

Examples:

- productivity and payroll
- obligation due dates
- hall-pass timing
- store item expiry
- class-local day boundaries

For CLE, the resolver must fail closed if the canonical class timezone cannot be established.

---

## V. Temporal Authority Resolution

The resolver must use one deterministic authority flow:

1. Accept evaluation type.
2. If `SLE`, set temporal authority to UTC.
3. If `CLE`, require canonical execution context.
4. Resolve Canonical Class Timezone from `ctx.class_id`.
5. Validate that the timezone is a valid IANA timezone.
6. Normalize all supplied timestamps into the resolved temporal authority.
7. Execute the requested primitive.
8. Return a canonical temporal evaluation object.

For architectural consistency, every CLE primitive evaluates in Canonical Class Timezone, even when the calculation would be mathematically equivalent in UTC.

No CLE primitive may operate directly on raw UTC timestamps after authority resolution.

---

## VI. Storage and Input Rules

All persisted timestamps remain UTC.

The resolver may accept UTC-aware timestamps from persistence, but callers must not independently convert them to class-local time before calling the resolver.

The resolver must reject or normalize inputs as follows:

| Input Condition | Required Behavior |
| --- | --- |
| UTC-aware timestamp | Accept |
| timezone-aware non-UTC timestamp | Normalize through temporal authority |
| naive timestamp | Reject unless the specific test-only pathway explicitly supplies authority |
| missing required timestamp | Fail closed |
| invalid interval with end before start | Fail closed |
| unknown timezone for CLE | Fail closed |
| missing `ctx.class_id` for CLE | Fail closed |

---

## VII. Canonical Return Object

Every primitive returns a `CanonicalTemporalEvaluation` object.

Minimum fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `evaluation_type` | `SLE` or `CLE` | Evaluation category |
| `temporal_authority` | string | `UTC` for SLE or IANA timezone for CLE |
| `canonical_now` | datetime | Current timestamp in the resolved authority |
| `canonical_now_utc` | datetime | Same instant in UTC for persistence/correlation |
| `reference_time_utc` | datetime | UTC timestamp used as the evaluation anchor |
| `class_id` | string or null | Class boundary for CLE |
| `result` | primitive-specific | Boolean, timestamp boundary, date, or duration result |

The object may expose typed convenience properties for primitive-specific results, but those properties must not introduce business semantics.

Examples:

- `is_earlier`
- `is_later`
- `is_between`
- `elapsed_seconds`
- `remaining_seconds`
- `evaluation_date`
- `boundary_start`
- `boundary_end`
- `period`
- `shifted_timestamp`
- `shifted_timestamp_utc`
- `display_timezone`

---

## VIII. Required Public API

The implementation must expose one entry point:

```python
canonical_temporal_resolver(
    evaluation_type: str,
    *,
    canonical_execution_context: CanonicalContext | None = None,
    primitive: str,
    reference_time_utc: datetime | None = None,
    **primitive_inputs,
) -> CanonicalTemporalEvaluation
```

Constants:

```python
SYSTEM_LEVEL_EVALUATION = "SLE"
CLASS_LEVEL_EVALUATION = "CLE"
```

Permitted primitive names:

- `current_time`
- `earlier_than`
- `later_than`
- `between_boundaries`
- `time_since`
- `time_until`
- `current_evaluation_day`
- `evaluation_day_boundaries`
- `evaluation_period_boundaries`
- `elapsed_duration`
- `shift_timestamp`

The resolver must not expose additional public temporal primitives without amending this spec.

---

## IX. Primitive Contracts

### 1. `current_time`

Purpose:

Resolve canonical "now" under the selected temporal authority.

Accepts:

| Input | Required | Notes |
|---|---|---|
| `reference_time_utc` | No | If omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
| --- | --- |
| `canonical_now` | Current timestamp in the resolved temporal authority |
| `canonical_now_utc` | Same instant in UTC |
| `display_timezone` | Timezone browser may use for display |

Rules:

- Callers must not call `datetime.now()` independently.
- Browser display may use `display_timezone`, but browser time is not authoritative.

### 2. `earlier_than`

Purpose:

Determine whether one timestamp is earlier than another under canonical temporal authority.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `candidate` | Yes | Timestamp being evaluated |
| `reference` | Yes | Timestamp being compared against |

Returns:

| Result Field | Meaning |
|---|---|
| `is_earlier` | `candidate < reference` |

### 3. `later_than`

Purpose:

Determine whether one timestamp is later than another under canonical temporal authority.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `candidate` | Yes | Timestamp being evaluated |
| `reference` | Yes | Timestamp being compared against |

Returns:

| Result Field | Meaning |
|---|---|
| `is_later` | `candidate > reference` |

### 4. `between_boundaries`

Purpose:

Determine whether a timestamp falls inside a canonical temporal window.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `candidate` | Yes | Timestamp being evaluated |
| `start_boundary` | Yes | Inclusive start boundary |
| `end_boundary` | Yes | Exclusive end boundary |

Returns:

| Result Field | Meaning |
|---|---|
| `is_between` | `start_boundary <= candidate < end_boundary` |

Rules:

- Boundary semantics are always inclusive start, exclusive end.
- Callers must not implement alternate inclusion rules locally.

### 5. `time_since`

Purpose:

Measure exact elapsed time from a supplied timestamp until canonical now.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `start` | Yes | Starting timestamp |
| `reference_time_utc` | No | Evaluation anchor; if omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
|---|---|
| `elapsed_seconds` | Exact integer elapsed seconds from `start` to canonical now |

Rules:

- Negative elapsed time fails closed.
- No rounding is performed.

### 6. `time_until`

Purpose:

Measure exact remaining time from canonical now until a supplied timestamp.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `target` | Yes | Target timestamp |
| `reference_time_utc` | No | Evaluation anchor; if omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
|---|---|
| `remaining_seconds` | Exact integer seconds from canonical now to `target` |

Rules:

- Negative remaining time is returned as `0` only if the caller explicitly requests clamping through a future spec amendment. Version 1.0 fails closed on negative values.
- No rounding is performed.

### 7. `current_evaluation_day`

Purpose:

Derive the current calendar day under the selected temporal authority.

Accepts:

| Input | Required | Notes |
|---|---|---|
| `reference_time_utc` | No | Evaluation anchor; if omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
|---|---|
| `evaluation_date` | Calendar date in the resolved authority |

Rules:

- For CLE, the evaluation date is the class-local date.
- For SLE, the evaluation date is the UTC date.

### 8. `evaluation_day_boundaries`

Purpose:

Derive canonical start/end boundaries for an evaluation day.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `evaluation_date` | No | If omitted, derive current evaluation day |
| `reference_time_utc` | No | Used only when `evaluation_date` is omitted |

Returns:

| Result Field | Meaning |
| --- | --- |
| `boundary_start` | Start of evaluation day in resolved authority |
| `boundary_end` | End of evaluation day in resolved authority |
| `boundary_start_utc` | Start boundary converted to UTC for DB queries |
| `boundary_end_utc` | End boundary converted to UTC for DB queries |

Rules:

- Day boundary is `[00:00, 24:00)` in the resolved authority.
- Callers must not derive day boundaries independently.

### 9. `elapsed_duration`

Purpose:

Measure exact elapsed duration across one or more timestamp intervals.

Accepts:

| Input | Required | Notes |
|---|---|---|
| `intervals` | Yes | List of `(start, end)` timestamp pairs |

Returns:

| Result Field | Meaning |
|---|---|
| `elapsed_seconds` | Exact sum of elapsed seconds across all intervals |

Rules:

- The caller selects which intervals have business meaning.
- The resolver only validates and measures the intervals.
- Each interval must have `end >= start`.
- Empty interval lists fail closed unless a future spec amendment explicitly allows zero-duration evaluation.
- Overlapping intervals fail closed in version 1.0 to prevent accidental double counting.
- Adjacent intervals are allowed.
- No rounding is performed.

Example:

```text
Input intervals:
08:00:00 -> 08:20:00
08:30:00 -> 09:00:22

Output:
elapsed_seconds = 3022
```

PROD may then apply payroll policy:

```text
3022 seconds -> round payable minutes up/down according to payroll policy
```

`canonical_temporal_resolver` must not perform that payroll rounding.

### 10. `shift_timestamp`

Purpose:

Construct a new timestamp by shifting a supplied timestamp by an exact elapsed duration.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `timestamp` | Yes | Timestamp being shifted |
| `elapsed_seconds` | Yes | Signed integer number of seconds to shift |

Returns:

| Result Field | Meaning |
| --- | --- |
| `shifted_timestamp` | Shifted timestamp in the resolved temporal authority |
| `shifted_timestamp_utc` | Same shifted instant converted to UTC for persistence/correlation |

Rules:

- The caller decides what business event requires a shifted timestamp.
- The resolver only normalizes the timestamp, applies the exact second shift, and returns canonical authority-local and UTC forms.
- `elapsed_seconds` must be an integer.
- No business rounding, payroll policy, obligation policy, or display formatting is performed.

Example:

```text
Input:
timestamp = active productivity start
elapsed_seconds = remaining daily-limit seconds

Output:
shifted_timestamp_utc = exact inactive-event timestamp that makes the active duration equal the class limit
```

PROD may use this primitive to construct the exact close-out timestamp for scheduled daily-limit enforcement, but the resolver must not know what a daily limit is.

### 11. `evaluation_period_boundaries`

Purpose:

Derive canonical start/end boundaries for a calendar period under the selected temporal authority.

Accepts:

| Input | Required | Notes |
| --- | --- | --- |
| `period` | Yes | `day`, `week`, or `month` |
| `reference_time_utc` | No | If omitted, resolver obtains current UTC time internally |

Returns:

| Result Field | Meaning |
| --- | --- |
| `period` | Normalized period name |
| `boundary_start` | Start of the period in resolved authority |
| `boundary_end` | Exclusive end of the period in resolved authority |
| `boundary_start_utc` | Start boundary converted to UTC for DB queries |
| `boundary_end_utc` | End boundary converted to UTC for DB queries |

Rules:

- `day` boundaries are `[00:00, 24:00)` in the resolved authority.
- `week` boundaries are Monday-start calendar weeks in the resolved authority.
- `month` boundaries are calendar-month boundaries in the resolved authority.
- Callers must not derive week or month boundaries independently.
- The resolver does not decide whether a weekly or monthly period has business meaning.

---

## X. Browser Timezone Contract

`canonical_temporal_resolver` is responsible for resolving and supplying the authoritative display timezone.

| Surface | Display Timezone |
| --- | --- |
| SLE page or system surface | `UTC` |
| CLE page or class-scoped surface | Canonical Class Timezone |

The browser may use the supplied timezone to render and continuously update visual clocks.

The browser must not use its displayed clock to decide business truth.

Allowed:

```text
Server supplies display_timezone = America/Los_Angeles.
Browser renders navbar clock in America/Los_Angeles.
```

Forbidden:

```text
Browser decides whether payroll is due from local device time.
Browser decides whether an obligation deadline passed from local device time.
Browser computes class-local day boundaries.
```

---

## XI. Domain Boundary Rules

### PROD

PROD owns:

- which productivity events are active or inactive;
- which intervals count as compensable;
- how exact elapsed seconds become payable minutes under payroll policy.

The resolver owns:

- measuring the supplied intervals;
- resolving class-local day and boundary truth;
- providing exact elapsed seconds.

### OBL

OBL owns:

- which obligation assessment boundary applies;
- which period or cycle has business meaning;
- whether an assessment is due.

The resolver owns:

- resolving the temporal boundary;
- comparing timestamps;
- calculating exact elapsed or remaining time.

### LED

Ledger owns monetary time only as recorded occurrence/provenance timestamps. Ledger must use `canonical_temporal_resolver` for temporal comparisons, reconciliation cutoffs, and display timezone metadata, but Ledger must not encode business-specific temporal semantics.

---

## XII. Prohibited Patterns

The following are prohibited outside `canonical_temporal_resolver`:

- `datetime.now()`
- `datetime.utcnow()`
- raw `end - start` duration math
- direct timezone conversion
- raw `.date()` derivation for business logic
- local day-boundary construction
- hardcoded `America/Los_Angeles`
- browser/device-local business evaluation
- FEAT-local current-time reads
- test-local current-time reads for domain behavior

Tests must inject `reference_time_utc` into `canonical_temporal_resolver` rather than relying on wall-clock time.

---

## XIII. Implementation Location

The canonical implementation must live at:

```text
app/utils/canonical_temporal_resolver.py
```

The public names exported by this module must include:

```python
SYSTEM_LEVEL_EVALUATION
CLASS_LEVEL_EVALUATION
CanonicalTemporalEvaluation
canonical_temporal_resolver
```

`canonical_temporal_resolver` may call any lower-level time utility it requires, including functions in `app/utils/time.py`.

No code outside `app/utils/canonical_temporal_resolver.py` may call `app/utils/time.py` or any other time tool directly for temporal behavior. All runtime code, tests, DOM logic, FEAT logic, route logic, scheduled jobs, service code, model defaults, and template/page context builders must obtain temporal values through `canonical_temporal_resolver`.

`app/utils/time.py` is an internal implementation dependency of the resolver, not a public application API.

Deprecated names include any prior temporal helper, temporal context, or temporal module name not routed through `canonical_temporal_resolver`.

Historical documents and migration notes may mention older names, but new implementation, tests, DOM specs, and FEAT specs must use `canonical_temporal_resolver`.

---

## XIV. Test Requirements

Targeted tests must prove:

1. SLE resolves to UTC.
2. CLE resolves to Canonical Class Timezone.
3. CLE fails closed without class context.
4. CLE fails closed when class timezone cannot be established.
5. `current_time` returns UTC and authority-local forms of the same instant.
6. `earlier_than` and `later_than` normalize through the selected authority.
7. `between_boundaries` uses inclusive-start/exclusive-end semantics.
8. `time_since` returns exact elapsed seconds.
9. `time_until` returns exact remaining seconds.
10. `current_evaluation_day` derives class-local day for CLE.
11. `evaluation_day_boundaries` returns both authority-local and UTC boundaries.
12. `elapsed_duration` sums one interval.
13. `elapsed_duration` sums multiple discontinuous intervals.
14. `elapsed_duration` rejects end-before-start intervals.
15. `elapsed_duration` rejects overlapping intervals.
16. `shift_timestamp` returns authority-local and UTC forms of the same shifted instant.
17. `evaluation_period_boundaries` returns day/week/month authority-local and UTC boundaries.
18. Payroll-style rounding is not performed by the resolver.
19. Browser display timezone is `UTC` for SLE.
20. Browser display timezone is Canonical Class Timezone for CLE.

Recommended test file:

```text
tests/dom/temporal/test_SPEC_TIME_001__canonical_temporal_resolver.py
```

---

## XV. Migration Rules

When migrating existing code:

1. Replace every direct call to `app/utils/time.py` outside `app/utils/canonical_temporal_resolver.py` with `canonical_temporal_resolver(...)`.
2. Keep `app/utils/time.py` only as an internal lower-level implementation dependency of the resolver.
3. Do not add compatibility wrappers that preserve old direct temporal APIs for any application caller.
4. Update FEAT specs to cite `SPEC-TIME-001` where they depend on temporal evaluation.
5. Add targeted tests before rewiring route/template surfaces that depend on temporal behavior.

---

## XVI. Definition of Done

`SPEC-TIME-001` is implemented when:

- `app/utils/canonical_temporal_resolver.py` exists and exports the required public names;
- all required primitives are implemented;
- CLE/SLE authority resolution is deterministic;
- every primitive returns `CanonicalTemporalEvaluation`;
- no code outside `app/utils/canonical_temporal_resolver.py` imports or calls `app/utils/time.py` or other time tools directly;
- domain/FEAT temporal behavior stops doing direct datetime math;
- targeted tests pass;
- PROD payroll can call `elapsed_duration` and receive exact elapsed seconds;
- OBL can call boundary primitives and receive canonical class-local boundaries;
- browser-facing request/page context can obtain display timezone from the resolver.

---

## XVII. Amendment

Revisions to this document must:

1. Increment the version number.
2. Update the effective date.
3. Remain subordinate to `INV-ARC-015`.
4. Preserve the finite primitive model unless `INV-ARC-015` is amended first.
5. Distinguish temporal measurement from business interpretation.
