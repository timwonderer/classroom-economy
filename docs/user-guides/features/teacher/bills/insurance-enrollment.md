---
title: Insurance Coverage and Enrollment
category: features
subcategory: teacher-bills
roles: [teacher]
description: How students take out coverage, why you cannot revoke it, and how to wind a policy down.
keywords: [insurance, enrollment, coverage, hide policy, retire policy, cancel coverage, contract]
related:
  - user-guides/features/teacher/bills/insurance-policies
  - user-guides/features/teacher/bills/insurance-claims
---

# Insurance Coverage and Enrollment

## Overview

You do not enroll students in insurance. Students buy it.

That distinction drives everything else on this page. A purchased policy is a contract between the student and the class, and the app treats it that way: you cannot cancel it, you cannot change its terms, and you cannot take it away. What you *can* do is stop selling it.

## Step-by-step instructions

### How students take out coverage

A student buys a policy from their own insurance page. At the moment of purchase the terms are frozen onto their contract — premium, charge frequency, claim time limit, and every cap.

Coverage starts at that moment. There is no delay, whatever **Waiting Period** you set on the policy — see *Important notes*. The only thing a claim is checked against is the purchase itself: an incident dated before the student bought the policy is rejected, and nothing else about timing is enforced.

### Withdrawing a policy from sale

On **Bills > Insurance**, each policy in **Existing Policies** shows its state and two controls.

| State | Meaning |
| --- | --- |
| For sale | Students can buy it |
| Hidden — winding down | No new purchases; existing holders keep their coverage |
| Retired | Permanently unavailable for new enrollment |

- **Hide** stops new purchases while leaving current policyholders untouched. Use this when you want to phase a product out.
- **Retire** does the same thing permanently. You are asked to confirm.

Neither one touches anybody's existing coverage. Both are about the shelf, not the contracts already sold.

### How coverage actually ends

Only the student can end their own coverage, and only by declining to renew it. When they cancel, the app tells them their benefits continue until the end of the current paid period, and the coverage expires at that boundary.

There is no early termination, no refund, and no way for you to revoke a policy someone is holding.

## Important notes

> [!IMPORTANT]
> **Purchased policies are enforceable contracts.** Editing a policy changes what *future* buyers get. Everyone already holding it keeps the terms they bought until their coverage period ends. This is deliberate — it is the lesson the feature exists to teach.

> [!CAUTION]
> **Waiting Period does not delay coverage.** The field saves and the suggested values imply a real wait, but nothing enforces it — a student can claim minutes after buying. See [Insurance Policies](insurance-policies.md).

> [!WARNING]
> **Editing does not withdraw the version you edited.** Saving a new version leaves the original for sale alongside it, so hiding or retiring the old one is a step you have to take yourself. [Insurance Policies](insurance-policies.md) covers this.

> [!IMPORTANT]
> **You cannot revoke a student's coverage.** Not for discipline, not for a policy change, not by hiding or retiring the product. If you need a consequence, use a different tool — insurance is not one of them.

> [!NOTE]
> **Hiding is reversible in effect, retiring is not.** A retired policy is permanently unavailable for new enrollment. If you are unsure, hide it.

> [!NOTE]
> **There is no roster of who is covered.** The Insurance Management page lists your policies, not your policyholders. To check one student's coverage, ask them to show you their insurance page. A teacher-facing enrollment list is a known gap.

> [!TIP]
> If a claims dispute turns on when coverage started, the answer is the purchase date. Not the waiting period, and not the terms currently shown in your settings — the student's own insurance page carries the contract they actually bought.

## Related guides

- [Insurance Policies](insurance-policies.md)
- [Insurance Claims](insurance-claims.md)
