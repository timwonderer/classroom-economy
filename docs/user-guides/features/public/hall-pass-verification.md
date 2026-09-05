---
title: Office Hall Pass Verification
category: features
subcategory: public
roles: [teacher]
description: Share a public link that lets office staff confirm a student's hall pass without giving them access to your class.
keywords: [hall pass, verification, office, front desk, public link, verify, regenerate, token, hallway, staff]
related:
  - user-guides/features/teacher/classroom/hall-pass
  - user-guides/features/teacher/classroom/hall-pass-setup
  - user-guides/features/student/work/hall-passes
---

# Office Hall Pass Verification

## Overview

A student stopped in the hallway says they have a pass. The adult who stopped them has no account in Classroom Token Hub and should not need one.

**Office Verification** is a public page for exactly that moment. It answers one question — *does this student have a hall pass right now* — and nothing else. Anyone holding the link can use it; no sign-in, no password.

## Step-by-step instructions

### Getting your link

1. In the teacher sidebar, open **Classroom** and select **Hall Pass**.
2. Look at the top right of the page.
   - If you see an **Office Verification** button, that is your link. Open it, copy the address, and give it to the people who need it.
   - If you only see **Regenerate QR**, you do not have a link yet. Select it once, confirm, and the **Office Verification** button appears.
3. Share the address with your front office, hallway staff, or whoever asks.

The link belongs to you, not to a class. One link covers every class you teach.

### What staff do with it

The page asks for three things:

1. **Class** — chosen from a dropdown of your classes.
2. **Student First Name**
3. **Student Last Name**

Then **Verify**. Names must match your roster; spelling is what makes or breaks the lookup. A **Verify Another** button resets the form for the next student.

### Reading the result

| What appears | What it means |
| --- | --- |
| A detail card with the student's name, class, destination, and status | A pass was found for today |
| **No hall pass record found for today.** *Please contact the teacher.* | Nothing today for that name in that class |
| **Unable to uniquely verify.** *Please contact the teacher.* | Two students in that class share the name — the page will not guess |

When there is a match, the **Status** line is one of:

| Status | Meaning |
| --- | --- |
| **Currently Out** *(N minutes)* | The student left and has not returned. The minute count is live |
| **Returned** | The student came back |
| **Approved (not yet out)** | You approved a pass, but the student has not left yet |

### Revoking a link

**Regenerate QR** issues a new link and kills the old one immediately. Use it if the address has been forwarded somewhere it should not have been, or shared with someone who no longer needs it.

You are asked to confirm first. Afterwards, everyone you gave the old link to needs the new one — there is no grace period.

## Important notes

> [!IMPORTANT]
> **Treat the link like a key.** There is no sign-in. Anyone who has the address can look up any student in any of your classes, indefinitely, until you regenerate it. Send it to specific people rather than posting it somewhere open.

> [!NOTE]
> **The page cannot leak your roster.** Staff have to already know the student's name — there is no list to browse, no search-as-you-type, and no way to page through students. It also shows only today: no history, no past passes, no balances, and nothing about the student beyond the pass in front of them.

> [!WARNING]
> **Times are shown in UTC, in raw computer format.** A time out reads like `2026-09-04T14:32:11Z`, which is neither your class's time zone nor a format most people can read at a glance. Tell staff to use the **Currently Out (N minutes)** count instead — that figure is correct and needs no conversion.

> [!CAUTION]
> **There is no QR code, despite the button.** The control is labelled *Regenerate QR* and its tooltip says *Regenerate Hall Pass QR*, but nothing in the app produces a QR image for this link. What you get is a web address. If you want a QR code for the office wall, generate one yourself from the address — and remember it stops working the moment you regenerate.

> [!TIP]
> The first press of **Regenerate QR** is what creates your link, not a replacement for one. If the **Office Verification** button is missing, that press is the fix.

> [!NOTE]
> A student's name has to match the roster exactly for the lookup to succeed. If staff report that a student "isn't in the system", check the roster spelling before assuming the pass is fake — see [Class Setup](../teacher/classroom/class-setup.md).

## Related guides

- [Hall Passes (Teacher)](../teacher/classroom/hall-pass.md)
- [Hall Pass Setup](../teacher/classroom/hall-pass-setup.md)
- [Hall Passes (Student)](../student/work/hall-passes.md)
