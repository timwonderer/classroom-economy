---
title: Installing the App and Working Offline
category: features
subcategory: public
roles: [teacher, student]
description: Install Classroom Token Hub to a phone or desktop, and understand why the app needs a live connection to do anything.
keywords: [install, PWA, app, home screen, offline, service worker, connection, You are offline, add to home screen]
related:
  - user-guides/features/public/maintenance-page
  - user-guides/diagnostics/error-pages
---

# Installing the App and Working Offline

## Overview

Classroom Token Hub runs in a browser, but it can be installed so it looks and launches like an app — its own icon, its own window, no address bar.

Installing changes how it *launches*. It does not let it work without internet. That distinction is the whole of this guide.

## Step-by-step instructions

### Installing it

There is no install button inside the app; installation is a browser feature.

| Device | How |
| --- | --- |
| iPhone / iPad | Open the site in Safari, tap **Share**, then **Add to Home Screen** |
| Android | Open the site in Chrome, tap the **⋮** menu, then **Install app** or **Add to Home screen** |
| Desktop Chrome or Edge | Look for an install icon at the right-hand end of the address bar, or use the **⋮** menu and **Install** |

The installed app is named **Token Hub**, opens at the sign-in page, and on a phone stays in portrait.

### What happens when the connection drops

You get a page reading **You are offline**, with a **Try Again** button. Select it once the connection is back.

That page is the whole offline experience. Balances, payroll, the store, attendance, hall passes — none of it is available without a connection, whether you installed the app or not.

## Important notes

> [!IMPORTANT]
> **Nothing you do is saved while offline.** There is no queue and no draft. If the connection drops mid-form, the work in that form is gone — reconnect and enter it again.

> [!WARNING]
> **Installing does not add offline access.** Every page that shows real data is fetched live, on purpose: cached class data could show one class's numbers to another. The installed app offline shows the same *You are offline* page the browser does.

> [!NOTE]
> **A blank or half-styled page usually means a flaky connection, not a broken app.** The app's own files can be cached even though its data cannot, so a weak signal can leave you with a page frame and no content. Reload once you have signal.

> [!TIP]
> If the app looks stuck on an old version after an update, close it completely and reopen it — or reload twice in a browser tab. That replaces the stored copy of the app's files.

> [!NOTE]
> Uninstalling is the same as removing any app: delete the icon from your home screen, or use your browser's app settings on desktop. Nothing in your account is affected.

## Related guides

- [Scheduled Maintenance](maintenance-page.md)
- [Error Pages](../../diagnostics/error-pages.md)
