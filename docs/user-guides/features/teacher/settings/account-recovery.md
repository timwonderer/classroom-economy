---
title: Account Recovery
category: features
subcategory: teacher-settings
roles: [teacher]
description: How student-assisted teacher account recovery works, and how to run it if you lose access.
keywords: [account recovery, teacher recovery, recovery codes, resume pin, lost access, totp reset]
related:
  - user-guides/diagnostics/teacher/login
  - user-guides/features/teacher/settings/passkey
---

# Account Recovery

## Overview

Classroom Token Hub does not store your email address, phone number, or date of birth. That means there is no reset link to send you. Instead, your students vouch for you.

If you lose access, you name one student from each class you teach. Those students log in, confirm their own passphrase, and each receives a **6-digit recovery code**. You collect the codes from them in person and enter all of them together to reset your credentials.

There is nothing to configure in advance. Recovery is active on your account by default.

## Step-by-step instructions

### The "Setup Account Recovery" banner

If your dashboard shows an **Action Required: Setup Account Recovery** banner, select **Setup Now**. The page explains that recovery runs on your class context and the student verification workflow, and that no extra personal information is needed. Select **Confirm & Return to Dashboard** to dismiss it.

Nothing is collected. The banner is an acknowledgement, not a form.

### Recovering your account

You do this from the login page, not from inside the app.

1. Go to the teacher login page and choose **Account Recovery**.
2. For each class you teach, enter a **Join Code** and one **Student Username** from that class. Use **+ Add another class** to add rows.
3. Select **Verify Identity**.

Every pair must be correct. The students you named are then notified in the app.

### Watching the verification progress

You land on the **Account Recovery Status** page. It shows:

- an expiry date and time for the request
- a progress bar reading **[n] / [total] Verified**
- one row per student, marked **Verified** with a timestamp or **Pending** with the time they were notified

The page does not push updates. Select **Refresh Status** to check again.

When every student has verified, the page shows **All Students Verified!** and a **Proceed to Reset Credentials** button.

### What your students do

A student you named sees a **Verify Teacher Recovery** prompt. They enter their own passphrase, and the app shows them a unique 6-digit code once. They must write it down and hand it to you in person.

See [Verify a Teacher Recovery Request](../../student/account/verify-teacher-recovery.md) for the student's view.

### Entering the codes

Collect every code, then enter them all on the reset page along with your new username. Order does not matter.

### Saving your progress

If you have some codes but not all of them, you can save what you have. The app gives you a **Resume PIN** — a 6-digit number shown **once**. Write it down immediately.

To come back later: go to the teacher login page, choose **Resume Recovery**, and enter the PIN. You pick up with the codes you already saved.

## Important notes

> [!WARNING]
> **One wrong code invalidates all of them.** If a code is mistyped, malformed, or you enter the wrong number of codes, every code in the request is destroyed and all of your students must verify again from scratch. Check each code carefully before submitting.

> [!IMPORTANT]
> **Codes must be handed over in person.** The whole point of the design is that someone who has stolen your password cannot also stand in your classroom. Do not ask students to text, email, or message you a code.

> [!IMPORTANT]
> **Recovery requests expire.** Both the request and the Resume PIN carry an expiry date shown on screen. Past that point you start over.

> [!NOTE]
> **You need one student per class you teach.** If a class has no students who can log in, you cannot complete recovery for that class. Make sure each active class has at least one student with working credentials.

> [!TIP]
> The most reliable time to run recovery is during class, when the students you named are in the room and can verify on the spot.

## Related guides

- [Verify a Teacher Recovery Request (Student)](../../student/account/verify-teacher-recovery.md)
- [Passkey and Login Security](passkey.md)
- [Login and Account Security Troubleshooting](../../../diagnostics/teacher/login.md)
