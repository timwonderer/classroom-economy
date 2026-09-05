---
title: Student Management
category: features
subcategory: teacher-classroom
roles: [teacher]
description: Build a roster by pasting names, hand out the join code, edit or reset a student, and delete one when they leave.
keywords: [students, roster, add students, join code, unclaimed seats, reset login, delete student, bulk actions, export]
related:
  - user-guides/features/teacher/classroom/class-setup
  - user-guides/features/teacher/classroom/student-detail
  - user-guides/features/student/account/login-setup
---

# Student Management

## Overview

**Classroom > Students** is where a roster becomes a class. You put names in; students turn those names into accounts by claiming them with a join code.

The page has two tabs — **Class Roster**, which shows who you have, and **Add Students**, where you put new names in. A **Need Help?** button in the page header opens a short built-in guide.

## Step-by-step instructions

### Adding students

There is no file upload and no CSV template. You paste.

1. Open the **Add Students** tab.
2. Copy a block of names out of Excel or Google Sheets and paste it into the grid. Two columns (First Name, Last Name) or three (First Name, Last Name, Notes) both work. You can also type straight into the cells, and **Add Row** gives you another line.
3. The counter under the grid reads *n students staged*. **Clear All** empties it.
4. Select **Add Students**.

If two staged students share a name, a warning card highlights them. Duplicate names are allowed — each one becomes its own seat, and each gets its own claim code.

### Handing out the join code

The **Class Roster** tab shows the join code for the current class in large monospace type with a **Copy** button, alongside a badge reading either *n unclaimed seat(s)* or *All seats claimed*.

Beside it are the instructions to give students: go to the student sign-in page, choose **First Time? Set Up Account**, then enter the join code followed by the first and last name exactly as they appear on your roster.

### Unclaimed Seats

Every name you add starts here — a roster entry with no account behind it yet. The table lists the name, the date added, and a **Waiting for Claim** badge. The only action is a delete button, for names added by mistake.

The section disappears once everyone has claimed.

### Active Students

Once claimed, a student moves into **Active Students (n)**:

| Column | What it shows |
| --- | --- |
| Name | Links to that student's detail page |
| Checking | Turns red and bold when negative |
| Savings | Current savings balance |
| Hall Passes | Remaining pass count |
| Privileges | Badges for what they have access to — green means covered by rent, blue means individually purchased |
| Actions | Edit and Delete |

Tick the checkboxes in the first column and a toolbar appears reading *n students selected*, with a **Bulk Actions** menu: **Start Work**, **Break**, **Adjust Hall-Pass Entitlements**, and **Delete Students**. **Clear** drops the selection.

Before you have any claimed accounts the section is replaced by a note: *No students have claimed accounts in [your class] yet.*

### Editing a student

The **Edit** button opens **Edit Student**:

- **First Name** — used for the account claim process
- **Last Name** — stored as the student's encrypted full last name
- **Notes** — an optional teacher-facing note
- **Reset Student Login** — a switch that issues a one-time reset code, good for 10 minutes. Account data is preserved.

Then **Save Changes**.

The reset code is shown to you immediately. The student goes to the login page, selects **"I can't log into my account"**, and enters that code on its own — no name, no join code — then sets a new username, PIN, and passphrase. [Student Detail Page](student-detail.md) covers this in full.

There is no control here for moving a student to a different class. A student who changes periods claims a seat in the new class with that class's join code.

### Deleting a student

**Delete** opens a confirmation listing exactly what goes: all transaction history, all attendance records, all purchased items, all other student data. Type **DELETE** into the box, then **Delete Permanently**.

Deleting several at once is deliberately harder. **Bulk Actions > Delete Students** opens a gate with a 30-second countdown, then asks you to type **DELETE STUDENTS** by hand — pasting is blocked — and finally to press and hold a button for ten seconds.

### Exporting the roster

**Export All**, in the **Class Roster** header, downloads a CSV of the current class: First Name, Last Name, Block, Checking Balance, Savings Balance, Total Earnings, Insurance Plan, Rent Enabled, Has Completed Setup.

## Important notes

> [!CAUTION]
> **Deletion is permanent and takes the money with it.** There is no undo and no archive. If a student is only leaving temporarily, leave the account alone.

> [!IMPORTANT]
> **The name on the roster is the name they must type.** Claiming matches on first and last name. If a student cannot get past the claim screen, check the spelling on your roster first — and if you change it, tell them, because you have just changed what they need to enter.

> [!NOTE]
> **Reset Student Login is not deletion, and it is not a re-claim.** It replaces the student's credentials via a 10-minute code. Balances, transactions, and attendance survive, and the account stays claimed. Use it when a passphrase is lost.

> [!NOTE]
> **The roster is per-class.** Everything on this page belongs to the class selected in the sidebar. Adding a student here does not add them anywhere else.

> [!WARNING]
> **The exported Insurance Plan column always reads "None."** The export does not currently look up active policies. Every other column is accurate. This is a known defect.

> [!TIP]
> Paste your whole class in one go on day one, then hand out the join code and let students claim at their own pace. The unclaimed-seat badge tells you who is still outstanding without your having to chase anyone.

## Related guides

- [Class Setup and Join Codes](class-setup.md)
- [Student Detail Page](student-detail.md)
- [Log In and First-Time Setup (Student)](../../student/account/login-setup.md)
