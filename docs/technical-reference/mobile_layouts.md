# Mobile Layout Guidelines

This reference explains how the mobile templates stay consistent with the desktop experience and brand colors.

## Theme mapping

- **Admin** screens use the dark-green palette from the desktop shell (`#1a4d47` primary with `#2a5d57` hover). Primary badges, subtle backgrounds, and outline buttons inherit this palette so Bootstrap defaults do not introduce off-brand blues.
- **Student** screens use the dark-slate-blue palette (`#2F4F7F` primary, `#5B8DBE` info). Badge, background, and outline utility classes are aligned to these values so store and dashboard tiles keep the same tone as the desktop student shell.

## Layout principles

- Prefer card-first layouts with generous spacing for tap targets. Filters, history feeds, and confirmation dialogs should live inside cards with clear headers.
- Reuse the bottom navigation from `mobile/layout_admin.html` and `mobile/layout_student.html` to keep routing parity with desktop navigation items.
- When adding badges, prefer the primary or info theme utilities defined in the layout styles instead of raw Bootstrap defaults.

## Template selection

`render_template_with_fallback` automatically serves `templates/mobile/<template>.html` for mobile user agents. If a mobile template is missing, the desktop template is used, so new routes should ship with a mobile variant when the UX differs from desktop.

_Last Updated: 2025-12-12_
