---
title: Support Tickets
category: features
subcategory: teacher-settings
roles: [teacher]
description: Submit a support ticket to the Classroom Token Hub team, choose whether it is about your class or your account, and read the My Tickets list.
keywords: [support, ticket, help, bug, feature request, my tickets, escalate, report a problem, contact support]
related:
  - user-guides/features/teacher/classroom/student-issues
  - user-guides/features/student/support/report-issues
  - user-guides/diagnostics/teacher
---

# Support Tickets

## Overview

**Support** at the bottom of the teacher sidebar opens **Help & Support**. The page is in two halves: a form for raising a ticket with the Classroom Token Hub team, and a **My Tickets** list of what you have already sent.

This form is for problems *you* hit as a teacher. It is not the route for a student's problem — see the note below.

## Step-by-step instructions

### Before you start

You need at least one class. Without one the page tells you so and refuses to submit; create a class first.

### Filling in the form

1. In the teacher sidebar, select **Support**.
2. **This issue applies to** — two choices only:

   | Choice | Use it when |
   | --- | --- |
   | *(your active class)* | The problem is with a class: its payroll, store, rent, roster, attendance |
   | My account (not class-specific) | Sign-in, your profile, billing, anything not tied to one class |

   Only the class you are currently in is offered. If the problem is in a different class, switch to it first using **Switch Class**, then come back.

3. Underneath, a grey line reads **We will know you as** and, for a class-scoped ticket, **We will know your class as**, each followed by a code. Those codes are how support identifies you. Quote them if you follow up by any other channel.
4. **Issue Type** (required) — *General Support*, *Bug / Error*, or *Feature Request*.
5. **Title** (required, 200 characters).
6. **What happened?** (required, 2000 characters). The useful version names the page, what you did, and what appeared.
7. **What did you expect to happen?** (optional, 1000 characters). Worth filling in for anything ambiguous — it is the difference between a bug report and a feature request.
8. **Page URL** (optional). The path where it happened, like `/admin/students`.
9. Select the submit button. It disables itself and shows *Submitting…* so a slow connection cannot send the ticket twice.

You get a confirmation that the ticket went to system administration, and the page reloads with it in the list.

### Reading My Tickets

**My Tickets** shows your most recent 20, newest first, filtered to your active class — plus every account-scoped ticket regardless of which class you are in. Switching classes changes the list.

Each entry shows the class label and join code it was filed under, the submitted date, the category, the first 220 characters of your description, and a status badge.

The statuses a ticket moves through are **Open**, **Teacher review**, **Escalated to dev**, **Dev resolved**, **Teacher final review**, and **Closed**. See the caution below about how they are displayed.

## Important notes

> [!IMPORTANT]
> **A student's problem has to start with the student.** You cannot open a ticket on a student's behalf from here. The student raises it from their own account, and it then reaches you for review — that queue is covered in [Student Issues](../classroom/student-issues.md). Only after that can it be escalated to the support team.

> [!WARNING]
> **The Title is not saved.** It is required, and it is discarded on submission — every entry in **My Tickets** is labelled *Support Ticket* regardless of what you typed, and support does not receive it either. Put anything that matters in **What happened?**, whose first 220 characters are what you will actually see in the list.

> [!CAUTION]
> **Two tickets with the same title, in the same scope, are treated as one submission.** The title is used for duplicate detection even though it is not stored. If a second ticket seems not to have been created, give it a different title.

> [!NOTE]
> **The status badge is always yellow.** The colour does not track the status — read the words, not the colour. The wording is also raw in places: an escalated ticket reads *Escalated_To_Dev*.

> [!NOTE]
> **There are no replies on this page.** My Tickets shows what you sent and where it has got to, not any response. Support replies arrive by whatever contact route your account is set up with.

> [!TIP]
> Fill in **Page URL** even when it feels obvious. It is the single most useful field for reproducing a problem, and it costs one copy-paste from your address bar.

## Related guides

- [Student Issues](../classroom/student-issues.md)
- [Report a Problem (Student)](../../student/support/report-issues.md)
- [Teacher Diagnostics](../../../diagnostics/teacher.md)
