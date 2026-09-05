---
title: Customizing Rent Behaviors
category: features
subcategory: teacher-bills
roles: [teacher]
description: Grace periods, late penalties, bill preview, partial payment, and blocking purchases while a student is overdue.
keywords: [rent, grace period, late penalty, recurring penalty, bill preview, incremental payment, partial payment, prevent purchase]
related:
  - user-guides/features/teacher/bills/rent-settings
  - user-guides/features/teacher/bills/rent-waivers
  - user-guides/features/teacher/bills/rent-itemization
  - user-guides/diagnostics/teacher/rent-insurance
---

# Customizing Rent Behaviors

## Overview

Setting the rent amount decides what students owe. These settings decide how the system treats them around it — how long they have, what it costs to be late, what they can see coming, and what they lose while overdue.

Both sections here are accordions on the **Settings** tab of **Bills > Rent**. Forgiving a charge a student has already missed is a separate job with its own tab — see [Rent Waivers](rent-waivers.md).

## Step-by-step instructions

### Grace periods and late penalties

Expand **Grace Period & Late Penalties** on the **Settings** tab.

| Field | What it does |
| --- | --- |
| **Grace Period (Days)** | *Days after due date before late penalty applies* |
| **Late Penalty Amount ($)** | *Fee charged for late payments* |
| **Penalty Application** | **Apply Once Per Rent Period** or **Apply Recurring** |
| **Recurring Every (Days)** | *Days between recurring penalty charges* — appears only when the penalty is recurring |

The choice between once-per-period and recurring is the difference between a fine and a meter. A once-per-period penalty is a fixed consequence a student can absorb and move past. A recurring penalty compounds until they pay, and a student who has genuinely run out of money cannot stop it by trying harder.

### Student payment options

Expand **Student Payment Options**. Three switches, each independent.

- **Enable Bill Preview** — *Students can see incoming bills before due date.* Turning it on reveals **Preview Days Before Due**: *How many days before due date students can see the bill.*
- **Allow Incremental Payment** — *Students can pay partial rent throughout the period before due date.*
- **Prevent Purchase When Late** — the label and its effect change depending on whether you have rent items configured:
  - With rent items: **Prevent Purchase of Items Not Part of Rent** — *When late on rent, students can only purchase items covered by rent (at à la carte prices), blocking all other store items.*
  - Without rent items: **Prevent Purchase/Redemption When Late** — *Block all store purchases and item redemptions if student is late on rent.*

Bill preview and incremental payment are the two that change student behaviour most. A student who cannot see the bill coming cannot plan for it, and a student who can only pay in one lump has to hold the full amount rather than chipping away.

## Important notes

> [!IMPORTANT]
> **A recurring penalty does not stop on its own.** It keeps applying every N days until the rent is paid or waived. If a student has fallen far enough behind that the penalty is outrunning their income, [waiving the assessment](rent-waivers.md) is the only way to break the cycle.

> [!WARNING]
> **Prevent Purchase When Late does not currently block anything.** The switch saves, and the **Settings** tab shows its badge, but no purchase path checks it — a student who is behind on rent can still buy freely. Do not rely on it as a consequence. Until it is fixed, enforce this by talking to the student.

> [!NOTE]
> **A student is not "late" until grace ends.** Lateness is measured from the end of the grace period, not from the due date, so a three-day grace means nothing keyed on lateness fires until day four.

> [!TIP]
> Turn on bill preview before you turn on penalties. A student who has never seen a bill coming and then gets fined for missing it learns that the system is arbitrary, which is the opposite of the lesson.

## Related guides

- [Rent Settings](rent-settings.md)
- [Rent Waivers](rent-waivers.md)
- [Rent Itemization](rent-itemization.md)
- [Rent and Insurance Troubleshooting](../../../diagnostics/teacher/rent-insurance.md)
