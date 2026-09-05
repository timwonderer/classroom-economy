---
title: Store and Redemptions Troubleshooting
description: Why store items, stock, or redemptions behave unexpectedly.
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/transactions-banking
  - user-guides/diagnostics/teacher/rent-insurance
---

# Store and Redemptions Troubleshooting

Diagnostic guide for resolving issues with store visibility, purchases, and redemption tracking.

## Students cannot see or buy an item

### Symptoms
- An item you created is not visible in the student store.
- Students see the item but the purchase button is disabled.

### Causes & Solutions
**Cause 1: Item is inactive or delisted**
- **Check:** Look at the item status in Store Management.
- **Fix:** Items past their auto-delist date are hidden. Reactivate the item or change its end date.

**Cause 2: Item blocked from class period**
- **Check:** Verify the "Block Visibility" settings on the item.
- **Fix:** Change the visibility to include the student's current class period.

**Cause 3: Inventory limits reached**
- **Check:** Check the remaining inventory or per-student limits.
- **Fix:** Increase the inventory quantity or the per-student purchase limit in the item settings.

## Redemptions are stuck

### Symptoms
- Purchases never show up for teacher approval.
- An item is purchased but never fully "redeemed".

### Causes & Solutions
**Cause 1: Item type differences**
- **Check:** Identify whether the item is Immediate, Delayed, Collective, or Hall Pass.
- **Fix:** 
  - **Immediate** items auto-complete; they skip the approval queue entirely.
  - **Collective** items remain pending until their funding goal is reached.
  - **Hall Pass** items simply add to the pass balance and skip redemption status.
  - Only **Delayed** items require teacher approval to complete redemption.

## When to Contact Support
Report this issue if:
- An item is purchased successfully without a passphrase being provided.
- Inventory drops below zero into negative numbers.
