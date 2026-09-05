---
title: Banking Settings
category: features
subcategory: teacher-economy
roles: [teacher]
description: Navigate Banking Management — read the Overview statistics, filter and void transactions, and find the two settings blocks.
keywords: [banking, banking management, overview, transactions, void, filters, savings, checking, deposits, settings tab]
related:
  - user-guides/features/teacher/economy/banking-interest
  - user-guides/features/teacher/economy/banking-overdraft
  - user-guides/features/teacher/economy/transactions
  - user-guides/diagnostics/teacher/transactions-banking
---

# Banking Settings

## Overview

**Economy > Banking** opens **Banking Management**, a three-tab page. **Overview** and **Transactions** tell you what has already happened; **Settings** decides what happens next.

This guide covers the page itself. The two settings blocks are big enough to have their own guides: [Interest and Payouts](banking-interest.md) and [Overdraft Rules](banking-overdraft.md).

## Step-by-step instructions

### Reading the Overview tab

**Banking Statistics** gives you four numbers:

| Statistic | What it counts |
| --- | --- |
| **Total Checking** | Money available to spend right now, across the class |
| **Total Savings** | Money set aside earning interest |
| **Total Deposits** | Checking and savings combined |
| **Students w/ Savings** | How many students are saving, out of the total |

That last one is the interesting one. It is a ratio, not a total, and it is the quickest read on whether saving has caught on in your class.

Beside it, **Current Savings Interest** shows the **Savings APY** and **Payout Frequency** in force. If no rate is set, it adds: *Interest is off. Set a small APY in the Settings tab to reward saving.*

Below both, **Recent Transaction Activity** lists the last ten entries with Date, Student, Type, Account, Amount, and Description. **View All Transactions** jumps to the next tab. When there is nothing yet it reads *No recent transactions found.*

### Finding a transaction

The **Transactions** tab lists **All Banking Transactions** behind five filters: **Account** (checking or savings), **Type**, **From**, **To**, and **Student**. Choose **Apply Filters**, or **Clear Filters** to start over. A counter beside the buttons reads *Showing N of N transactions*.

Student names link through to that student's detail page, so this tab is a reasonable starting point for "why is this balance wrong."

### Voiding a transaction

Each row has a cancel button in its **Actions** column. Choosing it asks *Are you sure you want to void this transaction? This cannot be undone.*

A voided transaction is not deleted. Its row greys out, the amount gains a **VOID** badge, and the Actions column reads **Voided** from then on.

### Finding the settings

The **Settings** tab holds two cards side by side — **Savings Interest** on the left, **Overdraft** on the right — and one **Save Banking Settings** button beneath them that commits both.

## Important notes

> [!IMPORTANT]
> **One save button covers both cards.** Editing the interest rate and the overdraft fee is a single save. If you only meant to change one, check the other before committing.

> [!WARNING]
> **Voiding cannot be undone.** There is no un-void. The transaction stays visible as a struck-through audit record, which is the point — but the money movement it reversed is not coming back.

> [!NOTE]
> **Every save creates a new economic-engine version.** *Rate changes affect future payouts only.* Your class's economic history is preserved rather than rewritten.

> [!TIP]
> Check **Students w/ Savings** before adjusting the APY. If the ratio is low, the problem is usually that students do not know savings exists, not that the rate is too small.

## Related guides

- [Interest and Payouts](banking-interest.md)
- [Overdraft Rules](banking-overdraft.md)
- [Transactions](transactions.md)
- [Transactions and Banking Troubleshooting](../../../diagnostics/teacher/transactions-banking.md)
