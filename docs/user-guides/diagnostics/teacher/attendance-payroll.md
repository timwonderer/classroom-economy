---
title: Attendance and Payroll Troubleshooting
description: Why attendance records or payroll runs produce unexpected hours and amounts.
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/students
  - user-guides/diagnostics/teacher/transactions-banking
---

# Attendance and Payroll Troubleshooting

Diagnostic guide for resolving payroll calculation errors and attendance tracking issues.

## Payroll does not run or looks wrong

### Symptoms
- A scheduled or manual payroll run produces no transactions.
- Students receive incorrect amounts when payroll is run.

### Causes & Solutions
**Cause 1: Payroll feature is disabled**
- **Check:** Go to Feature Settings and verify that Payroll is enabled for the class period.
- **Fix:** Enable the Payroll feature.

**Cause 2: No attendance activity**
- **Check:** Look at the attendance log for the period. Are there complete tap events?
- **Fix:** Students must have valid Start Work and Break Done events for payroll to calculate time worked.

**Cause 3: Incorrect pay rates**
- **Check:** Go to Payroll Settings and verify the set pay rates.
- **Fix:** Adjust the pay rate per block or global payroll settings.

## Attendance history looks wrong

### Symptoms
- Students dispute their recorded hours.
- Tap events seem to be missing or duplicated.

### Causes & Solutions
**Cause 1: Missing tap-out events**
- **Check:** Check the attendance log for unpaired "Start Work" events.
- **Fix:** The system uses auto-tap-out limits if students forget. The attendance log is append-only and cannot be manually edited; use manual adjustments to correct pay if necessary.

**Cause 2: Confusion from hall passes**
- **Check:** Look for Hall Pass actions interspersed with regular attendance.
- **Fix:** Hall pass actions automatically create tap-out and tap-in entries to pause payroll during the pass. This is intended behavior.

**Cause 3: Wrong class context**
- **Check:** Verify the student's class context when they tapped in.
- **Fix:** Join codes isolate attendance by period. A student must be in the correct class on their dashboard.

## When to Contact Support
Report this issue if:
- Payroll runs create duplicate transactions for the same time period.
- The attendance log becomes corrupted or unreadable.
