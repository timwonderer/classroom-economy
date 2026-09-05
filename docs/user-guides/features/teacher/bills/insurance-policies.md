---
title: Insurance Policies
category: features
subcategory: teacher-bills
roles: [teacher]
description: Build an insurance policy, choose its type, group it into tiers, and understand why editing one publishes a new version rather than changing the old.
keywords: [insurance, policies, premium, versioning, immutable, tier group, transaction, productivity, non-monetary, hide, retire]
related:
  - user-guides/features/teacher/bills/insurance-enrollment
  - user-guides/features/teacher/bills/insurance-claims
  - user-guides/diagnostics/teacher/rent-insurance
---

# Insurance Policies

## Overview

A policy is a contract template. Students buy from it; what they buy is frozen at the moment of purchase. That is why the app never lets you change a policy in place — **every save creates a new version with a new identity**, and the old one carries on unchanged for everyone already holding it.

**Bills > Insurance** lists what you have built. The list shows policies that are for sale and policies you have hidden; retired ones drop off it entirely.

## Step-by-step instructions

### Creating a policy

1. Choose **New policy** on **Bills > Insurance**. You build the whole contract in one pass — there is no draft state.
2. Give it a **Policy Title** and an optional **Description**. Students see both.
3. Choose an **Insurance Type**. This decides which of the remaining fields you are asked for.
4. Set the **Premium** and a **Charge Frequency** of **Weekly** or **Monthly**.
5. Fill in the type-specific fields (see below).
6. Optionally put the policy in a tier group.
7. Choose **Create policy**.

### Choosing a type

The type is the biggest decision on the form, because it changes both what the policy covers and what you are allowed to configure.

| Field | Transaction | Productivity | Non-monetary |
| --- | --- | --- | --- |
| Reimbursement % | ● | ● | — |
| Payout Multiple | ● | ● | — |
| Claims / week-equiv. | ● | — | ● |
| Claim Window (days) | ● | — | — |
| Claimable dates / week-equiv. | — | ● | — |
| Waiting Period (days) | — | — | ● |

Fields that do not apply are hidden as you switch types, and they are not submitted at all — so switching type on an existing policy discards the terms that belonged to the old type.

**Claim Window** is the deadline students face: how many days after an incident they may still file. **Claims / week-equiv.** and **Claimable dates / week-equiv.** are the usage caps.

### Tier groups

Turn on **Part of a tier group** to offer students a choice of plans rather than a single product.

- A group holds up to three plans: **Basic**, **Mid**, and **Premium**.
- A student may hold only one plan per group.
- Each rank can be filled once. The **Tier** dropdown greys out ranks a group has already taken.

Pick an existing group from the dropdown or choose **＋ New group…** and name it.

### Editing a policy

Selecting a policy from the list opens the same form, prefilled, with the button relabelled **Save as new version**. That label is literal:

- A **new policy** is written, with its own identifier and your edited terms.
- The **old policy is left exactly as it was** — including its state. It is not retired, not hidden, and not removed from the list.

For an ungrouped policy this means you end up with **two policies for sale**: the original and your revision, both purchasable, both shown to students. Hide or retire the old one yourself once the new version is saved.

For a **grouped** policy it means the edit is refused. The rank is still held by the original, so saving fails with *tier group '…' already has an active tier at level …; retire it before adding another at the same level*. See *Important notes* for the way around it.

### Withdrawing a policy

Each row carries **Hide** and **Retire**. Both stop new purchases and neither touches anyone's existing coverage. [Insurance Coverage and Enrollment](insurance-enrollment.md) covers what those states mean for policyholders.

## Important notes

> [!CAUTION]
> **Editing leaves the old version on sale.** Saving a new version does not withdraw the one you edited. Until you **Hide** or **Retire** the original, students see both and can buy either. Make withdrawing the old version the second half of every edit.

> [!WARNING]
> **A policy in a tier group cannot be edited.** The original still occupies its rank, so the new version is rejected. To change a grouped plan: **Retire** the original first, then create a fresh policy at that rank with the terms you want. Retiring is permanent, so be sure of the new terms before you start — and remember that retiring does not disturb anyone already covered.

> [!WARNING]
> **Hidden policies cannot be un-hidden.** There is no control that puts a policy back on sale, and editing a hidden policy produces another hidden policy. If you hide something you later want back, build it again as a new policy.

> [!CAUTION]
> **Waiting Period does not delay coverage.** The field saves, and the recommended values suggest a real waiting period — Basic plans are suggested at seven days. Nothing enforces it. A student can file a claim minutes after buying. Do not sell a non-monetary policy on the promise of a waiting period.

> [!IMPORTANT]
> **Terms are frozen at purchase.** A new version changes what *future* buyers get. Everyone holding the old version keeps the terms they bought until their coverage period ends. This is the lesson the feature exists to teach, and it is why there is no in-place edit.

> [!NOTE]
> **Values outside the recommended range are allowed.** The Economic Engine's suggestions are advisory. Only hard limits are enforced — premium at or above zero, reimbursement at or below 100%, no negative terms.

> [!TIP]
> Because a revision is a new product and the old one lingers, it is worth getting a policy right before you announce it. Build it, buy nothing, read it back on the list, and only then tell students it exists.

## Related guides

- [Insurance Coverage and Enrollment](insurance-enrollment.md)
- [Insurance Claims](insurance-claims.md)
- [Rent and Insurance Troubleshooting](../../../diagnostics/teacher/rent-insurance.md)
