---
title: Teacher Dashboard Overview
category: features
subcategory: teacher-classroom
roles: [teacher]
description: Read the four dashboard stats, work the three approval queues, and understand the payroll estimate.
keywords: [dashboard, pending tasks, approvals, redemptions, hall passes, claims, next payroll, recent transactions, attendance log]
related:
  - user-guides/features/teacher/classroom/students-overview
  - user-guides/features/teacher/economy/store-redemptions
  - user-guides/features/teacher/economy/economic-engine
---

# Teacher Dashboard Overview

## Overview

**Teacher Dashboard** is the only page where all three approval queues appear together. Redemptions, hall passes, and insurance claims each have their own management page, but a teacher who works from those pages has to visit three places to find out whether anything needs them. The dashboard answers that in one number.

## Step-by-step instructions

### Reading the four stats

| Card | What it shows |
| --- | --- |
| **Active Students** | Headcount for the selected class |
| **Total Economy Value** | *Sum of all student account balances* |
| **Pending Tasks** | Everything waiting on you, broken into badges: *N orders*, *N claims*, *N passes* |
| **Next Payroll** | The date, plus *Est: $N* and, when available, *Updated [timestamp]* |

**Next Payroll**'s estimate is a projection, not a commitment. It is what payroll would cost at current settings and current hours. The *Updated* timestamp tells you how fresh that figure is — if it is stale, hours have been logged since it was calculated.

### Working the approval queues

**Pending Actions** appears only when something is actually pending. It carries a count in its heading and splits into three tabs, each badged with its own number.

**Redemptions** shows the student, the item, and — unlike the same queue on the Store page — the student's answer to the item's redemption prompt. Two controls per row: a red cancel icon labelled *Refund and remove*, and **Approve**.

**Hall Passes** shows the student, the pass reason, and the request time, with a **View** button that takes you to the hall pass page to act on it.

**Claims** shows the student, the claim description, the amount, and the filed date, with a **View** button through to insurance.

Each tab shows five at a time. Past that you get *Showing 5 of N pending [type]* and have to use the full page.

### Reading the activity panels

**Recent Transactions** lists Student, Action, and Amount — green for credits, red for debits — with **View All** through to the full ledger. Empty, it reads *No recent activity found.*

**Attendance Log** lists today's clock-ins and clock-outs with each student's status and period. Empty, it reads *No attendance logs today.*

### Setup banners

Two banners can appear above the stats:

- **Action Required: Setup Account Recovery** — *Your account security details are missing or outdated. Please update your security setup to enable student-assisted recovery.* Choose **Setup Now**.
- **Update insurance to the new tiered design** — *Your existing policies use the legacy setup. Group them into tiers so students see the modern plan layout.* Choose **Review policies**. This is a *One-time prompt for legacy policies*.

## Important notes

> [!IMPORTANT]
> **Approve redemptions from here, not from the Store page.** This queue shows the student's answer to the redemption prompt. The identical queue on **Economy > Store** renders a dash in that column instead, so approving there means approving without reading what the student asked for.

> [!WARNING]
> **Rejecting a redemption is not a refund.** The confirmation reads *Are you sure you want to reject this redemption? The request will be removed and the student will keep the entitlement.* The student keeps the item and can request again. To take the money back instead, use *Refund and remove*.

> [!NOTE]
> **Pending Actions hides itself when empty.** An absent section means nothing is waiting, not that something failed to load.

> [!TIP]
> Deal with the **Action Required: Setup Account Recovery** banner the day you see it. Student-assisted recovery is how you get back into your own account if you lose your credentials, and it only works if it was configured beforehand.

## Related guides

- [Store Redemptions](../economy/store-redemptions.md)
- [Student Management Overview](students-overview.md)
- [Economic Engine](../economy/economic-engine.md)
