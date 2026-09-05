---
title: Economy Features
category: features
subcategory: teacher-settings
roles: [teacher]
description: Turn Rent, Store, Insurance, and Hall Pass on or off for a class, and understand why some features stay locked.
keywords: [economy features, feature toggles, enable rent, enable store, enable insurance, hall pass, locked features]
related:
  - user-guides/features/teacher/economy/economic-engine
  - user-guides/features/teacher/economy/payroll-settings
  - user-guides/diagnostics/teacher/onboarding
---

# Economy Features

## Overview

**Economy Features** is where you decide how much of the app a class actually uses. A first-week class might only need payroll. By spring you might have rent, a store, and insurance running.

The page is scoped to one class. If you teach four periods, each one has its own set of switches.

Features fall into three groups, and the page shows them in that order.

## Step-by-step instructions

### Opening the page

1. In the teacher sidebar, open **Class Tools**.
2. Select **Economy Features**.

The heading confirms which class you are editing — **Feature Settings — [your class]**.

### The three groups

#### Core · always on

| Feature | What it does |
| --- | --- |
| Payroll | Time tracking and student payments |
| Banking | Savings accounts and interest |

These have no switch. Payroll defines the economy — there is no classroom economy without a way to earn — and banking is where earnings live. You cannot turn either off.

#### Features

| Feature | What it does |
| --- | --- |
| Hall Pass | Bathroom and water break passes |

Toggle freely. Hall Pass has no pricing tie, so it works whether or not your economy is set up.

#### Pricing features

| Feature | What it does |
| --- | --- |
| Rent | Housing costs and payments |
| Store | Marketplace for student rewards |
| Insurance | Insurance policies and claims |

All three charge students money, so all three price themselves against your Classroom Wage Index. Until the app can calculate a CWI, the whole group is greyed out.

### Unlocking the pricing features

When the group is locked you see: *In order to use these features, you must first set up payroll and configure your economic engine.* Two checkboxes below show which prerequisite is still outstanding:

| Prerequisite | How to satisfy it |
| --- | --- |
| Payroll | Set a pay rate in **Economy > Payroll > Settings** |
| Economic Engine | Set expected hours per week in **Economy > Economic Engine** |

Both must be ticked. Once they are, the three switches become live.

### Turning a feature on or off

Flip the switch. There is no save button — the page says **Changes are saved automatically** at the top and the bottom, and each change is written as you make it.

Turning a feature off hides it from your students immediately.

## Important notes

> [!IMPORTANT]
> **Check which class you are in.** These switches belong to the class selected in the sidebar. Turning Rent on here does not turn it on for your other periods.

> [!TIP]
> **Start small.** Payroll and Banking are already on. Add Store once students have earned a few paychecks and understand what their balance means. Add Rent when you want a recurring obligation. Add Insurance last — it only makes sense once there is something worth insuring against.

> [!NOTE]
> **Turning a feature off does not delete anything.** Existing balances, purchases, and history stay in place. Turn it back on and everything is where you left it.

> [!WARNING]
> **Turning off Rent does not cancel bills already issued.** Obligations that have already been assessed remain on students' accounts. Resolve outstanding bills before you switch the feature off.

## Related guides

- [Economic Engine](../economy/economic-engine.md)
- [Payroll Settings](../economy/payroll-settings.md)
- [Onboarding and Feature Settings Troubleshooting](../../../diagnostics/teacher/onboarding.md)
