---
title: Error Pages
category: diagnostics
subcategory: general
roles: [teacher, student]
description: What each error number means, whether it is your problem or ours, and what to do next.
keywords: [error, 400, 401, 403, 404, 500, 503, error id, bad request, forbidden, not found, server error]
related:
  - user-guides/features/public/maintenance-page
  - user-guides/features/public/offline-and-install
---

# Error Pages

## Overview

Occasionally a page is replaced by a large number and a short phrase. The number says what kind of problem it was — and, usefully, whether it is something you can fix.

Every one of these pages has a **Return to Login Page** button. When in doubt, take it: signing back in clears most of them.

## Step-by-step instructions

### Finding your number

| Number | It says | What it usually means | What to do |
| --- | --- | --- | --- |
| **400** | Bad Request | Something in the request was malformed — often a stale form or a mangled link | Go back, reload the page, and try once more |
| **401** | Authentication Required | You are not signed in, or your session ended | Sign in again. This page gives you **Student Login** and **Admin Login** buttons directly |
| **403** | Access Forbidden | You are signed in, but this is not yours to open | Check you are in the right class and the right account. If it should be yours, ask your teacher or support |
| **404** | Page Not Found | Nothing lives at that address — usually a mistyped or out-of-date link | Navigate from the menu rather than the link |
| **500** | Internal Server Error | The app broke. Not your fault | See below — copy the Error ID first |
| **503** | Service Unavailable | The app is up but temporarily cannot answer | Wait 5–10 minutes. The page refreshes itself |

### If you get a 500

This one is worth thirty seconds of your attention, because it is the only page that hands you something useful.

The page shows an **Error ID**. It is logged automatically, but the ID is what lets support find *your* failure among everyone else's.

1. Copy the Error ID, or photograph the screen.
2. Note what you were doing when it happened.
3. Include both when you report it — teachers through **Support**, students through **Report a Problem**.

### If you get a 503

The 503 page refreshes itself and points at the status page for live updates. If it is still there after ten minutes, check the status page directly.

A 503 that shows a badge and a timeline is not this page at all — that is planned work. See [Scheduled Maintenance](../features/public/maintenance-page.md).

## Important notes

> [!IMPORTANT]
> **400, 401, 403 and 404 are usually about where you are. 500 and 503 are about us.** The first four are worth retrying yourself; the last two are worth reporting.

> [!NOTE]
> **A 401 after leaving the app open is normal.** Sessions expire. It is not a sign that anything is wrong with your account.

> [!WARNING]
> **A repeating 403 is worth reporting rather than retrying.** If you keep being refused something that should be yours, say so — that is the kind of thing worth knowing about, and retrying will not fix it.

> [!TIP]
> Before reporting any error, note the address in the bar. Both the teacher and student report forms have a **Page URL** field, and it is the single most useful thing you can give.

## Related guides

- [Scheduled Maintenance](../features/public/maintenance-page.md)
- [Installing the App and Working Offline](../features/public/offline-and-install.md)
