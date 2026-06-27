# ARC-OPS-012: Datetime Handling Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-012      | 1.1     | 2026-03-08     | 1.0        | Constitutional  |

## I. Purpose
This document defines the authoritative rules for how datetimes are created, stored, transmitted, compared, and displayed across the entire system.
The intent is to dramatically reduce ambiguity, enforce consistency, and make violations immediately visible and diagnosable by standardizing on UTC and centralizing localization in the presentation layer.

This specification applies to:
- Backend (Python / Flask)
- Database schema
- APIs
- Client-side JavaScript
- Templates and presentation layers

## II. Scope
All temporal operations, storage formats, API transmissions, and client-side display logic within the Classroom Token Hub.

## III. Authority Level
Constitutional (ARC Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Core Invariant (Non-Negotiable)

All persisted datetimes in the system MUST be UTC and timezone-aware.

Localization is a presentation concern for rendering, except for business rules defined by local calendar day (deadlines, due dates, expirations), which must be computed in teacher-local time and then converted to UTC for storage/comparison.

Any deviation from this invariant is considered a bug, not a stylistic choice.

### Definitions
- **UTC-aware datetime**: A datetime object with an explicit UTC timezone (tzinfo=UTC).
- **Naive datetime**: A datetime object with no timezone information. These are considered legacy artifacts and must not be intentionally created.
- **Presentation layer**: The UI, templates, or browser rendering layer. This is the only layer where localization occurs.

## VI. Server-Side Rules (Python / Flask)

### 1. Datetime Creation
All “current time” values MUST be obtained through a centralized utility.
Allowed:
`from app.utils.time import utc_now`
`utc_now()`

Forbidden:
`datetime.utcnow()`
`datetime.now()`
`datetime.now(tz=None)`

No direct calls to `datetime.utcnow()` or `datetime.now()` are permitted anywhere in the codebase.

### 2. Datetime Storage (Database)
All database datetime columns MUST:
- Store values in UTC
- Be timezone-aware
- Declare intent explicitly

Required SQLAlchemy pattern:
```python
created_at = db.Column(
    db.DateTime(timezone=True),
    nullable=False,
    default=utc_now
)
```

Notes:
- `timezone=True` is mandatory.
- Defaults MUST reference `utc_now`, not inline datetime calls.
- Existing naive columns are considered technical debt and should be normalized opportunistically.

### 3. Datetime Normalization (Legacy Compatibility)
Legacy data or external APIs may introduce naive datetimes. These MUST be normalized before use using a single shared normalization helper:
```python
def ensure_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
```

Rules:
- Normalization occurs at system boundaries.
- Normalization MUST happen before comparison or serialization.
- Ad-hoc normalization logic is prohibited.

### 4. Datetime Comparison
All comparisons MUST occur between UTC-aware datetimes.

Forbidden:
`if now > expiry_date:`

Required:
`if utc_now() > ensure_utc(expiry_date):`

Any comparison capable of raising offset-naive vs offset-aware is considered a spec violation.

### 5. Teacher-Local Deadline Expansion
For date-based business rules (rent due day, deadline, expiration date):
- Interpret the date in the teacher/admin timezone calendar.
- Expand to a precise UTC instant (e.g., local start/end of day) before persistence/comparison.
- If timezone cannot be resolved, fallback to `America/Los_Angeles` (PST/PDT).
- Client/browser timezone must not alter these server-side deadline boundaries.

### 6. API Serialization
All datetimes returned by APIs MUST:
- Be UTC
- Be ISO 8601 compliant
- Include timezone information (Z suffix)

Example: `"2026-01-12T21:45:00Z"`

APIs MUST NOT:
- Localize timestamps
- Return browser-dependent formats
- Omit timezone information

## VII. Client-Side Rules (JavaScript)

### 1. Source of Truth
- The server always sends UTC timestamps
- The client never sends localized timestamps back to the server

UTC is the only temporal language spoken across the network boundary.

### 2. Localization Responsibility
Localization is handled exclusively by `static/js/timezone-utils.js`.

Responsibilities include:
- Automatic timezone detection using `Intl.DateTimeFormat().resolvedOptions().timeZone`
- PST fallback (`America/Los_Angeles`) when detection fails
- Display formatting
- Automatic element conversion for elements with class `.local-timestamp`
- Optional server synchronization via `/api/set-timezone` endpoint

No other client-side code may:
- Perform timezone math
- Format timestamps independently
- Assume local time semantics

### 3. Approved Client Utilities
All timestamp rendering MUST use:
- `TimezoneUtils.formatTimestamp(utcString)` - Full date/time with timezone abbreviation
- `TimezoneUtils.formatDate(utcString)` - Date only
- `TimezoneUtils.formatTime(utcString)` - Time only with timezone abbreviation
- `TimezoneUtils.formatCompactDate(utcString)`

Direct use of `new Date().toLocaleString(...)` outside of `timezone-utils.js` is prohibited.

## VIII. Presentation Layer Rules (Templates / UI)
- Templates receive UTC timestamps or UTC strings only.
- Templates MUST return timestamps as ISO 8601 with 'Z' suffix: `{{ timestamp.isoformat() }}Z`
- Templates MUST NOT:
  - Compare dates
  - Perform timezone math
  - Infer timezone meaning
- Templates may only render:
  - Pre-formatted strings
  - `.local-timestamp` elements for client-side conversion (e.g., `<span class="local-timestamp" data-timestamp="{{ record.timestamp.isoformat() }}Z"></span>`)

## IX. Error Handling & Observability
Datetime invariant violations commonly surface as: `TypeError: can't compare offset-naive and offset-aware datetimes`.

These errors:
- MUST be logged at ERROR level
- MUST include route and request_id
- Indicate a breach of this specification

## X. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
