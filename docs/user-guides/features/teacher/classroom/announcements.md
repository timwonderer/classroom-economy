---
title: Announcements
category: features
subcategory: teacher-classroom
roles: [teacher]
description: Post a class announcement, pick its priority, set an expiry, and control visibility with Activate, Deactivate, Edit, and Delete.
keywords: [announcements, class announcements, priority, urgent, expiration, activate, deactivate, inactive, expired, dashboard message]
related:
  - user-guides/features/teacher/classroom/student-issues
  - user-guides/diagnostics/teacher/announcements-issues
---

# Announcements

## Overview

**Classroom > Announcements** opens **Class Announcements** — messages that appear at the top of the student dashboard for one class.

An announcement is visible to a student only when all three of these are true: it belongs to their class, it is **active**, and it has not expired. Every control on this page is one of those three levers.

## Step-by-step instructions

### Writing one

1. Choose **New Announcement**.
2. Check the class. The page tells you where it will land: *This announcement will post to the class currently selected in the sidebar: {class}.* There is no class picker on the form.
3. Fill in **Announcement Title**. The placeholder suggests the register: *e.g., Store Update, Important Reminder, Class Celebration*.
4. Fill in **Message**. *Students will see this message on their dashboard.* Line breaks are preserved.
5. Pick a **Priority**. Four choices, and the form is explicit that *Priority determines the visual style* — it changes colour and icon, nothing else.

   | Priority | Label |
   | --- | --- |
   | Low | *Low - General Information* |
   | Normal | *Normal - Standard Announcement* |
   | High | *High - Important Notice* |
   | Urgent | *Urgent - Critical Alert* |

6. Optionally set an **Expiration Date (optional)**. *Leave blank for no expiration. Expired announcements will be hidden automatically.*
7. Leave **Display to Students** ticked, or clear it to save without publishing. *Inactive announcements are hidden from students.*
8. Choose **Save Announcement**.

### Managing what is live

The list shows one card per announcement, newest first, colour-coded by priority. Above it, an **Active Class** banner reminds you which class you are looking at.

Badges tell you the state at a glance: an **Inactive** badge when it is hidden, an **Expired** badge when its date has passed. A live announcement gets a coloured bar down its left edge.

Each card carries three controls:

| Control | What it does |
| --- | --- |
| **Deactivate** / **Activate** | Hides or shows it to students. Toggles in place — the card updates without a page reload. |
| **Edit** | Reopens the form. Editing shows a **Preview** card underneath so you can see how it will read. |
| **Delete** | Removes it permanently, after a confirmation. |

Beneath the message body, each card shows *Created:* with the date and time, and *Expires:* when a date is set.

With nothing posted the page reads *No announcements yet. Create your first announcement to communicate with students in the active class.*

## Important notes

> [!IMPORTANT]
> **Announcements post to one class, and you cannot move them.** The class is fixed when you create it. To reach a second class period, switch class in the sidebar and write it again — the edit form says so directly: *To post to a different class, switch class in the sidebar and create a new announcement.*

> [!WARNING]
> **Delete cannot be undone.** The confirmation asks *Are you sure you want to delete the announcement "{title}"? This action cannot be undone.* If you only want it off students' screens, use **Deactivate** — it stays in your list.

> [!NOTE]
> **Students can dismiss an announcement, and their dismissal is per-device.** Closing it on a classroom computer does not close it on a phone. If a student says an old announcement "came back," that is why — and a student dismissing one does not remove it for anyone else.

> [!TIP]
> **Save Urgent for things that are actually urgent.** Priority only changes the colour, so its whole value is the contrast. A class where everything is red is a class where nothing is.

## Related guides

- [Student Issues Queue](student-issues.md)
- [Announcements and Issues Troubleshooting](../../../diagnostics/teacher/announcements-issues.md)
