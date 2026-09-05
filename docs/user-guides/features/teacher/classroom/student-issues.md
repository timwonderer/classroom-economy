---
title: Student Issues
category: features
subcategory: teacher-classroom
roles: [teacher]
description: Work the student issue queue — review a ticket, resolve or escalate it, and close it out.
keywords: [issues, tickets, disputes, escalate, compensating transaction, deny issue, close ticket]
related:
  - user-guides/features/student/support/report-issues
  - user-guides/diagnostics/teacher/announcements-issues
---

# Student Issues

## Overview

**Student Issues** is a ticket queue. A student who thinks something is wrong — a charge they did not expect, a balance that looks off, a button that does not work — files a ticket instead of arguing about it verbally. Every ticket carries a snapshot of their account at the moment they filed, so you are not reconstructing the story from memory.

A ticket does not simply get "resolved". It moves through a short lifecycle, and it is not finished until you close it.

## Step-by-step instructions

### Opening the queue

1. In the teacher sidebar, open **Classroom**.
2. Select **Student Issues**.

Three tabs sit across the top, each with a count:

| Tab | What is in it |
| --- | --- |
| Pending Review | New tickets waiting for you |
| Teacher Final Review | Tickets you have acted on, or a developer has fixed, that still need closing |
| Escalated to Developer | Tickets you sent onward |

Each card shows the student, the category, an excerpt of their explanation, the submission time, and — if the ticket points at a specific charge — the transaction number.

### Reading a ticket

Open any card. The detail page gives you:

- **Student's Explanation** and their **Expected Outcome**
- **Related Transaction** — the ID, amount, description, account type, and whether it has already been voided
- **System Context** — their checking, savings, and total balance *at the time of submission*, plus their five most recent transactions
- **Resolution Actions** — anything already done, and by whom
- **Status History** — every state change with a timestamp

### Resolving it

In the **Actions** panel, pick a **Resolution Action**:

| Action | When to use it |
| --- | --- |
| Post Compensating Transaction | The charge was genuinely wrong. Posts an offsetting entry. Only offered when the ticket is tied to a transaction |
| Manual Adjustment (I'll handle it) | You are fixing it yourself elsewhere and want the ticket to reflect that |
| Deny Issue | The report does not hold up. A **Denial Reason** is required |

Add **Notes** if useful, then select **Resolve Issue**.

The ticket moves to **Teacher Final Review**. It is not closed yet.

### Closing it

Open the ticket from the **Teacher Final Review** tab. You will see the resolution you recorded. Write a **Closure Summary** — it is required — and select **Close Ticket**.

### Escalating a technical problem

If it is a platform bug rather than a classroom dispute, select **Escalate to Developer**.

1. Choose an **Escalation Reason**: Suspected Bug, Data Integrity Issue, Cannot Resolve with Available Tools, System Error, Feature Request, or Other.
2. Add **Diagnostic Notes** — what you tried, what you saw. Students cannot talk to developers, so your description is the only account anyone gets.
3. Optionally tick **Share class name/identifier with developer**. By default only an opaque reference is sent.
4. Select **Escalate Issue**.

When a developer has finished, the ticket comes back marked **Developer Fix Applied — Teacher Review Required**. Confirm things look right in your classroom, then close it.

## Important notes

> [!IMPORTANT]
> **Resolving is not closing.** A resolved ticket sits in **Teacher Final Review** until you write a closure summary. Check that tab regularly or tickets pile up in a half-finished state.

> [!NOTE]
> **The balances shown are historical.** System Context is a snapshot from submission time, not a live reading. It is there so you can see what the student saw.

> [!NOTE]
> **Escalation is a last resort.** Escalate when you suspect a system bug or data integrity problem, or when you genuinely cannot fix it with the tools you have — not as a way to hand off a judgement call.

> [!IMPORTANT]
> **Developers never see student names.** Escalated tickets carry a non-identifying reference and your notes. Do not put a student's name in the diagnostic note.

> [!NOTE]
> **This is not a chat system.** The student files once; you respond by resolving, denying, or escalating. Your denial reason and closure summary are what they read. If you need a conversation, have it in class.

> [!TIP]
> Write the closure summary as if the student is the only reader — because they are. "Refunded the $15 rent charge; it was posted twice on the 4th" beats "fixed".

## Related guides

- [Report Issues (Student)](../../student/support/report-issues.md)
- [Announcements and Issues Troubleshooting](../../../diagnostics/teacher/announcements-issues.md)
