---
title: Bundles, Bulk Discounts, and Collective Goals
category: features
subcategory: teacher-economy
roles: [teacher]
description: The three sale mechanics on the item form — what each one is meant to do, what it actually does today, and how to set up items so students are not misled.
keywords: [bundle, bundle quantity, bulk discount, collective goal, whole class, target purchases, goal deadline, store item, sale mechanics]
related:
  - user-guides/features/teacher/economy/store-items
  - user-guides/features/teacher/economy/store-pricing
  - user-guides/features/teacher/economy/store-redemptions
  - user-guides/diagnostics/teacher/store
---

# Bundles, Bulk Discounts, and Collective Goals

## Overview

The item form offers three ways to sell something as more than a single fixed-price purchase. [Store Items](store-items.md) covers the fields; this page covers the behaviour behind them.

Read *Important notes* before you build an item around any of the three. All three are partly or wholly unfinished, and two of them show students a promise the app does not keep.

## What each one is for

| Mechanic | The idea | What happens today |
| --- | --- | --- |
| **Bundle** | One purchase contains several uses, redeemed separately over time | The student gets **one** use. The buy screen promises several |
| **Bulk discount** | Buying several at once lowers the price | The student is **charged full price**. The buy screen shows the discount |
| **Collective goal** | The class buys toward a shared target | Progress counts correctly. Reaching the target and missing the deadline both do nothing |

## Step-by-step instructions

### Bundles

Tick **This is a Bundled Item** on the item form and set **Bundle Quantity**. The quantity must be greater than 1.

The catalogue then shows a *n bundle* badge on your card, and students see *Bundle: n items* on the browse card.

What the student is told at the moment of purchase is the problem. The buy modal reads *You will get 10 total uses (2 bundles)* — quantity times bundle quantity. What they actually receive is one item per unit bought, exactly as though the bundle setting were off. Nothing is tracked per use, so nothing draws down.

**Set up bundles as single rewards.** If you want to sell "5 homework passes," price one homework pass and let students buy five, or price the reward at what a single redemption is worth and leave the bundle box unticked.

### Bulk discounts

Tick **Enable Bulk Discount**, then set **Minimum Quantity for Discount** and **Discount Percentage (%)**. Both are required once enabled, the quantity must be greater than 1, and the percentage cannot exceed 100.

At the threshold, the student's buy screen recalculates: the hint reads *Bulk discount applied!*, **Total Price** drops, and a savings figure appears. Their account is debited the full undiscounted price.

The gap is silent on both sides. The student sees a lower number than they are charged, and you see nothing unusual — the ledger entry is simply the ordinary full-price purchase.

**Leave bulk discounts off.** If you want volume pricing, list a separate cheaper item for the larger amount and describe the deal in its name.

### Collective goals

Set **Item Type** to **Collective Goal**, then choose a **Collective Goal Type**:

- **Fixed Number of Purchases** — you set **Target Number of Purchases**.
- **Whole Class Must Purchase (1 per person)** — the target follows your class size and updates as your roster changes.

**Goal Expiration Date** is required for this item type.

Progress is the part that works. Both your card and the student's browse card show a *count/target* bar, counted as **distinct students who have purchased**, scoped to the class you are viewing — so a student buying twice moves the bar once, and one class's progress never bleeds into another's.

Everything after the bar is unfinished:

- **Reaching the target does nothing.** The student's card changes to *Goal reached! Item will unlock soon.* No unlock follows, no one is notified, and no fulfillment is recorded. Note that students have already bought and paid for the item in order to move the bar — the "unlock" language describes an intent, not a step.
- **Missing the deadline does nothing.** The item does not deactivate. It stays on sale at the same price, and its bar keeps counting.

**Treat the deadline as your own calendar entry.** Watch the bar, and when the date arrives, decide what happens and do it by hand — deactivate the item on the Store page, or announce the reward and let it run.

## Deciding what to build

Given the above, three item shapes are safe to build today:

1. **A plain reward** — name, price, tier. This is fully working and is what most items should be.
2. **A collective goal you personally adjudicate** — set the target, watch the bar, deliver the reward yourself, deactivate the item when you are done with it.
3. **A long-term goal item** — for an expensive reward students save toward. See [Store Pricing Strategy](store-pricing.md) for how that interacts with the Classroom Wage Index.

Bundles and bulk discounts have no safe shape until they are fixed, because both mislead the student at the point of sale rather than simply failing to work.

## Important notes

> [!CAUTION]
> **Do not tick "This is a Bundled Item."** The purchase screen tells the student they will receive quantity × bundle quantity uses. They receive one per unit bought. There is no per-use counter behind a bundle, so a student who buys a "5-pack" gets a single redemption and has been charged for a pack. Price the reward as one item instead.

> [!CAUTION]
> **Do not enable Bulk Discount.** At the threshold the student's screen shows a reduced **Total Price** and a savings line, and then their account is debited the full price. Neither of you gets a warning; the transaction looks ordinary in the ledger. If you want a volume deal, list it as its own item.

> [!WARNING]
> **A collective goal deadline is not enforced.** Nothing deactivates the item when the date passes and nothing happens when the target is met. Both are yours to act on. If you set a deadline, put it in your own calendar.

> [!NOTE]
> **Collective progress counts students, not purchases.** The bar moves once per student who has bought the item, within the class you are viewing. A student buying a second copy does not advance it, and each class period tracks its own progress against its own target.

> [!TIP]
> **Whole Class Must Purchase** is the more forgiving of the two goal types, because its target follows your roster. If a student joins or leaves mid-goal, the target moves with them instead of stranding the class one purchase short of a number you set weeks earlier.

## Related guides

- [Store Items](store-items.md)
- [Store Pricing Strategy](store-pricing.md)
- [Store Redemptions](store-redemptions.md)
- [Store and Redemptions Troubleshooting](../../../diagnostics/teacher/store.md)
