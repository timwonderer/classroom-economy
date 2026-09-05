---
title: Hall Pass Configuration
category: features
subcategory: teacher-classroom
roles: [teacher]
description: What the Hall Pass Configuration page offers, what your class actually runs on today, and why saving does not stick.
keywords: [hall pass setup, pass types, queue limit, simultaneous limit, destinations, bathroom, master toggle, configuration]
related:
  - user-guides/features/teacher/classroom/hall-pass
  - user-guides/diagnostics/teacher/hall-pass
  - user-guides/features/student/work/hall-passes
---

# Hall Pass Configuration

## Overview

**Hall Passes → Configure** opens **Hall Pass Configuration**, where you would set your destinations and their limits.

Read the warning at the top of *Important notes* before you spend time on this page. The page does not currently save, and your class runs on a fixed set of five destinations regardless of what you enter here.

## What your class actually uses

Until the page is fixed, every class uses the same five built-in destinations, each with a queue limit of 10:

- Bathroom
- Water Fountain
- Office
- Nurse
- Counselor

These are what the approval queue on the [Hall Pass](hall-pass.md) page works against.

## Step-by-step instructions

### Reading the page

**How It Works** at the top defines the six controls:

| Control | What it is meant to do |
| --- | --- |
| **Master Toggle** | Turn the whole hall pass system on or off |
| **Pass Type Toggle** | Turn one destination on or off |
| **Queue Limit** | Most students approved and waiting for that destination. Blank means unlimited |
| **Simultaneous Limit** | Most students out at once for that destination. Blank means unlimited |
| **Total Queue Limit** | Cap on approved-and-waiting across all destinations |
| **Total Simultaneous Limit** | Cap on students out across all destinations |

Below that, the **Hall Pass System** switch reads *Currently enabled* or *Currently disabled*. Switching it off greys out every destination row and locks its toggle; hovering a locked toggle explains *You must enable hall pass first*.

### The Pass Types card

The card lists your destinations, each with a name, an on/off switch, a red delete button, and its two limit fields.

Because the page cannot read your saved configuration, this list always opens empty, reading *No pass types configured. Add one to get started.*

**Add New Pass Type** opens a modal asking for a **Pass Type Name** and, optionally, a **Queue Limit** and a **Simultaneous Limit**. Both limit boxes show *Unlimited* as their placeholder — leaving them blank means no cap. The modal rejects a blank name, a duplicate name, and any negative number.

Adding or removing a destination changes only what is on screen; the page reminds you with *Pass type added. Don't forget to save!*

### Total Limits

The two **Total Limits** boxes below the list are usually greyed out and calculated for you, reading *Calculated from individual pass type limits* — they simply add up the per-destination limits.

They unlock only when at least one enabled destination has an unlimited limit, since there is then nothing to add up. When unlocked, they enforce a floor: *Must be at least N (sum of non-unlimited pass types)*.

### Saving

**Save Configuration** submits; **Reset to Saved** discards your on-screen changes and reloads.

Saving with an empty list is refused with *Please add at least one pass type.* Saving with destinations listed reports *Configuration saved successfully!* — but see below.

## Important notes

> [!CAUTION]
> **This page cannot save, and saving makes things worse.** The page and the server disagree about the name of the field that carries your destinations, so nothing you enter reaches the server. What the server receives is an empty configuration, which it accepts. Your previous settings are retired and the class falls back to the five built-in destinations. You are told *Configuration saved successfully!* and the page reloads empty. This is a known defect; leave the page alone until it is fixed.

> [!WARNING]
> **Students cannot pick a destination anyway.** The student **Choose Break Type** menu is empty for the same reason, so *Done for the day* is currently the only option that works there. Configuring destinations would not change that today. See [Hall Pass Troubleshooting](../../../diagnostics/teacher/hall-pass.md).

> [!NOTE]
> **Simultaneous Limit is not enforced separately.** Where limits are applied, the app uses the destination's queue limit for both purposes. A distinct cap on students out at once is not currently checked.

> [!NOTE]
> **Total Limits are display-only.** They are calculated and shown for your reference. The app does not enforce a cross-destination cap.

> [!TIP]
> Approvals are the control that actually works. The five built-in destinations plus your judgement at the [Hall Pass](hall-pass.md) queue is the whole of hall-pass management right now — nothing is silently letting students out.

## Related guides

- [Hall Pass](hall-pass.md)
- [Hall Pass Troubleshooting](../../../diagnostics/teacher/hall-pass.md)
- [Hall Passes (Student)](../../student/work/hall-passes.md)
