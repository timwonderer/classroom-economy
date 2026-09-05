---
title: Interest and Payouts
category: features
subcategory: teacher-economy
roles: [teacher]
description: Set the APY, choose simple or compound growth, and understand why compounding and payout are two different settings.
keywords: [interest, savings, APY, simple, compound, compound frequency, payout frequency, economic engine]
related:
  - user-guides/features/teacher/economy/banking-settings
  - user-guides/features/teacher/economy/banking-overdraft
  - user-guides/features/teacher/economy/economic-engine
---

# Interest and Payouts

## Overview

Savings interest is the only way a student's money grows without them doing anything. It is what makes a savings account meaningfully different from a second pocket.

The controls live in the **Savings Interest** block on the **Settings** tab of **Economy > Banking**.

## Step-by-step instructions

### The four controls

| Control | What it does |
| --- | --- |
| **Annual Percentage Yield (APY %)** | *Annual yield applied to savings balances. Set 0 to disable interest.* |
| **Interest Type** | **Simple (accrued interest does not compound)** or **Compound**. *Simple interest never compounds; compound interest grows on prior interest.* |
| **Compound Frequency** | **Daily**, **Weekly**, or **Monthly**. *How often compound interest is applied. Ignored for simple interest.* |
| **Payout Frequency** | **Weekly** or **Monthly**. *How often interest is paid into savings accounts.* |

Finish with **Save Banking Settings**.

### Compounding is not payout

These two settings are routinely confused, and they answer different questions.

**Compound Frequency** asks: how often does earned interest start earning interest of its own? **Payout Frequency** asks: how often does the money actually appear in the student's savings account?

You can compound daily and pay out monthly. The student sees one deposit a month, but it was calculated on a balance that grew every day.

If **Interest Type** is **Simple**, the compound setting does nothing at all. Interest is always calculated on the original balance, never on interest already earned.

### Choosing simple or compound

Simple interest is predictable and easy for students to compute by hand — useful if you want them to check your maths. Compound interest is the concept most teachers actually want to demonstrate, but it accelerates, and it accelerates fastest for the students who already have the most saved.

The page shows an Economic Engine advisory ceiling for your APY. You can exceed it, but you will be warned. The reason is that a high compounding rate inflates the class money supply faster than payroll can be adjusted to compensate.

## Important notes

> [!IMPORTANT]
> **Rate changes are not retroactive.** *Saving creates a new economic-engine version. Rate changes affect future payouts only.* Interest already paid stays paid. Cutting the APY does not claw anything back.

> [!NOTE]
> **When interest is off, the Overview tab says so.** The **Current Savings Interest** card reads *Interest is off. Set a small APY in the Settings tab to reward saving.* That is the first thing to check if students report their savings are not growing.

> [!TIP]
> Start low, compound monthly, pay out monthly. You can always raise the rate after watching a month of real balances. Lowering it later feels to students like a punishment, even though nothing was taken away.

## Related guides

- [Banking Settings](banking-settings.md)
- [Overdraft Rules](banking-overdraft.md)
- [Economic Engine](economic-engine.md)
