# Timezone Handling

## Overview

The application uses a centralized JavaScript utility (`static/js/timezone-utils.js`) to handle timezone conversions for displaying timestamps to users. This ensures consistent formatting across all pages and provides a better user experience by displaying times in the user's local timezone with PST as a fallback.

## Architecture

### Client-Side Approach

All timestamps are stored and transmitted from the server as UTC (ISO 8601 format with 'Z' suffix). The client-side JavaScript utility converts these to the user's local timezone for display.

**Benefits:**
- Accurate timezone detection using browser APIs
- No server-side configuration needed
- Respects user's system timezone settings
- Consistent formatting across all pages

### Timezone Utility (`timezone-utils.js`)

The utility provides:

1. **Automatic timezone detection** using `Intl.DateTimeFormat().resolvedOptions().timeZone`
2. **PST fallback** (`America/Los_Angeles`) when detection fails
3. **Multiple formatting functions:**
   - `formatTimestamp(utcString)` - Full date/time with timezone abbreviation
   - `formatDate(utcString)` - Date only
   - `formatTime(utcString)` - Time only with timezone abbreviation
4. **Automatic element conversion** for elements with class `.local-timestamp`
5. **Server synchronization** via `/api/set-timezone` endpoint

## Usage

### In Templates

#### Full Timestamp

```html
<span class="local-timestamp" data-timestamp="{{ record.timestamp.isoformat() }}Z"></span>
```

Output: `Dec 3, 2025, 2:30 PM PST`

#### Date Only

```html
<span class="local-timestamp" data-timestamp="{{ record.timestamp.isoformat() }}Z" data-format="date"></span>
```

Output: `Dec 3, 2025`

#### Time Only

```html
<span class="local-timestamp" data-timestamp="{{ record.timestamp.isoformat() }}Z" data-format="time"></span>
```

Output: `2:30 PM PST`

### In JavaScript

```javascript
// Format a timestamp
const formatted = TimezoneUtils.formatTimestamp('2025-12-03T14:30:00Z');

// Format date only
const dateFormatted = TimezoneUtils.formatDate('2025-12-03T14:30:00Z');

// Format time only
const timeFormatted = TimezoneUtils.formatTime('2025-12-03T14:30:00Z');

// Detect user's timezone
const userTimezone = TimezoneUtils.detectTimezone();

// Manually convert all timestamps on page
TimezoneUtils.convertAllTimestamps();
```

## Implementation Details

### Server-Side Requirements

1. **Store timestamps as UTC** in the database
2. **Return timestamps as ISO 8601 with 'Z' suffix** in templates:
   ```python
   {{ timestamp.isoformat() }}Z
   ```
3. **Include timezone-utils.js** in base layout templates (already done)

### Updated Templates

The following templates have been updated to use the centralized utility:

1. `templates/student_detail.html` - Attendance history, transactions, items, rent
2. `templates/admin_attendance_log.html` - Attendance records table
3. `templates/mobile/admin_attendance_log.html` - Mobile attendance view
4. `templates/admin_hall_pass.html` - Hall pass history
5. `templates/admin_transactions.html` - Transaction history
6. `templates/student_dashboard.html` - Recent transactions
7. `templates/student_payroll.html` - Attendance events (date/time split)

### Layout Files

All base layout templates include the utility:

- `templates/layout_admin.html`
- `templates/layout_student.html`
- `templates/mobile/layout_admin.html`
- `templates/mobile/layout_student.html`

## Timezone Abbreviations

The utility attempts to determine the appropriate timezone abbreviation (e.g., PST, PDT, EST, EDT) based on:
- The user's detected timezone
- The specific date/time being formatted (handles DST automatically)

If abbreviation detection fails, it falls back to showing just the formatted time.

## Fallback Behavior

1. **Browser timezone detection fails** → Falls back to PST (`America/Los_Angeles`)
2. **Invalid timestamp** → Displays `—` (em dash)
3. **Missing timestamp** → Displays `—` (em dash)
4. **JavaScript error** → Returns original UTC string

## Testing

To verify timezone handling:

1. **Different timezones:** Test with system timezone set to different values
2. **DST transitions:** Verify dates around DST changes show correct abbreviations
3. **Edge cases:** Test with missing/invalid timestamps
4. **Multiple formats:** Verify date-only and time-only formats work correctly

## Server Synchronization

The utility automatically syncs the detected timezone to the server on page load via `/api/set-timezone`. This stores the timezone in the user's session for potential server-side use.

**Note:** The session timezone is currently not used server-side. All timezone conversion happens on the client. This may change in future updates.

## Future Enhancements

Potential improvements:
- User preference for timezone (stored in database)
- Server-side timezone conversion option
- Additional format options (relative time, custom formats)
- Timezone picker UI component
