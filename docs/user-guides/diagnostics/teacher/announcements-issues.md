---
title: Announcements and Issues Troubleshooting
description: Why an announcement doesn't reach students, and how to work the student issue queue.
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/onboarding
  - user-guides/diagnostics/teacher/students
---

# Announcements and Issues Troubleshooting

Diagnostic guide for resolving problems with class announcements and student issue reports.

## Students do not see an announcement

### Symptoms
- Students report they cannot see an announcement on their dashboard.
- An announcement you created is missing from the student view.

### Causes & Solutions
**Cause 1: Announcement is inactive or expired**
- **Check:** View the announcement list in the admin UI and check its status and expiration date.
- **Fix:** Edit the announcement to make it Active or extend the expiration date.

**Cause 2: Wrong class period assigned**
- **Check:** Verify which class periods the announcement is assigned to.
- **Fix:** Edit the announcement and ensure the student's class period is selected.

**Cause 3: Student in wrong class context**
- **Check:** Ask the student which class they have selected in their dashboard switcher.
- **Fix:** Instruct the student to switch to the correct class context.

## Issues are missing or cannot be submitted

### Symptoms
- Students cannot submit a bug report or issue.
- You do not see issues submitted by students in your queue.

### Causes & Solutions
**Cause 1: Bug reports disabled**
- **Check:** Go to Feature Settings and see if "Issue Reporting" is disabled.
- **Fix:** Enable Issue Reporting in the Feature Settings for the relevant class.

**Cause 2: Student looking at wrong class context**
- **Check:** Verify the student is in the correct class context when submitting the issue.
- **Fix:** Issues are scoped per join code; students must pick the correct class before submitting.

**Cause 3: Issue limit reached**
- **Check:** See if the student has reached the display limit.
- **Fix:** Only the last 20 issues show on the student help page. Resolve older issues to clear the queue.

## When to Contact Support
Report this issue if:
- Announcements assigned to "All Classes" are not visible to anyone.
- The issue submission form crashes with broken CSRF errors.
