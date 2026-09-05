---
title: Store Redemptions
category: features
subcategory: teacher-economy
roles: [teacher]
description: Work the pending redemption queue, read purchase statuses, and know why the Redemption Audit tab cannot answer what happened.
keywords: [store, redemptions, approve, refund, purchase history, audit log, entitlement status]
related:
  - user-guides/features/teacher/economy/store-items
  - user-guides/features/teacher/classroom/student-detail
  - user-guides/diagnostics/teacher/store
---

# Store Redemptions

## Overview

Buying and receiving are two separate events for **Delayed Use** items. The student pays when they buy; they receive when you approve. Three of the five tabs on **Economy > Store** cover the gap between those moments: **Overview** holds the live queue, **Purchase History** is the full record, and **Redemption Audit** presents itself as a searchable trail but is not one.

## Step-by-step instructions

### Working the queue

The **Overview** tab opens on **Store Statistics** — **Total Items**, **Active Items**, **Total Purchases** — with **Quick Actions** shortcuts to **Add New Item** and **View Purchase History** beside it.

Below those sits **Pending Redemption Requests**, the part you act on:

| Column | What it shows |
| --- | --- |
| Student | Who asked |
| Item | What they bought |
| Requested | When the purchase happened |
| Details | Currently always shows a dash — see the warning below |
| Action | The refund and approve controls |

Each row offers two things. The green **Approve** button hands the item over and closes the request. The outlined cancel icon is labelled *Refund and remove* — it returns the money and takes the request off the queue.

If the item had a **Redemption Prompt**, the student's answer does not appear in this table. Read it on your **Dashboard** approval queue or on the student's detail page instead.

Beneath the queue, **Recent Purchases** lists Student, Item, Price, Purchased, and Status. When nothing has been bought yet it reads *No purchases yet*.

### Reading a purchase status

Purchases carry one of seven states, and they are not all things you caused:

| Badge | Meaning |
| --- | --- |
| **Purchased** | Paid for, not yet acted on |
| **Pending** | Waiting in your redemption queue |
| **Processing** | Mid-flight |
| **Redeemed** | The student has used it |
| **Completed** | Finished |
| **Expired** | The item's expiry window ran out before it was used |
| **Revoked** | Withdrawn |

**Expired** is the one worth watching. It comes from the **Item Expiry in Days** setting on the item, not from anything you did — a student who buys a delayed-use item and never redeems it will eventually land here.

### Purchase History

The **Purchase History** tab is the complete record: **All Purchases**, showing Student, Item, Purchase Date, Status, and Quantity. Immediate-use items appear here directly, having never touched the queue.

### Redemption Audit

The **Redemption Audit** tab looks like a searchable history of requests and their outcomes. It is not one, and it will not answer the question its name implies.

The controls are a filter bar — **Student**, **Class**, **Action** (**Request**, **Approved**, **Rejected**, **All actions**), and **From** / **To** dates — over a paginated table of Student, Class, Date, Action, and Notes, with **Apply Filters** and **Clear**. Empty it reads *No audit records found.*

What sits behind it is the **unresolved** request queue — the same requests waiting on the Overview tab. A request's row is discarded the moment you approve or reject it, so an outcome is never recorded here. That makes the **Approved** and **Rejected** filter options unmatchable by construction, and it means an empty table tells you only that nothing is currently waiting.

The rest of the tab is unfinished in ways worth knowing before you spend time on it:

- The **Action** column shows the same internal code on every row rather than naming the action.
- Typing anything into **Student** and applying the filter produces an error page.
- **Class** cannot widen the search — the tab only ever shows the class you have selected, whatever the dropdown says.
- **Notes** shows the request's raw stored data rather than readable text, and rows may appear duplicated.

**Use Purchase History instead.** It is the tab that actually holds the record.

## Important notes

> [!WARNING]
> **Approve from the Dashboard when the item asks students a question.** The **Details** column on this page always renders a dash, so a redemption prompt's answer is invisible here. The same queue on your **Dashboard** shows the answer, as does the student's detail page.

> [!IMPORTANT]
> **Refunding is the only way to reverse a request.** There is no "undo approve." Once you approve, the entitlement is handed over and the queue row is gone.

> [!NOTE]
> **Immediate-use items never reach you.** They are granted at purchase and appear only in Purchase History. If you want a say in when a student gets something, it has to be a **Delayed Use** item.

> [!CAUTION]
> **Redemption Audit is not an audit trail.** It holds only requests still waiting on you, and it drops a request as soon as you approve or reject it — so the outcome you want to look up is precisely the thing it never keeps. Do not use it to settle a dispute, and do not read an empty table as evidence that nothing happened.

> [!TIP]
> When a student insists they bought something they never received, sort **Purchase History** by Student. The purchase and its current status sit on one row, which is the closest thing to a record the page offers. Their [student detail page](../classroom/student-detail.md) carries the same purchase under its Items tab if you would rather look at one student at a time.

## Related guides

- [Store Items](store-items.md)
- [Store and Redemptions Troubleshooting](../../../diagnostics/teacher/store.md)
