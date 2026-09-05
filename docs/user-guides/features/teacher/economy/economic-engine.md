---
title: Economic Engine
category: features
subcategory: teacher-economy
roles: [teacher]
description: Read your CWI, check the economic balance alerts, and use the recommended pricing ranges.
keywords: [economic engine, economy health, CWI, wage index, balance, recommendations, affordability]
related:
  - user-guides/economy_guide
  - user-guides/features/teacher/economy/policy-mode-rebalancer
  - user-guides/features/teacher/economy/interpretation
---

# Economic Engine

## Overview

The Economic Engine is the page that tells you whether your classroom economy adds up. It answers one question in several ways: **can a student who shows up and works afford the life you are charging them for?**

Everything on the page is built on one number — the **Classroom Wage Index (CWI)**, the amount a student with perfect attendance earns in a week.

> CWI = pay rate × expected weekly hours

Rent, insurance premiums, fines, and store prices are all judged against it.

## Step-by-step instructions

### Opening the page

1. In the teacher sidebar, open **Economy**.
2. Select **Economic Engine**.

### Setting up CWI

CWI needs two inputs. If either is missing the page tells you so and the pricing recommendations stay switched off.

1. **Pay rate** comes from payroll. If you have not configured payroll, a banner sends you to Payroll Management. Do that first.
2. **Expected hours per week** is set here, on this page — not in payroll settings. Enter how many hours a week your class actually works and select **Update**. The box accepts 0.25 to 80 hours.

Until you set it, the card is badged **Needs setup** and warns that CWI is undefined. Once both inputs exist the badge reads **In-Use**, and the card shows your weekly CWI, the pay rate per minute and per hour, and the expected hours it used. Calculation notes below explain how the figure was derived.

> [!NOTE]
> Rent, insurance, and the store still function without a CWI. Only the *recommendations* are disabled.

### Reading the Economic Balance alerts

The **Economic Balance** card checks your prices against CWI and sorts what it finds into three buckets:

| Bucket | What it means |
| --- | --- |
| Action Needed | Something is far enough out of line to distort the economy |
| Monitor | Worth watching, not urgent |
| Heads Up | Informational |

The card header reads **Balanced**, **Needs attention**, or **Awaiting payroll setup**. Below it, each affected feature is listed with a count of action items and a link straight to that feature's settings.

The **Additional Information** panel at the bottom of the page lists every individual alert, sorted by severity, each with the specific message and an **Open settings** link.

### Using the recommended ranges

The **Current Recommended Settings** card converts your CWI into concrete numbers:

- a weekly rent range, with an ideal value
- a weekly insurance premium range
- a fine range per incident
- store price tiers that scale with CWI
- a minimum amount students should be able to save each week

Beneath it are four shortcuts — **Review payroll**, **Tune rent**, **Adjust insurance**, **Update store** — that take you to the page where you would act on the recommendation.

### Banking and interest

A separate **Banking & Interest** card reports whether your interest settings are balanced and, when configured, shows the APY and payout schedule with a link to banking settings.

## Important notes

> [!IMPORTANT]
> **This page is scoped to the class you have selected.** Expected hours, CWI, alerts, and recommendations all belong to the current class. Switching classes changes every number on the page.

> [!NOTE]
> Changing expected hours changes CWI immediately, which changes every recommendation on the page at once.

> [!TIP]
> Recommendations are ranges, not rules. Being at the edge of a range is fine if it is deliberate. What matters is that a diligent student can cover their bills and still save something.

## Related guides

- [Economic Policy and Rebalancing](policy-mode-rebalancer.md)
- [Classroom Economy Guide](../../../economy_guide.md)
- [Interpretation](interpretation.md)
- [Payroll Settings](payroll-settings.md)
- [Banking Settings](banking-settings.md)
