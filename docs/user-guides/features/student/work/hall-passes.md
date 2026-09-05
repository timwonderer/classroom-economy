---
title: Hall Passes
category: features
subcategory: student-work
roles: [student]
description: Request a hall pass from your dashboard, wait for approval, and use the one button that becomes Pending, Leave, and Return.
keywords: [hall pass, break, leave, return, pending, passes left, destination, bathroom, check out, check in, done for the day]
related:
  - user-guides/features/student/work/start-end-work
  - user-guides/features/student/account/dashboard-overview
  - user-guides/diagnostics/student/hall-pass
---

# Hall Passes

## Overview

There is no Hall Pass page. The whole thing happens in the **Attendance** card on your dashboard, through a single button that changes its own label as your request moves along.

That button starts as **Break**. Once you ask for a pass it reads **Pending**, then **Leave**, then **Return** — same button, same place, four different jobs. Learning that sequence is most of learning the feature.

## Step-by-step instructions

### Before you can ask

Two things have to be true, and the app will tell you if either is missing:

- **You must be clocked in.** If you have not pressed **Start Work**, the **Break** button is greyed out. Asking through any other route returns *Start work before requesting a hall pass.*
- **You must have a pass to spend.** The badge in the top-right corner of the Attendance card reads **N Passes Left**. At zero, requests are refused with *No hall passes available.*

Passes are not free and they do not refill on their own. You get them by buying a **Hall Pass** item in the store, or as a perk attached to your rent — ask your teacher which applies in your class.

### Requesting a pass

1. Press **Break**. The **Choose Break Type** dialog opens: *Choose a hall-pass destination or mark yourself done for the day.*
2. Pick a destination from the list of buttons. Your teacher decides what is on that list.
3. The dialog closes and you see *Hall pass request sent.*

No PIN is required to request a pass.

### Waiting

A yellow banner appears above the buttons reading **Hall Pass: Pending Approval**, with the destination you chose and a **Cancel** button. The **Break** button becomes **Pending** and stops responding — pressing it just reminds you *Your hall pass request is pending approval.*

Your dashboard checks for an answer every ten seconds. You do not need to reload the page.

To withdraw the request, use **Cancel** on the banner and confirm *Are you sure you want to cancel this hall pass request?*

### Going and coming back

| The banner says | The button reads | What to do |
| --- | --- | --- |
| **Hall Pass: Pending Approval** | **Pending** | Wait, or **Cancel**. |
| **Hall Pass Approved!** | **Leave** | Press **Leave** when you actually go, and confirm *Ready to check out?* |
| **Currently Out** | **Return** | Press **Return** the moment you are back, and confirm *Ready to check in?* |
| **Hall Pass Denied** | **Break** | Your teacher declined. The banner shows their reason. |

Checking out greets you with *Checked out for {destination}. Have a safe trip!* Checking in replies *Welcome back! You have been checked in.* Once you are checked in the banner disappears and the button goes back to **Break**.

### Done for the day is not a hall pass

The same **Choose Break Type** dialog has a separate **Done for the day** button below a divider. It ends your day rather than requesting a pass, it costs no passes, and it asks for your PIN. See [Start and End Work](start-end-work.md).

## Important notes

> [!WARNING]
> **The destination list is currently broken.** **Choose Break Type** shows *No hall-pass destinations are currently available* no matter what your teacher has configured, which leaves **Done for the day** as the only working button in that dialog. This is a known app defect, not something you or your teacher can fix from the settings. Ask your teacher to let you out the usual way until it is repaired.

> [!IMPORTANT]
> **Your pass is spent when your teacher approves, not when you leave.** If you get approval and then change your mind, the pass is already gone. Cancelling *before* approval costs nothing.

> [!NOTE]
> **Your clock stops while you are out.** Pressing **Leave** marks you inactive and pressing **Return** marks you active again, so the time between them is not paid. Forgetting to press **Return** keeps you off the clock and quietly costs you money.

> [!NOTE]
> **You can only have one request waiting at a time.** Asking again while a request is pending replaces the first one rather than queuing a second.

> [!TIP]
> If your request is refused even though you have passes left, someone is probably already out. Your teacher sets how many people can be out at once, both per destination and for the class overall. Wait for them to come back and ask again.

## Related guides

- [Start and End Work](start-end-work.md)
- [Student Dashboard Overview](../account/dashboard-overview.md)
- [Troubleshooting Hall Passes](../../../diagnostics/student/hall-pass.md)
