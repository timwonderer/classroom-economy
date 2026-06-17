## PR Mode (Required – Select Exactly ONE)

<!-- Select exactly ONE option below to indicate PR mode.
     CI enforcement is currently label-based (for example, the `audit` label), not checkbox-based.
     Ensure your PR labels are consistent with the option you select.
-->

- [ ] Standard PR (Feature / Bug / Refactor / Docs / Performance)
- [ ] Audit PR (Read-Only, Documentation-Only – No Source Changes Allowed)

---

<details>
<summary>STANDARD PR SECTION (Click to expand)</summary>

<!-- Complete this section ONLY if "Standard PR" is selected above. -->

## Schema Change Gate Classification (Required for schema changes)

<!-- Required if this PR modifies app/models.py, app/models/**, or migrations/versions/**.
     Select exactly ONE classification for schema-affecting changes. -->

- [ ] **EXPAND** – Additive, backward-compatible (no removals)
- [ ] **CONTRACT (CODE ONLY)** – Model attribute removal, DB schema unchanged
- [ ] **CONTRACT (DATABASE)** – Destructive migration only
- [ ] **NON-MODEL CHANGE** – Comments, TODOs, or docstrings only; no structural model changes

## Description

<!-- Provide a brief description of the changes in this PR -->

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Other (please describe):

## Testing

<!-- Describe the tests you ran and how to reproduce them -->

- [ ] Tested locally
- [ ] All existing tests pass
- [ ] Added new tests for new functionality

## Accessibility Validation

<!-- Required for any PR touching templates/, shared layouts/components, template-supporting CSS, or template-driven JS.
     See INV-ARC-020 and docs/TESTING/SOP-TEST-002_Accessibility_Validation_And_PR_Gate.md.
     If not applicable, explicitly mark the N/A option and leave a short reason. -->

- [ ] Not applicable: this PR does not touch template/UI scope covered by `INV-ARC-020`
- [ ] Applicable: this PR includes template/UI scope and the accessibility report below is complete

**Accessibility Scope**
<!-- e.g. route template, shared layout, component partial, template CSS, template JS -->

**Accessibility Commands**
<!-- Required when applicable -->
- `pytest -q tests/test_accessibility.py`:
- `venv/bin/pytest -q tests/test_axe_compliance.py`:

**Accessibility Issues Found**
<!-- List issue categories and short summaries, or write "None". -->

**Accessibility Fixes Applied**
<!-- Summarize what changed to resolve the issues. -->

**Remaining Accessibility Issues / Follow-up Risk**
<!-- Write "None" if fully addressed. -->

**Changelog Accessibility Entry**
- [ ] `CHANGELOG.md` includes the accessibility issues/fixes found in this PR

## Database Migration Checklist

<!-- Complete this section ONLY if this PR includes a database migration -->

**Does this PR include a database migration?** [ ] Yes / [ ] No

If **Yes**, confirm:

- [ ] Synced with `main` branch immediately before running `flask db migrate`
- [ ] Migration file reviewed and verified correct `down_revision`
- [ ] Tested `flask db upgrade` successfully
- [ ] Tested `flask db downgrade` successfully
- [ ] Confirmed only ONE migration head exists (pre-push hook should verify this)
- [ ] Migration has a descriptive message/filename
- [ ] Breaking changes or data migrations documented in PR description

**Migration file location:**
<!-- e.g., migrations/versions/abc123_add_user_email.py -->

## Checklist

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code where necessary, particularly in hard-to-understand areas
- [ ] I have updated the documentation accordingly
- [ ] If this PR touched template/UI scope, I completed the required accessibility validation report
- [ ] My changes generate no new warnings or errors
- [ ] I have read and followed the [contributing guidelines](../CONTRIBUTING.md)

## Related Issues

<!-- Link any related issues here -->

Closes #

## Additional Notes

<!-- Any additional information that reviewers should know -->

---

</details>

<details>
<summary>AUDIT PR SECTION (Click to expand)</summary>

<!-- Complete this section ONLY if "Audit PR" is selected above. -->

## Audit Stage (Select Exactly ONE)

- [ ] Stage 1 – Static Structural Audit
- [ ] Stage 2 – Economic Invariant Risk Audit
- [ ] Stage 3 – Security & Boundary Scan
- [ ] Stage 4 – Test Coverage & Fragility Audit
- [ ] Stage 5 – Refactor Proposal (Plan Only)

## Audit Artifacts

<!-- List all NEW or MODIFIED documentation artifacts created under docs/audits/ in this PR -->

- Primary report file:
  - docs/audits/...

- Additional artifacts (if any):
  - docs/audits/...

## Audit Confirmation

- [ ] I confirm that this PR modifies documentation only and includes no changes to source code, migrations, or database schema.

</details>
