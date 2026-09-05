---
title: Student Detail Page
category: features
subcategory: teacher-classroom
roles: [teacher]
description: Work one student's record — balances, transactions, items, attendance, payroll, hall passes — and hand out the codes they need to claim or recover their account.
keywords: [student detail, void transaction, hall pass adjustment, reset code, recovery, edit student, teacher notes, setup status, join code]
related:
  - user-guides/features/teacher/classroom/students-overview
  - user-guides/features/teacher/economy/transactions
  - user-guides/features/teacher/classroom/attendance-corrections
  - user-guides/diagnostics/teacher/students
---

# Student Detail Page

## Overview

Selecting a student from **Students** opens their detail page. Everything the app knows about that one student in this class is here, split across six tabs.

Two things on this page cannot be done anywhere else: **voiding a single transaction** and **adjusting a student's hall-pass balance by hand**.

## Step-by-step instructions

### Reading the header

Four cards run across the top:

| Card | What it shows |
| --- | --- |
| **Checking Balance** | Spendable balance. Turns red if negative |
| **Savings Balance** | Set-aside balance |
| **Total Earnings** | Everything this student has earned in this class |
| **Hall Passes** | Current pass balance |

If the student has anything covered by rent, an **Active Rent Privileges** panel sits under the cards. Green badges are items included in rent; blue badges are items they bought.

**Edit Student** is at the top right. **Back** returns you to the roster.

### Overview tab

**Student Information** lists Name, **Setup Status**, Insurance, and **Join Code(s)**.

**Setup Status** is the one to watch:

- **Complete** — the student has claimed the account and set their own credentials
- **Pending** — nobody has claimed it yet

Beside it, **Recent Attendance** shows the single most recent event: Last Activity, Status, Period, and a Reason when one was given. Before any activity it reads *No attendance records found.*

Two alert cards appear on this tab only when they apply.

**Account Recovery / Setup** (yellow) shows on any account still Pending. It gives you the student's **Name** and **Join Code(s)** to read out so they can claim.

**Account Recovery In Progress** (red) shows when you have issued a reset code. It displays the code in large monospace, the join code, and the exact time the code expires, with the instruction that the student goes to the login page and clicks **"I can't log into my account"**.

### Transactions tab

The tab label carries a count. The table shows **Date**, **Type**, **Account**, **Amount**, **Description**, **Status**, and **Actions**.

To reverse one entry:

1. Find the row.
2. Select **Void** in the **Actions** column.
3. Confirm at *Are you sure you want to void this transaction?*

The row is struck through and greyed, and the amount stops counting toward the balance. The entry stays visible — voiding is a correction on the record, not a deletion of it.

Already-voided rows and refunds have no **Void** button.

### Items tab

Everything the student owns, with a status badge: **Purchased**, **Processing**, **Redeemed**, **Expired**, **Revoked**, **Used**, or **Approved**. Redemption itself is handled in [Store Redemptions](../economy/store-redemptions.md).

### Attendance tab

The full attendance record for this student. The table caps at 50 rows and tells you when it has — *Showing most recent 50 records out of N total*. Corrections are made from the attendance screens, not here; see [Fix Attendance Errors](attendance-corrections.md).

### Payroll tab

Three counters — **Total Earnings**, **Payroll Deposits**, **Manual Credits** — over a **Recent Earnings** table of the last 20 entries with Date, Type, Amount, and Description.

### Settings tab

**Hall Pass Management**, showing the current balance and a form to change it:

1. Choose **Add Passes** or **Remove Passes**.
2. Enter a **Quantity** (minimum 1).
3. Select **Apply**.

Removing does not erase history. It records a reversal against passes the student has not used yet, so a pass already spent cannot be taken back.

### Editing the student

**Edit Student** opens a modal with:

- **First Name** — used during the account claim
- **Last Name** — stored encrypted
- **Teacher Notes** — for you; the student never sees them
- **Reset Student Login** — a switch

Turning the reset switch on and saving generates an 8-character reset code that expires in **10 minutes**. The code is flashed to you immediately and also appears in the red **Account Recovery In Progress** card on the Overview tab until it expires.

The student then goes to the login page, selects **"I can't log into my account"**, and enters that code. The code alone gets them in — they are not asked for their name or join code — and they go straight to choosing a new username, PIN, and passphrase.

## Important notes

> [!IMPORTANT]
> **A reset is not a re-claim.** Resetting does not delete the account or return it to Pending. The student's balances, items, and history are untouched; only their login credentials are replaced.

> [!WARNING]
> **Reset codes expire in 10 minutes.** Issue one when the student is in front of you and ready to use it. If it lapses, flip the switch again for a fresh code.

> [!CAUTION]
> **Voiding is per-transaction and immediate.** There is one confirmation dialog and no undo. If you meant to correct an amount rather than cancel the entry, void it and post a replacement so the record shows what happened.

> [!NOTE]
> **Insurance always reads None on this page.** The field is not wired to the current insurance records, so it shows *None* even for insured students. Check the student's own insurance page for the real status.

> [!NOTE]
> **Ignore the Date of Birth instruction.** The yellow setup card tells you the student must also enter their date of birth. The app never collects or stores one, and the claim form does not ask for it. Name plus join code is the whole of it.

## Related guides

- [Student Management](students-overview.md)
- [Transactions](../economy/transactions.md)
- [Fix Attendance Errors](attendance-corrections.md)
- [Students and Join Codes Troubleshooting](../../../diagnostics/teacher/students.md)
