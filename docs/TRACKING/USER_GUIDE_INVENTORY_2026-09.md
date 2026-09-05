# User Guide Inventory — Phase 1

**Status:** Phase 1 complete
**Date:** 2026-09-04
**Scope:** User-facing help served by the in-app `/docs` site (`app/routes/docs.py`). Developer namespace docs (`INV-*`, `DOM-*`, `FEAT-*`, `ARC-*`, `SOP-*`) are out of scope — those ship separately via Docusaurus on GitHub Pages.

---

## What Phase 1 Did

Commit `da40d77d` moved the user guides to `docs/archive/v1-user-guides/` but left every consumer pointing at `user-guides/…`. The in-app docs site had been serving 404s for its entire user-facing section ever since.

Phase 1 restored the canonical location and repaired the reference graph:

| Change | Detail |
|--------|--------|
| Promoted guides out of archive | `docs/archive/v1-user-guides/` → `docs/user-guides/` (100 files) |
| Repaired docs-site nav | ~40 `doc_path` links in `templates/docs/index.html` now resolve |
| Repaired contextual help | `help_doc_map` in `layout_admin.html` (44 entries) and `layout_student.html` (12 entries) now resolve |
| Fixed never-valid deep links | `admin_payroll.html`, `admin_store.html` pointed at `features/payroll/running-payroll` and `features/store/creating-items`, which never existed |
| Fixed search audience filter | `app/routes/docs.py` keyed the `user` audience off the literal `v1-user-guides` path segment; now keys off the `user-guides` top-level directory |
| Fixed 25 frontmatter refs | Legacy flat naming (`diagnostics/student-money`) never updated when files were nested (`diagnostics/student/money`) |
| Fixed 1 orphan | Teacher bills index linked the *student* insurance-claims guide instead of its own |
| Removed dev-doc leak | `economy_guide.md` linked into the developer domain namespace, which SOP-DOC-000 §User-Facing Separation forbids |

**Post-move integrity:** 0 broken relative links, 0 broken `related:` refs, 100/100 pages reachable from a nav entry point.

---

## Corpus Summary

100 markdown files, ~3,900 lines.

| Section | Files | Audience |
|---------|-------|----------|
| Root guides | 5 | mixed |
| Diagnostics | 22 | student (8), teacher (11), index (3) |
| Feature guides — student | 24 | student |
| Feature guides — teacher | 39 | teacher |
| Feature guides — sysadmin | 5 | sysadmin |
| Legal | 5 | public |

### Metadata health

| Field | Missing |
|-------|---------|
| Frontmatter block | 1 (`README.md` — acceptable, it is a directory index) |
| `title` | 0 |
| `description` | 25 |
| `roles` | 8 |

`description` feeds search result context and `roles` feeds UI role-highlighting in `docs/view.html`. Both gaps degrade the experience rather than break it. Fold the fixes into the Phase 3 rewrite rather than doing a separate pass.

### Depth distribution

Most pages are 25–40 lines — a task-shaped page with Overview, Step-by-Step, and Related. Two outliers carry real analytical depth and are the most valuable content in the corpus:

- `diagnostics/teacher/rent-itemization.md` — 476 lines
- `diagnostics/teacher/analytics.md` — 384 lines

Neither is linked from the docs index nav; both are reachable only via `diagnostics/teacher.md`. Worth promoting in Phase 5.

---

## Full Inventory

#### Diagnostics — Index

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `diagnostics/index.md` | 14 | — | Diagnostics |
| `diagnostics/student.md` | 19 | student | Student Help and Support Guides |
| `diagnostics/teacher.md` | 28 | teacher | Teacher Help and Support Guides |

#### Diagnostics — Student

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `diagnostics/student/attendance.md` | 29 | student | Troubleshooting Attendance and Payroll |
| `diagnostics/student/classes.md` | 34 | student | Troubleshooting Classes and Join Codes |
| `diagnostics/student/hall-pass.md` | 29 | student | Troubleshooting Hall Passes |
| `diagnostics/student/login.md` | 32 | student | Troubleshooting Login and Setup |
| `diagnostics/student/money.md` | 35 | student | Troubleshooting Balances, Transfers, and Interest |
| `diagnostics/student/rent-insurance.md` | 42 | student | Troubleshooting Rent and Insurance |
| `diagnostics/student/store.md` | 36 | student | Troubleshooting Store and Purchases |
| `diagnostics/student/support.md` | 26 | student | Troubleshooting Help and Issue Reports |

#### Diagnostics — Teacher

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `diagnostics/teacher/analytics.md` | 384 | teacher | Analytics Dashboard Troubleshooting |
| `diagnostics/teacher/announcements-issues.md` | 56 | teacher | Announcements and Issues Troubleshooting |
| `diagnostics/teacher/attendance-payroll.md` | 56 | teacher | Attendance and Payroll Troubleshooting |
| `diagnostics/teacher/hall-pass.md` | 52 | teacher | Hall Pass Troubleshooting |
| `diagnostics/teacher/login.md` | 52 | teacher | Login and Account Security Troubleshooting |
| `diagnostics/teacher/onboarding.md` | 43 | teacher | Onboarding and Feature Settings Troubleshooting |
| `diagnostics/teacher/rent-insurance.md` | 71 | teacher | Rent and Insurance Troubleshooting |
| `diagnostics/teacher/rent-itemization.md` | 476 | teacher | Rent Itemization Troubleshooting |
| `diagnostics/teacher/store.md` | 52 | teacher | Store and Redemptions Troubleshooting |
| `diagnostics/teacher/students.md` | 55 | teacher | Students and Join Codes Troubleshooting |
| `diagnostics/teacher/transactions-banking.md` | 52 | teacher | Transactions and Banking Troubleshooting |

#### Features — index

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/index.md` | 19 | — | Feature Guides |

#### Features — student

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/student/index.md` | 33 | student | Student Feature Guides |

#### Features — student / account

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/student/account/dashboard-overview.md` | 32 | student | Student Dashboard Overview |
| `features/student/account/index.md` | 23 | student | Account Features (Student) |
| `features/student/account/join-class.md` | 37 | student | Join or Add a Class |
| `features/student/account/login-setup.md` | 36 | student | Log In and First-Time Setup |
| `features/student/account/reset-recovery.md` | 32 | student | Reset or Recover Your Account |
| `features/student/account/switch-class.md` | 36 | student | Switch Classes |

#### Features — student / banking

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/student/banking/accounts-transfers.md` | 35 | student | Accounts and Transfers |
| `features/student/banking/index.md` | 16 | student | Banking Features (Student) |
| `features/student/banking/savings-interest.md` | 29 | student | Savings Interest |

#### Features — student / bills

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/student/bills/index.md` | 19 | student | Bills Features (Student) |
| `features/student/bills/insurance-claims.md` | 31 | student | Submit an Insurance Claim |
| `features/student/bills/insurance-coverage.md` | 29 | student | Insurance Coverage and Claims |
| `features/student/bills/rent-payments.md` | 32 | student | Pay Rent |

#### Features — student / store

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/student/store/browse-buy.md` | 35 | student | Browse and Buy Items |
| `features/student/store/index.md` | 16 | student | Store Features (Student) |
| `features/student/store/redemption-status.md` | 31 | student | Track Redemptions |

#### Features — student / support

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/student/support/help-center.md` | 29 | student | Help Center Basics |
| `features/student/support/index.md` | 18 | student | Support Features (Student) |
| `features/student/support/report-issues.md` | 49 | student | Report Issues |

#### Features — student / work

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/student/work/attendance-history.md` | 32 | student | Attendance History and Pay Status |
| `features/student/work/index.md` | 16 | student | Work and Pay Features (Student) |
| `features/student/work/start-end-work.md` | 32 | student | Start and End Work |

#### Features — sysadmin

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/sysadmin/dashboard-overview.md` | 37 | sysadmin | Dashboard and Logs |
| `features/sysadmin/index.md` | 24 | sysadmin | System Admin Feature Guides |
| `features/sysadmin/platform-communication.md` | 47 | sysadmin | Platform Communication and Support |
| `features/sysadmin/security-access.md` | 42 | sysadmin | Security and Access Management |
| `features/sysadmin/teacher-management.md` | 39 | sysadmin | Teacher and Class Management |

#### Features — teacher

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/teacher/index.md` | 27 | teacher | Teacher Feature Guides |

#### Features — teacher / bills

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/teacher/bills/index.md` | 23 | teacher | Bills Features (Teacher) |
| `features/teacher/bills/insurance-claims.md` | 32 | teacher | Insurance Claims and Coverage |
| `features/teacher/bills/insurance-enrollment.md` | 30 | teacher | Insurance Enrollment |
| `features/teacher/bills/insurance-policies.md` | 36 | teacher | Insurance Policies |
| `features/teacher/bills/rent-behaviors.md` | 33 | teacher | Customizing Rent Behaviors |
| `features/teacher/bills/rent-itemization.md` | 33 | teacher | Rent Itemization |
| `features/teacher/bills/rent-settings.md` | 32 | teacher | Rent Settings |
| `features/teacher/bills/rent-waivers.md` | 30 | teacher | Rent Waivers |

#### Features — teacher / classroom

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/teacher/classroom/announcements.md` | 34 | teacher | Announcements |
| `features/teacher/classroom/attendance-approvals.md` | 36 | teacher | Attendance and Approvals |
| `features/teacher/classroom/attendance-corrections.md` | 32 | teacher | Fix Attendance Errors |
| `features/teacher/classroom/class-setup.md` | 41 | teacher | Class Setup and Join Codes |
| `features/teacher/classroom/dashboard-overview.md` | 32 | teacher | Teacher Dashboard Overview |
| `features/teacher/classroom/hall-pass.md` | 36 | teacher | Hall Pass |
| `features/teacher/classroom/index.md` | 32 | teacher | Classroom Features (Teacher) |
| `features/teacher/classroom/student-issues.md` | 43 | teacher | Student Issues Queue |
| `features/teacher/classroom/students-overview.md` | 43 | teacher | Student Management Overview |

#### Features — teacher / economy

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/teacher/economy/analytics.md` | 27 | teacher | Analytics Dashboard |
| `features/teacher/economy/banking-interest.md` | 28 | teacher | Interest and Payouts |
| `features/teacher/economy/banking-overdraft.md` | 29 | teacher | Overdraft Rules |
| `features/teacher/economy/banking-settings.md` | 28 | teacher | Banking Settings |
| `features/teacher/economy/economy-health.md` | 32 | teacher | Economy Health |
| `features/teacher/economy/index.md` | 37 | teacher | Economy Features (Teacher) |
| `features/teacher/economy/payroll-adjustments.md` | 40 | teacher | Payroll Adjustments |
| `features/teacher/economy/payroll-history.md` | 26 | teacher | Payroll History |
| `features/teacher/economy/payroll-run.md` | 35 | teacher | Run Payroll |
| `features/teacher/economy/payroll-settings.md` | 33 | teacher | Payroll Settings |
| `features/teacher/economy/policy-mode-rebalancer.md` | 79 | teacher | Economy Policy and Rebalancing |
| `features/teacher/economy/store-items.md` | 41 | teacher | Store Items |
| `features/teacher/economy/store-pricing.md` | 33 | teacher | Store Pricing Strategy |
| `features/teacher/economy/store-redemptions.md` | 32 | teacher | Store Redemptions |
| `features/teacher/economy/transactions.md` | 31 | teacher | Transactions |

#### Features — teacher / settings

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `features/teacher/settings/account-deletion.md` | 32 | teacher | Account Deletion Requests |
| `features/teacher/settings/account-recovery.md` | 30 | teacher | Account Recovery |
| `features/teacher/settings/feature-toggles.md` | 34 | teacher | Feature Toggles |
| `features/teacher/settings/index.md` | 25 | teacher | Settings Features (Teacher) |
| `features/teacher/settings/passkey.md` | 29 | teacher | Passkey and Login Security |
| `features/teacher/settings/personalization.md` | 30 | teacher | Personalization |

#### Legal

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `legal/attribution.md` | 160 | — | Attribution & Project Philosophy |
| `legal/commercial.md` | 133 | — | Commercial Use Policy |
| `legal/index.md` | 12 | — | Legal |
| `legal/license.md` | 107 | — | License |
| `legal/third-party-notices.md` | 96 | — | Third-Party Notices |

#### Root guides

| Doc | Lines | Roles | Title |
|-----|-------|-------|-------|
| `README.md` | 30 | — | — |
| `economy_guide.md` | 177 | teacher | Classroom Economy Guide |
| `student_guide.md` | 31 | student | Student Guide |
| `sysadmin_manual.md` | 18 | sysadmin | System Admin Manual |
| `teacher_manual.md` | 35 | teacher | Teacher Manual |

---

## Carried Into Phase 2

1. **Content is v1-shaped.** Every page describes v1 UI, navigation, and terminology. Accuracy against the current v2 app is unverified — that verification is Phase 2's job.
2. **Coverage is unknown.** 100 guides exist; whether they cover the v2 app's actual feature and template surface is exactly the Phase 2 question.
3. **Two known-stale areas.** `features/teacher/economy/policy-mode-rebalancer.md` and the rent itemization guides describe mechanics that have moved under the FEAT layer since v1.
4. **Sysadmin coverage is thin.** 5 pages against a substantial sysadmin surface (`templates/system_admin_*.html`, `sysadmin_*.html`).

---

## Out of Scope

Developer namespace links in `templates/docs/index.html` remain broken and are intentionally left alone — they target `ARCHITECTURE/`, `FEATURES/`, and `STANDARD_OPERATING_PROCEDURES/` paths that moved during the v2 reorganization. Those belong to the Docusaurus/GitHub Pages developer site:

- `ARCHITECTURE/ARC-CORE-000_Architecture_Foundation`
- `ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference`
- `ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema`
- `FEATURES/ANALYTICS/FEAT-MET-001_Analytics_Specification`
- `STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide`
- `STANDARD_OPERATING_PROCEDURES/DOCUMENTATION/SOP-DOC-002_Documentation_Index`
