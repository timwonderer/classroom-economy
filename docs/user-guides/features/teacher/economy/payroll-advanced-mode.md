---
title: Payroll Advanced Mode
category: features
subcategory: teacher-economy
roles: [teacher]
description: What the Advanced Mode toggle adds to payroll settings — time increments, overtime, rounding, custom schedules, and the pay simulator — and which of those actually change what students are paid.
keywords: [payroll, advanced mode, overtime, rounding, time increment, pay simulator, custom schedule, daily limit, auto run, automatic payroll]
related:
  - user-guides/features/teacher/economy/payroll-settings
  - user-guides/features/teacher/economy/payroll-run
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Payroll Advanced Mode

## Overview

The **Payroll Settings** card on **Economy > Payroll** has an **Advanced Mode** switch in its header. Simple mode asks four questions; advanced mode asks nine. The extra fields are not all live, so it is worth knowing which ones reach the ledger before you build a pay policy on them.

Underneath, payroll is one calculation: seconds worked since the last run, multiplied by a rate, rounded to the cent. Advanced mode changes how you *express* the rate and the schedule. It does not currently change that formula.

## Step-by-step instructions

### Switching modes

Flip **Advanced Mode** in the card header. The form swaps between two sets of fields, and the mode you were in when you pressed **Save Settings** is the one that is stored.

Saving clears the other mode's fields. Save in simple mode and overtime, the advanced daily limit, and rounding are reset; save in advanced mode and the simple daily limit is cleared. Nothing carries across, so treat a mode switch as a rewrite of the policy rather than an edit.

### Pay Amount and Time Increment

Advanced mode splits the rate in two: **Pay Amount** and a **Time Increment** of **Per Second**, **Per Minute**, **Per Hour**, or **Per Day**.

This is a data-entry convenience. Whatever you enter is converted to a single internal rate on save, so $0.25 per minute and $15.00 per hour are the same policy stored two ways. Pick whichever wording your students think in.

### Overtime

Ticking **Enable Overtime** opens four fields — **Threshold**, its **Unit**, a **Per** period of day, week, or month, and an **Overtime Multiplier** that must be at least 1.0.

These values save and reappear when you come back. They do not affect pay. Every second is paid at the base rate no matter how many hours a student accumulates. See *Important notes*.

### Daily Time Limit

This is the advanced form of the limit simple mode expresses as hours and minutes: a value plus a unit of seconds, minutes, or hours.

It works, and it is the one advanced setting that changes student behaviour. When a student reaches the limit they are automatically tapped out and cannot tap back in until the next day. The counter resets at midnight PST. Leave it blank for no limit.

### Pay Schedule

Advanced mode adds two options simple mode does not offer:

- **Daily** — a run every day
- **Custom** — reveals a number and a unit of **Day(s)** or **Week(s)**, so you can set something like every 10 days or every 3 weeks

**First Pay Date** anchors the calendar. The **Next Payroll** figure at the top of the page is calculated forward from that date and your frequency, so a manual run does not shift it.

### Rounding

**Round Down**, **Round Up**, or **Round to Nearest**, described on the form as applying *if time doesn't reach next increment*.

The choice is stored and does nothing. Pay is calculated from the exact elapsed time and rounded to the nearest cent regardless of which option you pick. See *Important notes*.

### Pay Simulator

The panel to the right of the form estimates earnings from your unsaved form values. Enter **Minutes per Class** and **Classes per Week**, then choose **Calculate** for a **Per Week**, **Per Month (4 weeks)**, and **Per Semester (18 weeks)** figure.

It reads the rate straight off the form, so it is accurate for the rate and honest about the parts of advanced mode that do not work — it ignores overtime and rounding, exactly as payroll does. It also ignores your **Daily Time Limit**, which payroll does *not*. If you have set a limit that your simulated day exceeds, the estimate will be too high.

Below the simulator, **Current Settings** narrates your form in plain English. Two of its sentences are unreliable — see *Important notes*.

### Validation

The form checks three things when you save and lists any failures in a red box above the button:

| Message | What it means |
| --- | --- |
| *Overtime multiplier must be ≥ 1.0* | A multiplier below 1.0 would make overtime a pay cut |
| *Maximum time per day overrides overtime. Consider disabling one of them.* | A student tapped out at the limit can never cross an overtime threshold above it |
| *Custom schedule requires a value* | You chose **Custom** without entering a number |

## Important notes

> [!CAUTION]
> **Overtime does not pay overtime.** The threshold, period, and multiplier all save and all redisplay, and none of them enter the pay calculation. A student who works twelve hours is paid twelve hours at the base rate. Do not promise students an overtime rate — set a base rate you are happy to pay for every hour worked.

> [!CAUTION]
> **Rounding is not applied.** All three options behave identically. Time is measured to the second and money is rounded to the cent, whatever the dropdown says. This matters most if you chose **Per Hour** or **Per Day** as your increment expecting partial periods to be dropped — they are not, and a student who works nine minutes of an hour is paid for nine minutes.

> [!WARNING]
> **Payroll does not start running on its own.** The in-page guide describes an *Auto run* setting and *attendance rules* for choosing which tap types count. Neither control exists on the form. A scheduled run only continues a schedule that nothing currently starts, so in practice payroll runs when you press **Run Payroll**. Put the payday in your own calendar and treat **Next Payroll** on this page as a reminder rather than a promise.

> [!NOTE]
> **The Current Settings summary misreports two things.** Its rounding sentence always reads *rounds down* no matter which option you selected, and its overtime sentence never appears even when overtime is enabled. The form fields themselves show what was saved — trust those over the summary.

> [!IMPORTANT]
> **Settings are per class.** One policy is stored for the class you currently have selected. If you teach several periods and want different rates, switch class context and save again for each one. Rate and schedule changes apply only to future runs; money already paid is never recalculated.

> [!TIP]
> Advanced mode earns its place when you want a **Daily** or **Custom** schedule, a per-second or per-day way of describing the rate, or a daily limit finer than whole minutes. If you only want a different hourly rate, simple mode does the same job with fewer ways to be misled.

## Related guides

- [Payroll Settings](payroll-settings.md)
- [Run Payroll](payroll-run.md)
- [Attendance and Payroll Troubleshooting](../../../diagnostics/teacher/attendance-payroll.md)
