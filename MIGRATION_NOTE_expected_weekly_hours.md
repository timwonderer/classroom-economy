# Database Migration Required

## New Field Added

**Table:** `payroll_settings`
**Field:** `expected_weekly_hours`
**Type:** FLOAT
**Nullable:** True
**Default:** 5.0

## SQL Migration

```sql
ALTER TABLE payroll_settings
ADD COLUMN expected_weekly_hours FLOAT DEFAULT 5.0;
```

## Purpose

This field stores the expected hours per week that students attend class. It is used **ONLY** for economy balance checking (CWI calculation), not for actual payroll processing.

## Notes

- Default value is 5.0 hours (typical school week)
- Teachers can customize this based on their schedule
- Existing rows will get the default value (5.0)
- This does not affect existing payroll calculations
