---
title: Hall Pass Troubleshooting
description: Why hall pass configuration, approvals, or pass balances behave unexpectedly.
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/store
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Hall Pass Troubleshooting

Diagnostic guide for resolving issues with hall pass approvals, tracking, and terminal usage.

## Passes cannot be approved

### Symptoms
- You cannot approve a student's hall pass request.
- The approve button is disabled or missing.

### Causes & Solutions
**Cause 1: Hall pass feature disabled**
- **Check:** Verify Hall Pass is enabled in Feature Settings for the class.
- **Fix:** Enable the feature to allow approvals.

**Cause 2: Pass is no longer pending**
- **Check:** Look at the pass status in the queue.
- **Fix:** Approved, rejected, or cancelled passes cannot be re-approved. The student must submit a new request.

**Cause 3: Insufficient passes available**
- **Check:** Check the student's remaining hall pass balance.
- **Fix:** If you require passes for approval, the student cannot be approved if their balance is zero. Grant more passes or waive the requirement in settings.

## Hall pass tracking looks wrong

### Symptoms
- Passes are stuck in the queue.
- Pass deductions are incorrect.

### Causes & Solutions
**Cause 1: Pass stuck as "Approved"**
- **Check:** Verify if the student scanned the pass at the terminal.
- **Fix:** The queue shows approved passes that haven't left yet. Terminal scans move passes from approved to left, then returned. If a student forgets to scan, manually mark them returned.

**Cause 2: Passes not deducted from balance**
- **Check:** Check the reason selected for the pass.
- **Fix:** Office, Summons, or "Done for the day" passes do not deduct from the standard pass balance. Only standard bathroom/water/errand passes do.

## When to Contact Support
Report this issue if:
- The hall pass terminal tablet fails to load or connect to the system.
- Passing scanning results in a systemic server error.
