---
title: Submit an Insurance Claim
category: features
subcategory: student-bills
roles: [student]
description: File a claim against coverage you hold, for either a purchase you lost money on or work time you lost, and read the refusal messages.
keywords: [insurance, claim, file a claim, payout, transaction, productivity, hours, allowance, reimbursement, rejected]
related:
  - user-guides/features/student/bills/insurance-coverage
  - user-guides/features/student/work/start-end-work
  - user-guides/diagnostics/student/rent-insurance
---

# Submit an Insurance Claim

## Overview

A claim is how you ask for the money your policy promised. You file it, your teacher reviews it, and if they approve it the payout lands in checking.

Which form you get depends on the policy's type, and the two are quite different:

- **Transaction** policies claim against a **purchase you already made**.
- **Productivity** policies claim against **work time you lost**.

## Step-by-step instructions

### Getting to the form

Open **Bills → Insurance**, find the policy under **Your coverage**, and press **File a claim**. You can only claim against coverage you currently hold — if you cancelled it and the period has ended, the button is gone and going to the page directly says *You don't hold active coverage for that policy.*

The top of the form restates the policy's terms so you can check them before filing: what percentage it reimburses, the *up to N× premium* period ceiling, and how many days you have to file.

### Claiming against a purchase (Transaction policies)

1. Open the **Transaction being claimed** dropdown and pick the purchase. Entries read like *Nov 03 · $4.50 · Pencil*.
2. Under **What happened**, describe it. Up to 1000 characters.
3. Press **Submit claim**.

The dropdown only offers your recent **money-out** transactions, and it deliberately leaves out things insurance is not for: transfers between your own accounts, rent and other bills, and insurance premiums themselves. If the purchase you want is not listed, it is not claimable.

### Claiming lost work time (Productivity policies)

The form shows a row of three fields under **Days you're claiming**:

| Field | What goes in it |
| --- | --- |
| **Date** | The day you lost. It will not accept a future date. |
| **Hours** | How much time you lost, in quarter-hour steps. |
| **What happened** | Your account of the lost time. |

Press **+ Add another day** to claim several days in one submission — each gets its own row. **Anything else (optional)** at the bottom is context for the whole claim, not for one day.

Then press **Submit claim**.

### After you file

You get *Insurance claim submitted.* and land back on the insurance page, where the claim appears in **Your claims** as **Submitted**. When your teacher decides, the status becomes **Approved** (with the amount) or **Rejected**. The claim form for that policy also keeps its own **Your claims on this policy** table.

Approved payouts go to **checking**.

### If your claim is refused

The app refuses some claims before your teacher ever sees them. The message tells you which rule you hit:

| Message | What it means |
| --- | --- |
| *Source transaction predates the purchased coverage* | The purchase happened before you bought the policy. Insurance never covers backwards. |
| *Filing window for this transaction has closed* | You waited too long. The window is on the policy card at the top of the form. |
| *Claim allowance exhausted (N/M for this period)* | You have used all your claims for this billing period. |
| *No remaining period payout capacity* | Approved payouts have already hit the *up to N× premium* ceiling for this period. |
| *Date {date} predates the purchased coverage* | Same rule as above, for a productivity date. |
| *Date {date} is in the future* | You can only claim days that have happened. |
| *Date allowance exhausted (N/M distinct dates for this period)* | You have claimed as many separate days as the policy allows this period. |
| *Claimed hours for {date} exceed the remaining daily capacity after time worked* | You are claiming more hours than that day had left after the time you actually clocked. |

## Important notes

> [!IMPORTANT]
> **Rejected claims still use up your allowance.** The per-period claim count includes every claim you filed — submitted, approved, *and rejected*. A claim your teacher turns down does not come back to you. Do not file speculatively to see what sticks.

> [!WARNING]
> **Insurance never covers anything from before you bought it.** Both claim types check the incident against your purchase timestamp and refuse anything earlier. Buying a policy after the thing goes wrong does not work.

> [!NOTE]
> **The two ceilings are separate.** The *claim allowance* limits how many times you can file in a period and counts rejections. The *payout capacity* limits how much money you can actually receive in a period and is only consumed by approved claims. You can run out of either one first.

> [!NOTE]
> **For lost-time claims, hours you actually worked reduce what you can claim.** If your class has a daily hours limit, the app subtracts the time you clocked that day from it, and only the remainder is claimable. A day you worked in full has nothing left to claim.

> [!TIP]
> Write the explanation as though your teacher were not in the room when it happened — because they may not have been. "Left my pencil on the bus" is reviewable. "You know what happened" is not.

## Related guides

- [Insurance Coverage](insurance-coverage.md)
- [Start and End Work](../work/start-end-work.md)
- [Troubleshooting Rent and Insurance](../../../diagnostics/student/rent-insurance.md)
