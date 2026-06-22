# INV-ARC-020: Accessibility Requirements and Template Contract

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-020      | 1.0     | 2026-06-13     | None       | Constitutional |

## I. Purpose

This document defines the canonical accessibility requirements for user-facing templates, shared UI shells, template-driven JavaScript interactions, and template-supporting CSS in the `codex/v2.0` codebase.

It exists to ensure that template work is governed by explicit accessibility contracts rather than visual preference or one-off cleanup.

## II. Scope

This document applies to:

- Jinja templates under `templates/`
- shared layout templates
- template-driven components and partials
- CSS that affects rendered UI semantics, contrast, focus visibility, or interaction
- JavaScript that controls accordions, modals, tabs, menus, disclosures, toasts, and other interactive UI states
- documentation claims that state or imply accessibility conformance

## III. Authority Level

Constitutional. This document derives directly from `INV-CORE-000` Section III.7, `No Unnecessary Barriers to Supported Use`, and is governed within the `INV` hierarchy described by `INV-CORE-001`. It defines repository-wide accessibility requirements for template and UI work and is subordinate to those foundational invariants. It may be tightened by a stricter domain, spec, SOP, or gate document, but it must not be weakened by route-local convention.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-017_GENERAL_TESTING_INVARIANTS.md`
- `docs/TESTING/SOP-TEST-003_Test_Creation.md`
- `docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md`
- `docs/TRACKING/V2_REBUILD_VALIDATION_REPORT.md`

## V. Accessibility Principles

1. Accessibility is a runtime contract, not a cosmetic enhancement.
2. Every interactive element must expose a meaningful accessible name.
3. Visual hierarchy must map to semantic hierarchy.
4. Keyboard operation must be first-class, not incidental.
5. Template work must preserve or improve accessibility; regressions are not acceptable tradeoffs for layout changes.
6. Shared components and shells must be treated as high-blast-radius accessibility surfaces.

## VI. Required Baseline for Template Changes

Every template or template-supporting UI change must preserve the following:

1. Exactly one meaningful page `h1`.
2. Logical heading order with no unjustified level skips.
3. Labels or ARIA naming for all form controls.
4. Accessible names for links, buttons, disclosure toggles, icon-only controls, and modal dismiss buttons.
5. Unique IDs across the rendered page.
6. Sufficient color contrast for text, badges, buttons, tabs, alerts, nav items, and helper text.
7. Visible focus indication for keyboard users.
8. Valid ARIA usage only where the element role supports it.
9. State-bearing controls that correctly expose `aria-expanded`, `aria-controls`, `aria-selected`, or similar attributes when applicable.
10. No UI pattern that depends solely on color to communicate meaning.

## VII. Template and UI-Shell Requirements

The following rules are mandatory for any PR that touches templates or shared UI structure.

### A. Semantic Structure

- Use native headings where possible.
- Do not substitute visual size classes for document structure without preserving semantic heading levels.
- Do not create duplicate `id` values across repeated accordions, tabs, or cards.

### B. Interactive Controls

- Icon-only controls must have `aria-label` or equivalent naming.
- Collapse, tab, menu, and modal triggers must use supported ARIA attributes only.
- Interactive elements must not nest incompatible interactive descendants.

### C. Forms

- Inputs, selects, and textareas must have explicit labels or equivalent ARIA references.
- Placeholder text is not a substitute for labeling.

### D. Color and Contrast

- Text and icons that communicate meaning must meet WCAG 2.1 AA contrast requirements in their actual rendered state.
- Bootstrap utility classes may not be assumed to satisfy contrast once combined with project tokens or custom backgrounds.
- Muted, secondary, badge, and alert styling must be treated as high-risk accessibility surfaces.

### E. Keyboard and Focus

- Focusable controls must remain reachable and visibly focused.
- Hidden or collapsed content must not trap focus.
- Disclosure widgets must remain operable without pointer interaction.

## VIII. High-Risk Change Classes

The following changes automatically trigger accessibility validation requirements:

1. Any change under `templates/`.
2. Any change to shared layout templates.
3. Any change to shared template components.
4. Any change to `static/css/` affecting rendered colors, spacing, display states, or focus styles.
5. Any change to template-driven JS controlling stateful UI.
6. Any PR that changes the rendered output of tabs, accordions, alerts, nav, cards, dialogs, or forms.

## IX. Prohibited Patterns

The following are prohibited:

1. Adding ARIA attributes to elements whose roles do not support them.
2. Using color alone to distinguish links from surrounding text.
3. Downgrading heading semantics to non-heading elements for styling convenience without a justified accessibility reason.
4. Relying on Bootstrap defaults without verifying contrast in the project token system.
5. Shipping template changes without the required accessibility validation evidence when the change is in scope.

## X. Documentation and PR Obligations

When a PR touches a covered template/UI surface:

1. Accessibility validation results must be reported in the PR template.
2. Accessibility issues found and fixes made must be reported in `CHANGELOG.md`.
3. If accessibility issues remain intentionally unresolved, they must be explicitly listed as follow-up risk in the PR.

## XI. Amendment

Changes to this document must update the version and effective date, remain aligned with `INV-ARC-017` and `SOP-TEST-003`, and update any dependent SOP or PR-process document that references this accessibility contract.
