---
title: Rent Settings
category: features
subcategory: teacher-bills
roles: [teacher]
description: Set the rent amount, choose how often it comes due, pick the first due date, and read who is current and who is behind.
keywords: [rent, amount, frequency, custom period, due date, day of month, roster, behind on rent, CWI]
related:
  - user-guides/features/teacher/bills/rent-behaviors
  - user-guides/features/teacher/bills/rent-itemization
  - user-guides/features/teacher/economy/economic-engine
---

# Rent Settings

## Overview

**Bills > Rent** opens **Rent Management**, a three-tab page:

- **Overview** — what rent is currently set to, and which students are current or behind
- **Settings** — the five collapsible sections where you configure everything
- **Waivers** — forgiving a specific unpaid assessment

This guide covers the Overview tab and the first two Settings sections: how much rent is, how often it comes due, and when the first one lands. Grace periods, penalties, and student payment options are in [Customizing Rent Behaviors](rent-behaviors.md); breaking rent into line items is in [Rent Itemization](rent-itemization.md).

## Step-by-step instructions

### Reading the Overview tab

Two cards head the tab: **Current on Rent** and **Behind on Rent**, each a headcount.

**Current Rent Configuration** below them is read-only — it reflects what you saved, not somewhere to edit:

| Field | What it shows |
| --- | --- |
| **Rent Amount** | The amount with its frequency suffix — *per day*, *per week*, *per month*, or *every X [unit]* |
| **Late Penalty** | The amount, plus *once per period* or *every X days* |
| **Grace Period** | Days |
| **First Due Date** | A date, or *Day X of each month* |
| **Current Rent Period** | A date range, or *Not active yet* |
| **Next Due Date** | A date, or *Not scheduled yet* |

Badges beneath show which behaviours are on: **Bill Preview** (with its day count when enabled), **Incremental Payment**, **Prevent Purchase When Late**, and **Total Students**. Green means on, grey means off.

**Student Roster** splits the class into a green **Current** section and a red **Behind** section. Behind rows read *Behind by X cycle* or *Behind by X cycles* — cycles, not days, so a student two periods in arrears is visibly worse off than one who is a day late. With no students it reads *No students in class yet.*

### Setting the amount and frequency

Open the **Settings** tab and expand **Rent Amount & Frequency**.

- **Rent Amount ($)** — *How much students pay per rent period*
- **Payment Frequency** — **Per Day**, **Per Week**, **Per Month (30 days)**, or **Custom**

Choosing **Custom** reveals two more fields: **Custom Period Value** (*Number of time units*) and **Custom Period Unit** (**Days** / **Weeks** / **Months**). The section header then carries a **Custom** badge so you can see at a glance that this class is not on a standard cycle.

**Bypass CWI Warnings** sits at the bottom of this section: *Suppress live CWI warnings for rent and hide rent notes from Economy Health for this class.*

### Setting when rent comes due

Expand **Due Date Settings**.

- **First Rent Due Date** — *When the first rent payment is due (subsequent payments calculated from this)*
- **Due Day of Month (for monthly frequency)** — *Day of month rent is due (1-31, only used for monthly frequency)*

These two are not alternatives. The first due date anchors the whole schedule for every frequency. The day-of-month field only does anything when frequency is monthly, and it is what keeps rent landing on the 1st rather than drifting by 30-day steps.

Once a value is set, the section header shows an **Active** badge.

### Saving

**Save Settings** at the bottom of the tab commits every section at once, not just the one you expanded.

## Pricing rent against the economy

Rent is checked live against your Classroom Wage Index. When payroll is configured, the page shows a recommended range based on expected weekly hours — rent that consumes most of a student's earnings leaves nothing for the store, and rent that costs less than a snack teaches nothing.

If payroll is not configured yet, a **Payroll Configuration Warning** banner appears at the top of the Settings tab explaining what is missing.

## Important notes

> [!IMPORTANT]
> **Set payroll before you set rent.** Rent is priced as a share of what students earn. Without payroll configured there is no wage index to price against, and the page will tell you so.

> [!NOTE]
> **The Overview tab is a mirror, not a control panel.** Every value there comes from the Settings tab. If a figure looks wrong, fix it in Settings and save — there is nothing to click on Overview.

> [!TIP]
> Pick a **First Rent Due Date** a week or two after you launch the economy. Students need at least one payroll run in the bank before the first bill arrives, or rent begins as a debt rather than a decision.

## Related guides

- [Customizing Rent Behaviors](rent-behaviors.md)
- [Rent Itemization](rent-itemization.md)
- [Economic Engine](../economy/economic-engine.md)
