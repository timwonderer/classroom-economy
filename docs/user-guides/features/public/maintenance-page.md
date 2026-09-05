---
title: Scheduled Maintenance
category: features
subcategory: public
roles: [teacher, student]
description: What the maintenance page means, how to read its badge and timeline, and what to do while you wait.
keywords: [maintenance, scheduled maintenance, down, outage, status page, unavailable, 503, refresh]
related:
  - user-guides/features/public/offline-and-install
  - user-guides/diagnostics/error-pages
---

# Scheduled Maintenance

## Overview

If Classroom Token Hub is taken offline deliberately, every page is replaced by a single maintenance page. You cannot sign in or reach your class while it is showing — that is the point of it.

It affects everyone at once. Nothing is wrong with your account, your device, or your connection.

## Step-by-step instructions

### Reading the page

At the top is a badge naming the reason:

| Badge | Meaning |
| --- | --- |
| **Scheduled Maintenance** | Planned work, arranged in advance |
| **System Update** / **New Feature Deployment** | A new version is going out |
| **Bug Fix In Progress** | Something is being repaired |
| **Security Patch** | A security fix is being applied |
| **Server Unavailable** / **Unexpected Error** | Unplanned — the app is down and being looked at |

Beneath it, two tiles:

- **Planned timeline** — when the app is expected back, or *We currently do not have an estimated time of recovery* if that is not yet known. The page says plainly that the real time may be earlier or later.
- **Want to know the latest?** — a link to the status page, `status.classroomtokenhub.com`, which keeps working while the app does not.

### Waiting it out

The page refreshes itself every 60 seconds, counting down at the bottom right. **Refresh Page** does it immediately. Leave the tab open and it will let you back in on its own once the work finishes.

## Important notes

> [!IMPORTANT]
> **Nothing is lost.** Balances, transactions, rosters, and settings are untouched by maintenance. Work you had already saved is still saved. Anything you were typing when the page appeared is not.

> [!NOTE]
> **The status page is the place to check.** It is hosted separately and stays up during an outage, so it can tell you things the app cannot.

> [!NOTE]
> **The System Admin sign-in button is not for you.** *System Admin: Sign In For Bypass* is for the people running the platform to test during the outage. Teachers and students have no bypass — the wait is the wait.

> [!TIP]
> If classmates or colleagues can reach the app and you cannot, it is not maintenance. Check your connection first, then see [Error Pages](../../diagnostics/error-pages.md).

## Related guides

- [Installing the App and Working Offline](offline-and-install.md)
- [Error Pages](../../diagnostics/error-pages.md)
