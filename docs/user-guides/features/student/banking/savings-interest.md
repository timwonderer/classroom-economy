---
title: Savings Interest
category: features
subcategory: student-banking
roles: [student]
description: Find your interest rate, read the 12-month savings projection, and understand what the chart is and is not promising you.
keywords: [savings, interest, interest rate, projection, chart, compound, simple, APY, payout, monthly interest]
related:
  - user-guides/features/student/banking/accounts-transfers
  - user-guides/diagnostics/student/money
---

# Savings Interest

## Overview

Savings can earn interest. Whether it does, and at what rate, is a setting your teacher controls — the app will not invent a rate to make the page look better.

Everything about interest lives on the **Accounts** page, on its first tab, also called **Accounts**.

## Step-by-step instructions

### Finding your rate

The **Statistics** card, to the right of your balances, carries four numbers. Two of them are about interest:

| Statistic | What it means |
| --- | --- |
| **Total Earnings** | Everything you have earned in this class |
| **Monthly Interest Rate** | Your class's annual rate divided by twelve, shown as a percentage |
| **Estimated Monthly Interest** | What one payout is worth on your savings balance right now |
| **Total Transactions** | How many entries are in your history |

**Monthly Interest Rate** is a *monthly* slice of an *annual* rate. If your class is set to 6% a year, this reads 0.50%. It is not a separate rate — it is the same rate expressed per month.

The **Transfer** tab states the same thing the other way round, in a blue **Tip** under the form: the annual rate, whether it is simple or compound, and *approximately $X per weekly payout* or *per monthly payout*.

### Reading the projection

Below Statistics, **Savings Balance Projection (12 Months)** draws a line from today out twelve months. Hovering a point shows *Balance: $NN.NN*. The horizontal labels are **Now**, then **Month 1** through **Month 12**.

The caption under the chart tells you exactly what it assumed:

> Projection based on current balance of **$X** with N.NN% annual compound interest (compounded monthly)

If your class has no rate set, it says so plainly instead:

> Savings interest is not currently configured for this class, so your balance of **$X** is projected flat.

A flat line is not a broken chart. It is the app declining to show you growth that is not configured.

### Simple and compound

The caption names which one your class uses.

- **Simple** — interest is worked out on the balance, period after period.
- **Compound** — interest is worked out on the balance *including interest already credited*, so the line curves upward instead of running straight. The caption also names how often it compounds.

Over one term the difference is usually small. Over the whole chart it is visible.

### When interest arrives

A credited payout appears in your history like anything else: **Accounts → Transactions → Savings**, with the type **Interest** and the description *Monthly Savings Interest*.

If you have never seen that line and your class does show a rate, ask your teacher — crediting interest is something they run, not something you can trigger.

## Important notes

> [!IMPORTANT]
> **The projection assumes you never touch the money.** It takes today's savings balance and grows it forward with nothing added and nothing removed. It is a picture of the rate, not a prediction of your behaviour. Every transfer out resets the line lower.

> [!NOTE]
> **Only savings earns.** Checking does not. That is the trade — savings grows but cannot be spent, checking can be spent but sits still. See [Accounts and Transfers](accounts-transfers.md).

> [!NOTE]
> **The chart has a text version.** The same month-by-month figures are published in a table beside the chart for screen readers, captioned *Projected savings balance by month*. Nothing in the chart is picture-only.

> [!TIP]
> Compare **Estimated Monthly Interest** against the price of something in the store. If a month of interest does not buy a pencil, the way to grow savings faster is a bigger balance, not a longer wait — the rate is fixed, the balance is the part you control.

## Related guides

- [Accounts and Transfers](accounts-transfers.md)
- [Troubleshooting Balances, Transfers, and Interest](../../../diagnostics/student/money.md)
