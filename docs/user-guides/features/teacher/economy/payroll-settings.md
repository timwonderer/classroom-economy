---
title: Payroll Settings
category: features
subcategory: teacher-economy
roles: [teacher]
description: Configure pay rates, block settings, and payroll behavior.
keywords: [payroll, pay rate, settings, blocks]
related:
  - user-guides/features/teacher/economy/payroll-advanced-mode
  - user-guides/features/teacher/economy/payroll-run
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Payroll Settings

## Overview

Payroll settings control how students earn pay from their attendance records. The **Payroll Settings** card on **Economy > Payroll** opens in **Simple Mode** — four fields — with an **Advanced Mode** switch in its header for finer control.

## Step-by-step instructions

### Configuring pay in Simple Mode

1. Navigate to **Economy > Payroll** and open the **Settings** tab.
2. Set the **Pay Rate** — an amount per hour of attendance.
3. Choose a **Payroll Frequency** of **Weekly**, **Bi-weekly**, or **Monthly**, and a **Starting Date (First Payday)**.
4. Optionally set a **Daily Time Limit** in hours and minutes. A student who reaches it is automatically tapped out and cannot tap back in until the next day; the counter resets at midnight PST. Leave both boxes blank for no limit.
5. Choose **Save Settings**.
6. Use the **Pay Simulator** beside the form, or the preview tables on the Overview tab, to confirm the rate produces the earnings you expect.

Settings are stored for the class you currently have selected. If you teach several periods and want different rates, switch class context and save again for each one.

## Important notes

> [!IMPORTANT]
> Payroll calculations rely on "Start Work" and "Break" or "Done" taps from the Attendance Log. You must confirm that attendance taps are enabled and being used correctly for each class period for payroll to calculate.

> [!WARNING]
> **Press Run Payroll yourself.** Despite what the in-page guide says about auto-run, payroll does not currently start on its own — see [Payroll Advanced Mode](payroll-advanced-mode.md) for the detail. The **Next Payroll** date on this page is a calculated reminder, not a scheduled job.

> [!NOTE]
> Rate and schedule changes affect future runs only. Payments already made are never recalculated.

## Related guides
- [Payroll Advanced Mode](payroll-advanced-mode.md)
- [Run Payroll](payroll-run.md)
- [Attendance and Payroll Troubleshooting](../../../diagnostics/teacher/attendance-payroll.md)
