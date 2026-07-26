# SOP-TEST-002: Accessibility Validation and PR Gate

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-TEST-002     | 1.0     | 2026-06-13     | None       | Standard Operating Procedure |

## I. Purpose

This SOP defines how accessibility validation is executed, remediated, and reported for template and template-supporting UI changes.

## II. Dependencies

- `docs/INVARIANT/ARCHITECTURE/INV-ARC-017_GENERAL_TESTING_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
- `docs/TESTING/SOP-TEST-001_Validation_Execution_And_Reporting.md`

## III. Scope

This SOP applies whenever `INV-ARC-020` says a change is in scope for accessibility validation, including:

- route templates
- shared layouts, shells, and partials
- template-supporting CSS
- template-driven JavaScript interactions
- PRs that claim accessibility improvement, cleanup, or WCAG alignment

## IV. Required Validation Commands

For an in-scope template or UI change, run:

```bash
pytest -q tests/test_accessibility.py
venv/bin/pytest -q tests/test_axe_compliance.py
```

If a command is blocked, the PR must say so explicitly and explain why.

## V. Remediation Rules

When accessibility findings are discovered:

1. Fix the user-facing issue, not just the test symptom.
2. Prefer semantic HTML, valid labeling, and correct state announcement over ARIA-only patches.
3. Treat contrast, focus visibility, keyboard reachability, and name/role/value integrity as release-facing defects for in-scope surfaces.
4. If a finding is intentionally deferred, document it as remaining risk in the PR report.
5. If the change alters a shared shell, partial, or reusable styling primitive, validate the highest-blast-radius surfaces affected by that shared change.

## VI. Required PR Report Fields

Every in-scope PR must report:

1. Accessibility scope
2. Exact commands run
3. Result of each command
4. Accessibility issues found
5. Accessibility fixes applied
6. Remaining known accessibility issues, if any
7. Confirmation that `CHANGELOG.md` was updated with accessibility issues/fixes

## VII. Gate Condition

A PR that changes templates, shared layouts/components, template-supporting CSS, or template-driven interactive JavaScript is not merge-ready unless it contains the accessibility validation report required by this SOP.

Permitted outcomes:

- `pass`
- `pass with follow-up risk`
- `blocked`
- `not applicable`

`not applicable` is allowed only when the PR does not touch any surface covered by `INV-ARC-020`.

## VIII. Gate Failures

The gate fails when any of the following are true:

1. Missing accessibility report section
2. In-scope PR marked `not applicable`
3. Required commands omitted without explanation
4. Known issues found but not reported
5. PR text implies full accessibility validation when the run was partial
6. Accessibility issues or fixes were material to the PR but omitted from `CHANGELOG.md`

## IX. PR Report Shape

```text
Accessibility Scope: <scope or N/A>
pytest -q tests/test_accessibility.py -> <result>
venv/bin/pytest -q tests/test_axe_compliance.py -> <result>
Issues Found: <summary or None>
Fixes Applied: <summary or None>
Remaining Issues / Risk: <summary or None>
CHANGELOG Updated: Yes/No
```
