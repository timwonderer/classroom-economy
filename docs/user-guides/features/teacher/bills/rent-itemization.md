---
title: Rent Itemization
category: features
subcategory: teacher-bills
roles: [teacher]
description: Break rent into named items — privileges, per-use goods, and hall passes — and decide which ones students can buy separately in the store.
keywords: [rent, itemization, privilege, per-use, hall pass, free uses, store price, available in store]
related:
  - user-guides/features/teacher/bills/rent-settings
  - user-guides/features/teacher/bills/rent-behaviors
  - user-guides/diagnostics/teacher/rent-itemization
---

# Rent Itemization

## Overview

Flat rent is a number students pay. Itemized rent is a list of things they get for paying it — a desk, a locker, two hall passes, three free worksheet prints.

Itemization lives inside **Bills > Rent**, on the **Settings** tab, in the **Rent Itemization (Optional)** section. It is not a separate tab. The section header shows either *X items* or *Not configured*.

Itemization is optional, and it does not change what rent costs. It changes what rent *means*, and it opens a second path: students who are not paying rent can buy individual items from the store instead.

## Step-by-step instructions

### Adding an item

Expand **Rent Itemization (Optional)** and choose **Add Rent Item**. Before you add anything the section reads *No rent items configured yet. Click "Add Item" to get started.*

Each item takes a name and an optional description, then a type. The type is the decision that matters.

| Type | What it is | What it grants |
| --- | --- | --- |
| **Privilege** | *Standard rent benefit (e.g. Desk, Locker).* Ongoing, not countable | Valid until the next rent due date |
| **Per-Use Item** | *Consumable item (e.g. Pencil, Snack). Always available in store.* Countable | A number of free uses per period |
| **Hall Pass** | *Adds to student hall pass balance upon rent payment.* | A fixed number of passes |

The page states the distinction directly: *Privileges are ongoing, non-countable benefits (sit in teacher's chair, choose music). Per-use items are countable services or goods (print worksheet, borrow pencil, phone call home, late work pass).*

### Configuring by type

**Privilege** items offer **Available in Store** — *Allow students to buy this privilege separately (expires next rent due date)*. Tick it and a **Store Price ($)** field appears. Duration is not configurable: *Privilege duration: Always per-period (valid until next rent due date).*

**Per-Use Item** always requires a **Store Price ($)**, and adds **Free Uses Per Period** — *Rent payers get this many free uses per period.* This is the mechanism that makes itemization worth the effort. A student who pays rent gets three free prints; a student who did not pays per print. Same item, two prices, and the difference is visible on the store page.

**Hall Pass** items take **Passes Granted** — *Number of hall passes added when rent is paid.*

### Saving

Items save with the rest of the Settings tab via **Save Settings**. The page warns: *Items marked as "Available in Store" will be automatically added to your class store when you save. If you uncheck this option, the store item will be deactivated.*

## When the Store feature is off

If the Store feature is disabled for the class, the section shows: *Store feature is turned off for this class. You can still configure rent items, but none will be added to the store — the "Available in Store" option is disabled and per-use items won't appear in the store — until you enable the Store feature in Economy Features.*

You can build the whole item list in advance; nothing reaches students until the feature is on.

## Important notes

> [!IMPORTANT]
> **Rent items own their store entries.** An item you publish here appears in **Economy > Store** carrying a **Rent Perk** badge and the note *Managed by rent settings*. Its Deactivate control is disabled there and Delete is not offered at all. This page is the only place to change or retire it.

> [!NOTE]
> **Unticking "Available in Store" deactivates rather than deletes.** The store item is hidden from students but its purchase history survives. Re-ticking the box brings it back.

> [!TIP]
> Itemize before you raise rent. A rent increase reads as a tax; the same increase alongside a list of what it buys reads as a price. Students argue with the number far less when they can see the line items.

## Related guides

- [Rent Settings](rent-settings.md)
- [Customizing Rent Behaviors](rent-behaviors.md)
- [Store Items](../economy/store-items.md)
- [Rent Itemization Troubleshooting](../../../diagnostics/teacher/rent-itemization.md)
