---
title: Fix Attendance Errors
category: features
subcategory: teacher-classroom
roles: [teacher]
description: Find attendance mistakes in the log and correct a student's work status from the roster.
keywords: [attendance, corrections, tap errors, start work, break]
related:
  - user-guides/features/teacher/classroom/attendance-approvals
  - user-guides/features/teacher/classroom/students-overview
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Fix Attendance Errors

## Overview

Attendance is a stream of events. Each time a student starts work or goes on break, the app records one event with a timestamp. Payroll pays for the time between a **Start Work** event and the **Break** event that follows it, so a student who forgets to tap is either underpaid or left clocked in all afternoon.

Two pages are involved:

- **Classroom > Attendance** is where you *find* the problem. It is a read-only history.
- **Classroom > Students** is where you *fix* it, by setting the student's current work status.

## Step-by-step instructions

### Finding the problem

1. In the teacher sidebar, open **Classroom**.
2. Select **Attendance**.
3. Use the filter row to narrow the history:

   | Filter | What it does |
   | --- | --- |
   | Status | Limits to **Start Work (Active)** or **Break (Inactive)** events |
   | Start Date | Earliest date to include |
   | End Date | Latest date to include |

4. Select **Apply**. The circular arrow beside it clears the filters and reloads the full history.

The cards above the table summarize what you are looking at: total records, how many were Start Work, how many were Break, and the range showing. Each row lists the student, class, period, timestamp, status, and reason.

Read the rows for one student in order. A healthy day alternates Start Work, Break, Start Work, Break. Two Start Work events in a row with no Break between them means the student never tapped out.

### Correcting a student's work status

1. In the teacher sidebar, open **Classroom**.
2. Select **Students**.
3. Check the box beside each student you need to correct. A toolbar appears showing how many are selected.
4. Open **Bulk Actions** and choose:
   - **Start Work** — for a student who is working but was never tapped in.
   - **Break** — for a student who is finished but was never tapped out.
5. Confirm when prompted.

This writes a new attendance event with the current timestamp, and the page reloads with the updated status.

## Important notes

> [!IMPORTANT]
> **Correct records before you run payroll.** Payroll pays from the events as they stand when the run happens. Fixing an event afterward does not retroactively change a payroll run that has already been posted.

> [!WARNING]
> **Corrections are stamped with the current time, not the time the student meant to tap.** There is no way to edit or delete an existing attendance event, and no way to backdate one. If a student was left clocked in overnight, choosing Break now closes the session at this moment — check the payroll estimate before running payroll.

> [!NOTE]
> Students already in the state you select are skipped rather than duplicated. If you choose Break for ten students and four were already on break, only the other six get a new event.

> [!NOTE]
> Pausing attendance for the class stops new activity but does not change any record that already exists.

## Related guides

- [Attendance and Approvals](attendance-approvals.md)
- [Student Management Overview](students-overview.md)
- [Run Payroll](../economy/payroll-run.md)
- [Attendance and Payroll Troubleshooting](../../../diagnostics/teacher/attendance-payroll.md)
