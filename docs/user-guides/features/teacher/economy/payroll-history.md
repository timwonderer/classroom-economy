---
title: Payroll History
category: features
subcategory: teacher-economy
roles: [teacher]
description: Read the History tab on Economy > Payroll — payment types, reversals, and where the date-filtered Detailed Payroll History page lives.
keywords: [payroll history, history tab, reversal, payroll event, reward, fine, detailed payroll history, date filter]
related:
  - user-guides/features/teacher/economy/payroll-run
  - user-guides/features/teacher/economy/payroll-settings
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Payroll History

## Overview

**Economy > Payroll** has four tabs — **Overview**, **History**, **Settings**, and **Manual Payments**. This guide covers **History**: the record of every payroll event in the active class.

"Payroll event" is broader than payday. Rewards and fines land here too, which makes this tab the single place to answer "where did that money come from."

## Step-by-step instructions

### Reading the History tab

One row per event, newest first, with five columns: **Date**, **Type**, **Student**, **Amount**, and **Notes**.

**Type** is a colour-coded badge:

| Type | What it is |
| --- | --- |
| **Payroll** | A scheduled payroll run |
| **Reward** | Money you granted outside payroll |
| **Fine** | Money you deducted |

**Amount** is green for money in, red for money out. Student names link to that student's detail page, so a row is a starting point rather than a dead end.

An empty tab reads *No payroll records found.*

### Spotting a reversal

A reversed event does not disappear. Its row greys out and its amount picks up a **REVERSAL** badge, so the original payment and its undo both stay on the record.

### Filtering by date range

The History tab has no filters. For those, there is a separate page — **Detailed Payroll History** — with **From** and **To** date boxes and a **Filter** button. Its table drops the **Type** column and shows **Class** instead, which is useful when you want a plain date-bounded list.

Reach it at `/admin/payroll-history` (see the warning below).

## Important notes

> [!WARNING]
> **Detailed Payroll History has no link anywhere in the app.** No sidebar entry, no button on the Payroll page. The only way in is to type `/admin/payroll-history` after your site address. Everything it shows is scoped to the class selected in your sidebar, so switch class first if you want a different period.

> [!IMPORTANT]
> **History is per-class.** The tab shows the class currently selected in the sidebar and nothing else. A payment you remember making may simply belong to another period.

> [!NOTE]
> **Rewards and fines sit alongside payroll runs.** If a total looks wrong for a pay period, read the **Type** column before assuming the run miscalculated — a fine on the same day changes the number a student sees without changing what payroll paid.

> [!TIP]
> After every run, spot-check two or three students here against what the **Overview** tab predicted. It is a ten-second check that catches a bad pay rate before students do.

## Related guides

- [Run Payroll](payroll-run.md)
- [Payroll Settings](payroll-settings.md)
- [Attendance and Payroll Troubleshooting](../../../diagnostics/teacher/attendance-payroll.md)
