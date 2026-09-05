---
title: Store Pricing Strategy
category: features
subcategory: teacher-economy
roles: [teacher]
description: Understand the Classroom Wage Index, read the four store tier bands, and interpret the live pricing warnings when you set an item's price.
keywords: [store pricing, CWI, classroom wage index, pricing tier, basic, standard, premium, luxury, recommended range, economic mode, long-term goal]
related:
  - user-guides/features/teacher/economy/store-items
  - user-guides/features/teacher/economy/economic-engine
  - user-guides/features/teacher/economy/payroll-settings
---

# Store Pricing Strategy

## Overview

Every store price in the app is measured against one number: your **Classroom Wage Index**, or CWI. This guide is about choosing the number you type into the **Price** field. The mechanics of the form — item types, bundles, inventory — are in [Store Items](store-items.md).

## Step-by-step instructions

### What the CWI actually is

The CWI is what a typical student earns in a week:

> **CWI = pay rate × expected weekly hours**

The pay rate comes from **Economy > Payroll > Settings**; the expected weekly hours are set on **Economy > Economic Engine**. You do not calculate anything yourself — supply those two and the app derives the rest.

This matters because **no pricing guidance exists without it.** Until both are set, the recommended-range box on the item form stays hidden and the price warnings do not appear. If you are seeing no guidance at all, check the CWI card on the Economic Engine page — it names whichever half is missing.

### Choosing a tier

**Pricing Tier (optional)** on the item form is the fastest way to a defensible price. Selecting one reveals **Recommended range** with a dollar figure computed from your CWI.

The four tiers, expressed as a share of one week's earnings:

| Tier | Share of CWI | What belongs here |
| --- | --- | --- |
| **Basic** | 1–3% | Small, frequent, low-stakes rewards |
| **Standard** | 2–5% | The everyday middle of your catalogue |
| **Premium** | 5–15% | Worth planning for — a few days of saving |
| **Luxury** | 15–30% | The top of the ladder, weeks of saving |

Those figures are for the **Default** economic mode. **Tight** narrows every band and **Comfortable** widens them, so the dollar range you see is the authority — read it rather than doing the percentage arithmetic yourself.

### Reading the warnings

As you type a price, the form checks it against the bands and tells you one of three things:

| What you see | What it means |
| --- | --- |
| *Price fits {TIER} tier: $X (Y.YYx CWI)* | Informational. The price landed inside a band. |
| *Price ($X) is below BASIC tier min ($Y). May not be a meaningful reward.* | A warning, not a block. Something this cheap is close to free. |
| *Price ($X) exceeds LUXURY tier max ($Y). Students may never afford this.* | Critical. The message adds: *Consider marking as 'Long Term Goal Item' if this is intentional.* |

None of these stop you saving the item. They are advice.

### Building a ladder, not a list

A catalogue priced entirely in one band gives students nothing to plan around. The useful shape spans the tiers:

1. **A few Basic items** that a student can buy the week they start. These teach that earning works.
2. **A working Standard middle.** This is where most purchases should happen.
3. **One or two Premium items** that require skipping a Basic purchase or two.
4. **A single Luxury item** as the visible top of the ladder.

Then leave it alone long enough to see what students actually buy. If nothing above Standard ever sells, either the top is priced wrong or the pay rate is too low — check the [Economic Engine](economic-engine.md) before re-pricing item by item.

## Important notes

> [!IMPORTANT]
> **The percentages in the tier dropdown do not match the ranges the app recommends.** The dropdown reads *Basic (2-5% of CWI)*, *Standard (5-10%)*, *Premium (10-25%)*, *Luxury (25-50%)* — but the **Recommended range** box beneath it is computed from the narrower bands in the table above. Trust the dollar range, not the label.

> [!WARNING]
> **Raising a price does not change what students already bought.** Purchases settle at the price in force when they were made. Re-pricing shapes future behaviour only.

> [!NOTE]
> **Long-Term Goal Item and Bypass CWI Warnings are not interchangeable.** The first excludes a genuinely expensive item from balance checks — the honest option for a real savings target. The second silences warnings *and* removes the item from Economy Health, so your economy's health picture stops accounting for it.

> [!TIP]
> Price against the CWI, not against real money. A $20 item is meaningless to a student until you know whether $20 is an afternoon or a month. The ratio in the warning message — *0.14x CWI* — is the number that tells you what you actually charged.

## Related guides

- [Store Items](store-items.md)
- [Economic Engine](economic-engine.md)
- [Payroll Settings](payroll-settings.md)
