# Accessibility and Usability Review — 2026-09-03

This review is governed by `INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md` and reported according to `SOP-TEST-002_Accessibility_Validation_And_PR_Gate.md`.

## Accessibility Scope

The review covers shared admin, student, and system-administration shells; public GitHub Pages; teacher and student feature templates; template-driven JavaScript feedback; icon-font loading; keyboard-reachable controls; and generated controls in roster, timeline, history, and store workflows. Feature-page interpretation was checked against the applicable canonical `FEAT-*` contracts before remediation.

## Validation Commands

```text
pytest -q tests/test_layout_accessibility_contract.py tests/test_accessibility.py tests/test_axe_compliance.py -> 39 passed, 2 skipped
ACCESSIBILITY_TEMPLATE_PATHS="$(find templates github-pages -type f -name '*.html' | sort)" pytest -q tests/test_accessibility.py -> 37 passed, 68 skipped
git diff --check -> passed
```

An unauthenticated runtime smoke pass reached the public, login, recovery, offline, health, and documentation entry routes on the local development server. All expected pages returned `200`; `/` redirected to `/gh/landing.html` and `/recovery/` redirected to `/recovery/lookup` as designed.

A second pass exercised 102 registered non-parameterized GET routes. A third pass expanded this to 120 safe parameterized GET route patterns using placeholder values. Neither pass found an unexpected 5xx response among user-facing routes; the two 500 responses were the explicitly diagnostic `/debug/admin-db-test` and `/health/deep` endpoints, whose bodies identify internal database diagnostics rather than rendering a user workflow. Authenticated state-changing journeys still require role-specific browser coverage.

`tests/test_axe_compliance.py` now contains a real axe-core audit for all public pages, but it is currently skipped because the Python Playwright package is unavailable in this environment. The skip is explicit and is not treated as WCAG conformance evidence.

The local teacher dashboard was also rendered in a real browser session. Its accessibility tree exposed the skip link, page heading, class context, quick actions, tables, and status content. A nonfunctional `href="#"` information link was found and replaced with a descriptive, noninteractive tooltip; the refreshed tree no longer exposes the misleading link.

The authenticated Student Management page was rendered as well. Before remediation, decorative icon names were announced alongside headings and controls. After the shared-layout fix, the accessibility tree exposes the user-facing labels without icon-name noise, including `Student Management`, `Class Roster`, `Copy`, and named student actions.

Sortable tables now expose keyboard-focusable headers, descriptive sort labels, and `aria-sort` state updates for keyboard and assistive-technology users.

Unauthenticated login and account-recovery surfaces now explicitly hide decorative authentication/status icons from the accessibility tree while retaining their visible cues and surrounding text.

Standalone error pages now hide decorative icons, and the offline page now provides skip navigation to a named `main` landmark so users who are already blocked can orient and recover more easily.

The teacher dashboard contained a nonstandard, unclosed `<subtitle>` element around metric help content. It has been replaced with standard inline HTML so the metric structure remains predictable to browser and assistive-technology parsers.

The student Savings Projection chart now has a screen-reader-readable table of the same month and balance values. The visual canvas remains available for sighted users, while the equivalent data is available without relying on chart interaction or color.

Shared passkey feedback now uses the accessible toast path for validation and operation errors. If Bootstrap is unavailable, `AppCore.toast` creates and focuses an assertive in-page live region instead of falling back to a blocking browser alert.

The shared runtime now observes post-render DOM mutations and hides newly inserted decorative Material Symbols as well, covering dynamic attendance, hall-pass, loading, and action-state content.

All template form controls in the source-level inventory now have an associated label or ARIA name; the check excludes only shared fragments that are not standalone pages.

Student issue-form character counters now announce their updated values politely, so users composing a report can track the 1000-character limit without relying on visual changes.

The source inventory now has a regression guard preventing blocking `alert()` calls from returning to templates or client scripts. Explicit `confirm()` safeguards for irreversible actions remain permitted and unchanged.

The complete template inventory now reports no unscoped table-header cells and no new-tab links without an accessible context-change disclosure. The public-page inventory also remains clear.

The authenticated Attendance page was rendered in the browser. Its generated pagination initially exposed icon-only `href="#"` links; these are now named keyboard buttons with disabled state for unavailable pages and `aria-current="page"` for the active page. The refreshed accessibility tree exposes `Previous page`, `Page 1`, and `Next page`.

The authenticated Payroll page and its Settings tab were rendered as well. The accessibility tree exposed the page heading, four tabs with selected state, labeled settings inputs, the Advanced Mode switch, and the Save Settings action.

The same fake-navigation pattern was found in Hall Pass history pagination and in Payroll's “Save Template” actions. Hall Pass history now uses named pagination buttons with disabled/current state, and Payroll uses typed action buttons instead of links that point to `#`.

The platform's single-session invariant was validated during the authenticated browser review: signing in through the verification session invalidated the previously active teacher session. This confirms that only one active teacher session is allowed for the account in the tested development environment.

The Student Store now keeps successful purchase/use announcements in a page-level live status region before closing the confirmation modal. Purchase request failures also receive focused in-page feedback.

Hall Pass Setup now names dynamically generated pass-type toggles and limit inputs, exposes configuration feedback as a focused live region, and gives the Add Pass Type modal an explicit accessible name.

Progress indicators in Store and account-recovery surfaces now expose descriptive accessible names, preserving the meaning of visual completion state for non-visual users.

Shared mobile navigation now uses the same 992px breakpoint as the shell CSS and marks a closed sidebar `inert`, preventing hidden navigation links from becoming sequential keyboard stops. Authentication and recovery fields also expose username, one-time-code, current-password, and new-password autocomplete purposes where applicable.

The standalone Hall Pass Verification surface now has a labelled `main` landmark and hides its decorative badge and restart icons from the accessibility tree, keeping verification content and controls understandable without the shared application shell.

The standalone-document inventory now reports a `main` landmark on every full HTML document in `templates`, including authentication, onboarding, recovery, error, maintenance, and hall-pass configuration pages.

The complete HTML inventory now gives every template and public-page button an explicit `type`, preventing navigation, modal, and disabled-state controls from accidentally submitting an enclosing form. The inventory reports no remaining button without a type attribute.

## Issues Found

- Public pages loaded an external Material Symbols stylesheet and could display literal icon names when the font did not load.
- Several shared or feature-specific controls lacked a meaningful accessible name or state relationship.
- Student Management used action links with `href="#"` for bulk operations and relied heavily on blocking browser alerts.
- Student class switching, PIN setup, passkey operations, clipboard operations, and several teacher workflows provided errors through alerts or no focused status region.
- Documentation timeline cards were mouse-clickable but did not consistently expose keyboard disclosure semantics.

## Fixes Applied

- Added local icon-font loading and ligature configuration for public pages.
- Added landmark names, `aria-current`, `aria-controls`, `aria-expanded`, labels, unique IDs, modal labels, and live status regions across affected surfaces.
- Replaced interruptive alerts with focused in-page status or toast feedback where the action is not a destructive confirmation.
- Retained explicit confirmation and timed safety gates for irreversible deletion actions.
- Converted Student Management bulk-operation links to typed buttons.
- Added keyboard behavior and state synchronization for timeline disclosures.
- Added explicit table column scopes across teacher, student, and system-admin record views.
- Added consistent new-tab disclosures to public resource links and operational escape routes.
- Preserved Store purchase/use feedback after modal dismissal with a page-level live status region.
- Added accessible names to visual progress indicators and a regression guard for modal title relationships.
- Added explicit button types across shared navigation and student/public interactive controls to prevent unintended form submission.
- Aligned responsive sidebar behavior with the shell breakpoint and added `inert` state synchronization for closed navigation.
- Added regression coverage for shared navigation, controlled dropdowns, timeline behavior, public font loading, bulk-action semantics, explicit button types, new-tab disclosures, and standalone-document landmarks.

## Remaining Issues / Risk

Status: **pass with follow-up risk** for the remediated source scope; the entire application review is not yet complete.

- Authenticated browser journeys for teacher and student roles still require route-by-route rendered verification.
- The axe test remains a placeholder and should be replaced or supplemented with real rendered axe coverage.
- Focus order, contrast, zoom/reflow, reduced motion, and dynamic error recovery need explicit browser verification on the remaining feature pages.
- Some generated pagination and dynamic-row controls remain candidates for deeper interaction testing even where static naming checks pass.

## CHANGELOG Updated

Yes. Accessibility fixes and user-facing feedback changes are recorded under `Unreleased` in `CHANGELOG.md`.
