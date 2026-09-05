# User Guide Coverage — Phase 2

**Status:** Phase 2 complete
**Date:** 2026-09-04
**Scope:** The v2 app's user-facing surface, measured against the 100 guides restored in Phase 1.
**Inputs:** `app/routes/*.py`, `templates/**/*.html`, `docs/user-guides/**/*.md`

---

## The Surface

| Measure | Count |
|---------|-------|
| Routes across 8 blueprints | 198 |
| Routes that render a page | 74 |
| Templates on disk | 98 |
| Templates rendered directly by a route | 72 |
| Teacher + student page routes (docs' primary audience) | 58 |
| Teacher-toggleable features | 6 (payroll, rent, banking, insurance, hall_pass, store) |

Blueprint distribution: `admin` 94 routes, `system_admin` 33, `student` 27, `api` 22, `main` 13, `docs` 5, `recovery` 3, `analytics` 1.

The 26 templates with no rendering route are layouts, macros, error pages, and partials — expected, not gaps.

---

## Headline Findings

1. **Coverage is broad but shallow.** Nearly every *page* has some guide pointing at it. Almost no guide covers the page's actual depth. The teacher store page is 1,160 lines across five tabs; its guide is 30.
2. **Roughly a quarter of the corpus is wrong, not merely thin.** Guides name sidebar destinations that no longer exist, tabs that were removed, and buttons that were never built in v2.
3. **Eight guides are orphaned** — they document features with no route, no template, and no nav entry.
4. **The contextual help wiring is systematically miscategorized.** All 34 wired pages open a *troubleshooting* page. Not one opens a feature guide. 24 pages have no help link at all.
5. **The sysadmin guides were in the wrong corpus entirely** and unreachable by their own audience. Resolved 2026-09-04 — rescoped to `SPEC-OPS-003`. See "Sysadmin Scope Decision" below.

---

## Gaps — Capabilities With No Guide

### Teacher

| Capability | Evidence | Proposed doc |
|---|---|---|
| ~~Student detail page — 7 tabs, per-transaction void, hall-pass entitlement adjustment, edit-info modal~~ | `student_detail.html` (893 lines), tabs at `:123-165` | ✅ done 2026-09-04 — `features/teacher/classroom/student-detail.md`. Documents **six** tabs; the Rent tab never renders (defect #27). Surfaced defects #26, #27, #28, and corrected a false Reset description in `students-overview.md` |
| ~~Hall pass configuration — pass types, queue limits, simultaneous-out limits~~ | `hall_pass_setup.html` (643 lines), `:230-278` | ✅ done 2026-09-04 — `features/teacher/classroom/hall-pass-setup.md`. Surfaced defect #29: the page cannot read or write, and Save silently resets the class to the five built-in destinations. Guide leads with what the class actually runs on |
| ~~Roster bulk actions + timed delete confirmation~~ | `admin_students.html:380-430`, `:1185-1294` | ✅ no new doc needed — already covered by `students-overview.md` (bulk toolbar at `:59`, 30-second / type-DELETE-STUDENTS / press-and-hold gate at `:80`). **Do not create `students-bulk-actions.md`.** |
| ~~Store bundles, bulk discounts, collective goals~~ | `admin_store.html:573,596,624` | ✅ done 2026-09-04 — `features/teacher/economy/store-bundles-goals.md`. Surfaced defects #30 (bundle quantity decorative — student promised N uses, receives one), #31 (bulk discount displayed but not charged), #32 (collective goals never complete or expire). Guide tells teachers to leave bundles and bulk discounts off and to enforce goal deadlines by hand; `store-items.md` corrected to stop repeating the form's claims |
| ~~Store redemption audit log with filters~~ | `admin_store.html:748-783` | ✅ no new doc needed — already covered by `store-redemptions.md`, which described the tab wrongly and has been corrected in place. Surfaced defect #33: the tab is the pending queue, not an audit trail, and it discards each request on approve/reject. **Do not create `store-audit-log.md`.** |
| ~~Payroll Advanced Mode — overtime, rounding, pay simulator, auto-run~~ | `admin_payroll.html:424,573-609,687,724-747,107` | ✅ done 2026-09-04 — `features/teacher/economy/payroll-advanced-mode.md`. Surfaced defects #34 (overtime stored, never paid), #35 (rounding stored, never applied; summary panel misreports both), #36 (automatic payroll never arms its schedule cursor; *Auto run* and *Attendance rules* are phantom controls). Guide keeps teachers to the live fields — time increment, daily limit, custom schedule; `payroll-settings.md` rewritten off the real Simple Mode form and warned to run payroll by hand |
| Manual payment templates (save/apply) | `admin_payroll.html` Manual Payments pane | `features/teacher/economy/payroll-manual-payments.md` |
| ~~Rent bill preview, incremental payment, CWI warning bypass, hall-pass rent items~~ | `admin_rent_settings.html:481,592-600,611,720-777` | ✅ no new doc needed — all four already covered: preview and incremental payment in `rent-behaviors.md:42-48,62`, the CWI bypass in `rent-settings.md:56`, hall-pass rent items in `rent-itemization.md:36,46`. Unlike the store mechanics, these are live — preview is consumed at `app/routes/student.py:2323` and `app/services/obligation_view_model.py:255`, incremental payment at `app/feats/rent_payment_feat.py:192,205`. **Do not create `rent-bill-preview.md`.** |
| ~~Insurance hide vs retire, availability states, policy versioning~~ | `admin_insurance.html:57-64`, `admin_edit_insurance_policy.html:167` | ✅ done 2026-09-04 — no new file. Hide/retire and availability states were already correct in `insurance-enrollment.md:29-42`; versioning was the real gap, so the v1 stub `features/teacher/bills/insurance-policies.md` was rewritten in place to the real form. Surfaced defects #37 (an edit leaves the old version on sale to students) and #38 (grouped tiers cannot be edited; hidden policies cannot be un-hidden), and corrected three waiting-period claims in `insurance-enrollment.md` that contradicted #22. **Do not create `insurance-versioning.md`.** |
| ~~Expected Weekly Hours; selective rebalance apply timing~~ | `admin_economic_engine.html:298,220-247` | ✅ done 2026-09-04 — no new file. Both halves were nominally covered but wrongly: expected hours belongs to `economic-engine.md:33-40` (corrected to say the field lives on this page, not payroll settings, with its 0.25–80 range and Needs setup / In-Use badges; `store-pricing.md` carried the same wrong sourcing and was fixed), apply timing to `policy-mode-rebalancer.md:59-68`. Surfaced defects #39 (a queued rebalance never activates — `activate_due_rebalances` is imported and never called, while the UI shows a confident *Economy Update Scheduled* badge on the option it marks *Recommended*) and #40 (the preview can only ever contain rent). **Do not create `expected-weekly-hours.md`.** |
| ~~Class creation and class switching~~ | `admin_create_class.html`, `admin_select_class_context.html` | ✅ done 2026-09-04 — no new file. Creation was already correct in `features/teacher/classroom/class-setup.md`; the switching paragraph was expanded in place (persists on the account not the session, inline failure warning, the **Select Your Class** fallback gate) and a renaming section added. Surfaced defect #41: Section is stored and editable but rendered nowhere, while the switcher lists classes by name alone — so the guide's old advice to use Section to tell periods apart was actively wrong and has been reversed. **Do not create `settings/class-switching.md`.** |
| ~~Teacher support tickets (submit + My Tickets)~~ | `admin_support_tickets.html` | ✅ done 2026-09-04 — `features/teacher/settings/support-tickets.md`, the last teacher gap. Surfaced defects #42 (Title required, never stored, and silently the dedup key — every ticket lists as *Support Ticket*) and #43 (status badge branches on values that no longer exist, so it is always yellow and can render *Escalated_To_Dev*). Guide leads with the rule that a student's issue must be raised by the student first |

### Student

| Capability | Evidence | Proposed doc |
|---|---|---|
| **The entire hall pass workflow.** No student hall-pass page exists; the flow lives in the dashboard Attendance card. One polymorphic button relabels Break → Pending → Leave → Return. Plus passes-left badge and restroom queue UI. | `student_dashboard.html:180-246`, `static/js/attendance.js:177-236,447,472` | `features/student/work/hall-passes.md` |
| "Done for the day" — PIN-gated day lock, reachable only inside the Break modal | `attendance.js:283-292` | fold into `features/student/work/start-end-work.md` |
| **Student-verified teacher account recovery** — dashboard banner, passphrase gate, one-time 6-digit code handed over in person | `student_dashboard.html:39-67`, `student_verify_recovery.html:27-35,70-85` | `features/student/account/verify-teacher-recovery.md` |
| PIN vs passphrase rules — transfers and purchases need the passphrase, using an item needs the PIN | `student_transfer.html:412-446`, `student_shop.html:322-324,360-361` | `features/student/account/pin-vs-passphrase.md` |
| Insurance tier groups, one-plan-per-group, cancel = stop-renewal (no refund) | `student_insurance_marketplace.html:30-39,55-97` | ~~`features/student/bills/insurance-tiers-and-cancellation.md`~~ — **folded into `insurance-coverage.md` instead (2026-09-04).** A separate file would have split enrollment across two guides: tiers are *how you choose what to buy* and cancellation is *how you stop buying it*, both enrollment questions. `insurance-coverage.md` needed a rewrite regardless (it was 30 lines and described a nav path and a waiting period that do not exist), so the content landed there. Do not re-create the third file. |
| Rent late fees, waivers, obligation history | `student_rent.html:58-95,259-294,321-387` | ~~`features/student/bills/rent-history-and-late-fees.md`~~ — **already covered by `rent-payments.md` (verified 2026-09-04).** That guide was rewritten in Phase 3 and already documents the one-bill rent+late-fee model, the Late Fee History card, waivers, and the obligation-history counters and table. This gap entry was written against the pre-Phase-3 version of the file. Do not create the second file. |
| ~~12-month savings projection chart~~ | `student_transfer.html:111-146,498-554` | ✅ done 2026-09-04 — `features/student/banking/savings-interest.md` rewritten |
| Productivity-type insurance claims (multi-day grid) | `student_file_claim.html:56-79` | extend `features/student/bills/insurance-claims.md` |

### Public / unauthenticated — zero coverage today

| Capability | Evidence | Proposed doc |
|---|---|---|
| ~~Public hall-pass verification kiosk~~ | `main.py:287,295-300`, `hall_pass_verify.html:97-124` | ✅ done 2026-09-04 — `features/public/hall-pass-verification.md`. Written for front-office staff as the reader, and for the teacher who has to hand them the link. Surfaced defects #44 (no token is ever minted lazily, so the button does not exist until you press **Regenerate QR** once), #45 (the button promises a QR code that is never produced) and #46 (times render as raw UTC ISO strings) |
| ~~PWA install and offline behavior~~ | `offline.html`, `/sw.js` | ✅ done 2026-09-04 — `features/public/offline-and-install.md`. The load-bearing point is that installing changes how the app *launches* and adds no offline capability: `authRoutes` in `sw.js` are network-only on purpose, because cached class data could show one class's numbers to another |
| ~~Maintenance page~~ | `maintenance.html:196,206,218` | ✅ done 2026-09-04 — `features/public/maintenance-page.md`. Documents all seven `MAINTENANCE_BADGE_TYPE` values, the two info tiles, the 60-second self-refresh, and states plainly that the System Admin bypass is not available to teachers or students |
| ~~Error pages 400/401/403/404/500/503~~ | six `error_*.html` templates | ✅ done 2026-09-04 — `diagnostics/error-pages.md`. Organized around whether the number means *you* or *us*: 400/401/403/404 are worth retrying, 500/503 are worth reporting. The 500 section is built around capturing the Error ID |
| ~~Privacy and Terms have **no in-app doc counterpart.**~~ | `main.py:235-244` | ✅ done 2026-09-04 — `legal/index.md` now links out to `/privacy` and `/terms` and explains the split: these guides cover how the *software* may be used and reused, Privacy and Terms cover the reader's relationship with the *service*. No copy of either was made in-repo — they are deliberately published where a person without an account can read them |

---

## Orphaned Docs — Features That No Longer Exist

Delete or rewrite from scratch. These describe pages with no route.

| Doc | Reality |
|---|---|
| `features/teacher/economy/transactions.md` | `/transactions` now 302s to `/banking`; transactions are a tab (`admin_banking.html:91-103`) — **rewritten in Phase 3** against the Banking > Transactions tab |
| `features/teacher/economy/analytics.md` | The analytics route renders a page titled **Interpretation** with a payroll-cycle selector and an `awaiting_first_completed_cycle` empty state. Nothing in the guide matched — **replaced in Phase 3** by `features/teacher/economy/interpretation.md` |
| `features/teacher/economy/payroll-adjustments.md` | Describes Rewards & Fines tabs. `admin_payroll.html:205-228` has four panes and none is Rewards; the `editReward`/`saveReward` JS at `:1294-1345` is dead code. Manual payments are credit-only (`:852`) — **renamed in Phase 3** to `manual-payments.md` and rewritten against the Manual Payments tab |
| `features/teacher/classroom/attendance-corrections.md` | `admin_attendance_log.html` is a read-only filtered table. No correction tooling — **rewritten in Phase 3**: the log locates the problem, the fix is Bulk Actions > Start Work / Break on `admin_students.html:379-430` |
| `features/teacher/classroom/class-setup.md` | No matching sidebar destination — **rewritten in Phase 3** against **Create New Class** (`layout_admin.html:233-238` → `admin_create_class.html` + `_class_setup_fields.html`), the join-code card, and the Add Students grid |
| `features/sysadmin/teacher-management.md` | **Fully orphaned.** No route, template, or nav entry; no `manage_teachers`/`delete_admin` symbol exists. **Deleted** — see Sysadmin Scope Decision. |
| `features/sysadmin/platform-communication.md` | Global Announcements half is orphaned — no global announcement model or route; announcements are teacher-owned and class-scoped (`admin.py:9401-9416`). **Deleted** — see Sysadmin Scope Decision. |
| `features/sysadmin/security-access.md` | "Manage Admins", "Reset TOTP", "Delete administrator", and the "Sysadmin Registration Phrase" all describe nonexistent screens. The dashboard admin table is display-only. Only the passkey section is real. **Deleted** — see Sysadmin Scope Decision. |

---

## Stale Docs — Wrong Nav, Wrong Labels, Wrong Controls

**Status: all resolved (2026-09-04).** Every teacher and student entry below has been corrected or the file renamed to the product's own label; the sysadmin entries were rescoped out of the user guide into developer docs under the Operations domain. The list is kept as the audit record of what was wrong and why.

The v2 teacher sidebar (`layout_admin.html:100-265`) is the yardstick. Note that `templates/admin_nav.html` is a leftover v1 navbar still linking `admin.transactions` and `admin.economy_health` — likely the origin of several of these.

**Teacher**
- `economy/economy-health.md`, `economy/policy-mode-rebalancer.md` — say "Economy > Economy Health"; the sidebar item is **Economic Engine**.
- `settings/feature-toggles.md` — says "Settings > Features" and implies payroll/banking are toggleable. Real path is **Class Tools > Economy Features**; payroll and banking are `essential_features` with **no toggle**, and pricing features are gated behind `view.cwi_ready`.
- `settings/personalization.md` — page is **Class Tools > Customizations**.
- `settings/account-recovery.md` — references a nav item that does not exist; the entry point is a dashboard banner (`admin_dashboard.html:24`).
- `bills/insurance-claims.md:22`, `bills/insurance-enrollment.md:21` — reference a "Claims" tab and an "Active Student Policies" tab. `admin_insurance.html` has **no tabs**; it is a flat list.
- `classroom/student-issues.md:27,34` — describes a "Void Transaction" button and a "bug reward" checkbox. Neither exists; the real actions are Post Compensating Transaction / Manual Adjustment / Deny Issue (`admin_view_issue.html:262-270`). The "Resolved (closed)" tab is actually **Final Review** plus a separate Close Issue form requiring a Closure Summary.
- `classroom/students-overview.md` — describes a CSV template + Individual Add. v2 is a paste-from-spreadsheet staging grid (`admin_students.html:527-600`).

**Student**
- `account/switch-class.md` — class dropdown is at the **bottom** of the sidebar labeled "Switch Class", not the top; Add Class is a `+` icon (`layout_student.html:134-156`).
- `work/start-end-work.md` — "click Done." v2 is Break → modal → "Done for the day".
- `work/attendance-history.md` — says records read Present/Late/Absent; v2 shows **Start Work / Break** (`student_payroll.html:81`).
- `account/login-setup.md` — says "4-digit PIN" and omits the passphrase. Setup enforces **4–8 digits** plus a zxcvbn-gated passphrase requiring score ≥ 3 (`student_pin_setup.html:275,339,359`).
- `bills/rent-payments.md` — button reads **"Pay Bill ($X)"**, not "Pay Rent" (`student_rent.html:238`).
- `diagnostics/student/login.md:20` — "Passphrases are only for purchases and transfers." Also required for `/verify-recovery`.
- `diagnostics/student/hall-pass.md:22` — "A pass only works at a terminal after it is approved." False; Leave/Return are student-initiated from the dashboard.
- `diagnostics/student/attendance.md:15,28` — describes three peer buttons; there are two.
- `diagnostics/student/classes.md:21` — class switcher is in the sidebar on every page, not on the dashboard.

**Sysadmin**
- `sysadmin/dashboard-overview.md:17-25` — sends the reader to System Logs, Error Logs, and Combined Logs as three destinations. Only Combined Logs is in nav, and `/error-logs`, `/network-activity`, `/logs-testing` **hardcode empty result sets** (`system_admin.py:656-658,678,705-710`). `combined_logs`' own docstring says it replaces them.
- `sysadmin/platform-communication.md:34-44` — status vocabulary is `new/reviewed/closed/spam`, not "In Progress"/"Resolved"; there is no "Send Reward" on a user report (that lives on the escalated-issue resolve form).
- `sysadmin/security-access.md:26` — nav label is "Passkey Settings", not "Manage Security".

---

## Thin Docs — Accurate but Far Shallower Than the Page

Ordered by severity of the depth mismatch.

| Doc | Page depth |
|---|---|
| `economy/store-items.md`, `store-redemptions.md` | 1,160-line five-tab page; Deactivate-vs-Delete and "Managed by Rent Settings" locking unmentioned |
| `bills/rent-settings.md` | 1,384 lines, multi-section accordion |
| `classroom/dashboard-overview.md` | 634 lines with inline approval queues (redemptions / hall passes / claims) and payroll estimate |
| `student/store/browse-buy.md` | Four item types, bundles, bulk discounts, collective-goal deadlines, per-student limits, rent-perk free uses |
| `student/store/redemption-status.md` | My Items has five distinct states |
| `student/support/report-issues.md` | Omits the irreversibility warning, six student-visible statuses, and escalation-with-bug-reward |
| `classroom/hall-pass.md` | Four tabs plus queue and simultaneous-out limits |
| `economy/banking-settings.md` | Compound frequency (`admin_banking.html:442`) unmentioned |
| `classroom/announcements.md` | Per-announcement show/hide toggle unmentioned |
| `economy/payroll-history.md` | Covers the tab but not the separate `/payroll-history` page |
| `student/account/dashboard-overview.md` | Omits Weekly Stats, announcements, per-transaction report icon |
| `student/banking/accounts-transfers.md` | Omits voided/active badges and the 50-row cap |

---

## Contextual Help Wiring

Teachers and students reach docs through a help control in the page header. The target is resolved from `help_doc_map` in `layout_admin.html:267-312` (44 entries) and `layout_student.html:168-181` (12 entries), keyed on `current_page` and falling back to `request.endpoint`.

| Measure | Count |
|---|---|
| Distinct doc references across all templates | 44 |
| References that resolve to a real file | 38 |
| References broken (all developer-namespace, out of scope) | 6 |
| Teacher/student pages **with** a help link | 34 |
| Teacher/student pages **without** any help link | 24 |
| Wired pages whose link opens a **feature guide** | **0** |
| Wired pages whose link opens a **troubleshooting page** | 34 |
| Map keys pointing at endpoints that do not exist | 4 |

**The categorical problem:** every help link opens a diagnostics page. A teacher on the Store page who clicks help gets "Troubleshooting Store and Purchases" rather than a guide to the store. Troubleshooting is the right destination when something is broken, not when someone is trying to learn the page. Phase 5 should point contextual help at the feature guide and surface the diagnostics page as a secondary "Something's not working?" link.

**Dead map keys** (silently fall through to no help link): `admin.announcement_form`, `admin.claim_students`, `student.complete_profile`, `student.student_insurance`.

**Pages with no help link at all:**

*Teacher* — `/login`, `/signup`, `/recover`, `/recovery-status`, `/reset-credentials`, `/resume-credentials`, `/save-recovery-progress`, `/select-class-context`, `/create-class`, `/hall-pass/setup`, `/students/<id>`, `/announcements/create`, `/announcements/edit/<id>`, `/admin/analytics/` (sets `current_page=interpretation`, which is absent from the map)

*Student* — `/login`, `/create-username`, `/setup-pin-passphrase`, `/setup-complete`, `/add-class`, `/select-class-context`, `/insurance`, `/insurance/policy/<id>`, `/insurance/claim/<uuid>`, `/verify-recovery/<id>`

The account-setup and recovery flows are the most damaging omissions: they are exactly where a confused first-time user needs help, and they are the flows where no teacher is standing next to the student.

---

## Sysadmin Scope Decision — RESOLVED 2026-09-04

**Decision: the sysadmin console is developer documentation. It is rescoped to the Operations domain and specified by `SPEC-OPS-*`.**

The docs site already contradicted the old placement. `app/routes/docs.py:365-387` resolves a sysadmin session to the **`devops`** audience, and search enforces strict isolation at `docs.py:706-712` — the `user` audience sees only `user-guides/`, and `devops` sees everything *except* `user-guides/`. So a logged-in sysadmin could not find the sysadmin guides in search unless they manually flipped the audience cookie. The audience is also plainly the platform operator, not school staff: the surface is log tailing, a Grafana reverse proxy, HTTP error-page test harnesses, and a maintenance bypass.

Executed:

- Deleted `docs/user-guides/features/sysadmin/` (5 files) and `docs/user-guides/sysadmin_manual.md`. Roughly two-thirds of their content described screens that do not exist — "Manage Teachers", "Manage Admins", "Reset TOTP", "Global Announcements", "Sysadmin Registration Phrase" — so none of it was worth carrying forward verbatim.
- Wrote `docs/SPEC/SPEC-OPS-003_SYSTEM_ADMINISTRATION_CONSOLE.md` against the real blueprint: the four-destination nav (Dashboard, Support, Logs, Passkeys), the access-control model, the mutation boundary (the console may not touch classroom domain truth), and the known non-conformances.
- Removed the sysadmin card from `templates/docs/index.html` and the sysadmin accordion from `templates/docs/view.html`; added the new spec under the devops **Operations** card.
- Updated `docs/user-guides/README.md`, `docs/user-guides/features/index.md`, and `SOP-DOC-002`.

`docs/self-hosting/` remains unbuilt — `docs/README.md:66` lists it and `docs.py:56` already maps it to a friendly category name. That destination is still declared but empty, and is separate from this decision.

---

## App Defects Found During Inventory

Documentation work surfaced these product bugs. None are docs problems; recorded here so they are not lost.

1. **`GET /admin/store/edit/<id>` returns 500.** `render_template()` at `app/routes/admin.py:5153` is called with no template name. Its intended template `admin_edit_item.html` (366 lines) is orphaned as a result. Regression from `4f2e7dc3`. *(Spun off as a separate task.)*
2. **`/student/insurance/policy/<enrollment_id>` is unreachable and would 500.** No template links to `student.view_policy`, and the template's own `url_for` kwargs (`policy_id`, `enrollment_id` at `student_view_policy.html:196,219,248`) don't match the route params (`policy_uuid`), so rendering raises a BuildError.
3. **Three sysadmin log pages are hollow** — `/error-logs`, `/network-activity`, `/logs-testing` hardcode empty result sets.
4. **PIN length is inconsistent** — setup allows 4–8 digits (`student_pin_setup.html:275`) while `student/recovery/reset_form.html` states 4–6.
5. **`templates/admin_nav.html` is a dead v1 navbar** still linking `admin.transactions` and `admin.economy_health`.
6. **`sysadmin.update_user_report` never commits.** `app/routes/system_admin.py:1000-1015` assigns status, notes, and review metadata directly on the `Issue` model, then flashes success inside a `try` with no `db.session.commit()` — and mutates outside the FEAT layer. Recorded in `SPEC-OPS-003` §VIII.
7. **Payroll "Save Template" is a no-op that reports success.** `app/routes/admin.py:8001-8005` is a bare `pass`, yet `save_only` flashes `Template "<name>" saved successfully!`. Nothing is persisted and no picker exists to load a template back — the `presetSelector` / `clearFormBtn` elements the JS at `admin_payroll.html:949-985` binds to are not in the markup.
8. **The Payroll help drawer describes a tab that does not exist.** `admin_payroll.html:129-142` renders a "Rewards & Fines" accordion item telling teachers to use the "Rewards & Fines tab". There are four tabs — Overview, History, Settings, Manual Payments — and deductions belong to Obligations (`admin.py:7989-7991`).
9. **Teachers have no navigable path to insurance claims.** `admin.view_student_policy` (`app/routes/admin.py:6291`) carries `@admin_required` but **no `@admin_bp.route(...)` decorator**, so it is absent from the URL map and its template `admin_view_student_policy.html` can never render. That template is the only thing linking to `admin.process_claim`, so the 254-line `admin_process_claim.html` review screen — approve/reject, approved amount, validation status, claims history, caps — is reachable only by hand-typing `/admin/insurance/claim/<claim_id>`, and nothing in the UI exposes a claim ID. Meanwhile students *can* file claims (`/student/insurance/claim/<policy_uuid>`), so claims accumulate with no teacher-facing queue. `admin_insurance.html` has no tabs and no claims or enrollment listing at all.
10. **The roster CSV export always reports "None" for Insurance Plan.** `admin.export_students` (`app/routes/admin.py:8264`) writes an `Insurance Plan` column but initialises `active_insurances_map = {}` and never populates it (`app/routes/admin.py:8315-8318`, comment: "Insurance policy prefetch is not yet wired"). Every row therefore reads `None` regardless of actual coverage. All other exported columns are correct.
11. **The Student Management help drawer describes controls that do not exist.** `admin_students.html:189` tells teachers to "use the **Remove** action next to their name in the Class Roster" — the control is labelled **Delete**. The drawer also refers to a "Class Roster tab" for the join code (`:95`, `:139`) as though multiple class tabs existed; the page renders one class at a time.

12. **Hall-pass destinations never reach the student, and teacher configuration is silently discarded.** The client and the API disagree on the payload key in three places:
    - **Teacher save is a no-op.** `templates/hall_pass_setup.html:588` POSTs `pass_types: passTypesToSave`, but `app/routes/api.py:1209` reads `data.get('pass_type_payload', [])`. The saved list is therefore always empty, while the endpoint still returns `"message": "Hall pass configuration saved successfully"`.
    - **Teacher setup page never re-renders saved types.** `templates/hall_pass_setup.html:620` reads `data.pass_types || []` from a GET that returns `pass_type_payload` (`app/routes/api.py:1187`, `:1194`).
    - **Student break menu is always empty.** `static/js/attendance.js:227` calls `renderBreakDestinations(data.pass_types || [])` against `/api/hall-pass/available-types`, which returns `pass_type_payload` (`app/routes/api.py:1359-1362`). **Choose Break Type** therefore always falls through to "No hall-pass destinations are currently available," leaving **Done for the day** as the only working option.

    There is a **second, independent mismatch inside the same student call**, so fixing the payload key alone will not repair the flow. Every item the API emits is keyed `pass_name` — both the configured branch (`api.py:1355`) and the `HallPassSettings.get_default_pass_types()` fallback (`app/models.py:854-860`, which supplies Bathroom / Water Fountain / Office / Nurse / Counselor). But `renderBreakDestinations()` reads `passType.name` (`attendance.js:259`) and then drops any item that resolves empty (`:260`). With the key corrected the list would still render zero buttons.

    A complete fix therefore needs three edits: the teacher save key, the teacher load key, and — on the student side — both the payload key and `passType.name` → `passType.pass_name`.

    Net effect: the hall-pass feature cannot be used end to end. This blocks the planned `features/student/work/hall-passes.md` guide from describing a working flow.

13. **The Store page's pending-redemption Details column is hardcoded to a dash.** `admin_store.html:246-248` renders `<small class="text-muted">-</small>` in place of `entitlement.redemption_details`. The data is real and captured — student answers the prompt at `student_shop.html:356`, posted at `api.py:393` — and it renders correctly on the dashboard queue (`admin_dashboard.html:242-244`) and the student detail page (`student_detail.html:489`). Only this table drops it, which is the one place a teacher is most likely to be approving from. Documented as a workaround in `features/teacher/economy/store-redemptions.md`; should be a one-line template fix.

    Minor, same page: **View All Pending Items** (`admin_store.html:268`) links to `#overview`, the tab the button is already on. It does nothing.

14. **The hall-pass Out Limit is never consulted; only one student can be out at a time.** `admin_hall_pass.html:142` offers an **Out Limit** input accepting 1–50 students, but `admin_hall_pass.html:239` disables every **Left Class** button with `{% if out_of_class %}disabled{% endif %}` — truthy for any non-empty list. So the moment one student is marked out, no second student can be, regardless of the configured limit. The teacher must mark the first **Returned** to unblock the queue.

    The fix is to compare against the limit rather than testing the list for emptiness. Documented as current behaviour in `features/teacher/classroom/hall-pass.md`.

15. **`prevent_purchase_when_late` is a dead setting — nothing enforces it.** `admin_rent_settings.html:621` renders the **Prevent Purchase When Late** switch, `admin.py:5459` persists it, and `admin_rent_settings.html:279` shows a status badge for it, but no purchase path ever reads the column. `execute_store_purchase()` in `app/feats/store_purchase_feat.py` resolves the policy, the economic engine, and the ledger plan, and never consults rent lateness. A repo-wide search finds the name only in `app/models.py`, the admin save handler, the template, and migrations.

    So a teacher can switch it on, watch the badge go green, and still have students who are months behind on rent buying freely. Both label variants (**Prevent Purchase of Items Not Part of Rent** and **Prevent Purchase/Redemption When Late**) are equally inert. Documented as a warning in `features/teacher/bills/rent-behaviors.md`.

16. **The issue form's expected-outcome counter advertises twice the limit it enforces.** `student_submit_issue.html:114-116` renders the counter as *N / 1000 characters*, but both `StudentIssueSubmissionForm.expected_outcome` and `TransactionIssueSubmissionForm.expected_outcome` (`app/forms.py:256-259`, `:270-273`) validate `Length(max=500)`. A student who trusts the counter and writes 700 characters has the submission rejected with *Expected outcome must be 500 characters or less* — after being told they had room. The adjacent **explanation** counter is correct at 1000.

    One-character template fix. Documented as a tip in `features/student/support/report-issues.md`.

17. **`/admin/payroll-history` is an orphaned page — nothing in the app links to it.** `admin.payroll_history` (`app/routes/admin.py:7121`) renders **Detailed Payroll History**, the only payroll surface with a **From**/**To** date-range filter. A repo-wide search of `templates/` and `static/js/` finds no `url_for('admin.payroll_history')` outside the page's own filter form, and no sidebar entry. `layout_admin.html:292` maps the endpoint for the contextual help icon — which only helps a teacher who is already there.

    The History tab on **Economy > Payroll** covers the common case but has no date filtering, so the one capability unique to this page is unreachable without typing the URL. Either link it from that tab or fold the date filter into the tab and retire the page. Documented as a warning in `features/teacher/economy/payroll-history.md`.

18. **The store Pricing Tier dropdown advertises percentage bands the app does not use.** `StoreItemForm.tier` (`app/forms.py:12-18`) labels the choices *Basic (2-5% of CWI)*, *Standard (5-10%)*, *Premium (10-25%)*, *Luxury (25-50%)*. Those are the hardcoded `EconomyBalanceChecker.STORE_TIERS` fallbacks (`app/utils/economy_balance.py:111-116`), but `_store_tiers()` (`:167-176`) overlays the active economic mode's profile — and all three modes in `app/utils/economy_policy.py` define a full `store_tiers` block, so the fallback is never reached.

    In **Default** mode the real bands are Basic 1–3%, Standard 2–5%, Premium 5–15%, Luxury 15–30% (`economy_policy.py:59-64`); **Tight** and **Comfortable** differ again. A teacher who selects **Luxury** reads "25-50% of CWI" on the label and then sees a **Recommended range** box computed from 15–30% directly beneath it. The dollar range is correct; the label is not.

    Fix is to derive the labels from the active profile, or drop the percentages from the labels entirely. Documented as an IMPORTANT callout in `features/teacher/economy/store-pricing.md`; the previously-wrong band list in `features/teacher/economy/store-items.md` has been corrected to point there.

19. **The student dashboard's Restroom Queue panel is dead markup.** `student_dashboard.html:185-193` renders a queue block — *Restroom Queue: N waiting*, a `queueLimitBadge`, and a `queuePreview` line — each hardcoded to `style="display: none !important;"` with a comment claiming it is *"Hidden by default, populated by JS."* Nothing populates it. A repo-wide search of `static/js/` and `templates/` finds no other reference to `queueStatus`, `queueCount`, `queuePreview`, or `queueLimitBadge`; the only near-match is `queueStatusLabel` on the teacher's `admin_hall_pass.html`, an unrelated element.

    The `!important` means even a script that set `style.display = 'block'` would not reveal it. Meanwhile `max_queue` is configured per pass type by the teacher and returned by `/api/hall-pass/available-types`, so the data exists and the student is simply never shown it. Either wire the panel to that payload or delete the block. Deliberately **not** described in `features/student/work/hall-passes.md`, since no student can see it.

20. **`consume_pass` is a dead per-destination setting — every approved pass deducts one.** The flag is carried on every pass type, defaulted to `True` (`app/models.py:855-859`), and strictly validated on save by both `app/feats/attendance.py:90-92` and `app/routes/api.py:1223-1230`, which reject any pass type whose key set is not exactly `{pass_name, max_queue, consume_pass}`. Nothing then reads it. `_record_hall_pass_log_impl` (`app/feats/prod.py:437-441`) calls `consume_hall_pass(...)` unconditionally at teacher approval, and `_enforce_hall_pass_settings` (`:98-157`) inspects only `enabled` and `max_queue`. A repo-wide search finds no read of `consume_pass` anywhere.

    So a teacher who sets Nurse to not consume a pass still watches the student's balance drop by one. Note the neighbouring keys in that same payload *are* honoured: `max_queue` is enforced both as a per-destination simultaneous-out cap (`:149-156`) and, combined with `max_queue_limit`, as a class-wide queue ceiling (`:145-147`).

    This also invalidated a published claim — `diagnostics/student/hall-pass.md` told students that "some destinations do not deduct a pass," which has been corrected.

21. **Spending money is credential-gated inconsistently.** Mapping every student action that moves money produced no coherent rule:

    | Action | Gate |
    |---|---|
    | Store purchase | Passphrase (`student_shop.html:322`) |
    | Checking ↔ savings transfer | Passphrase (`student_transfer.html:431`) |
    | Using an item already owned | PIN (`student_shop.html:360`) |
    | Start Work / Done for the day | PIN (`attendance.js:31,287`) |
    | **Buy insurance** | **Nothing** (`student_insurance_marketplace.html:85-91`) |
    | **Pay a rent bill** | Browser `confirm()` only (`student_rent.html:237`) |
    | **Cancel insurance** | Browser `confirm()` only (`:35`) |

    Buying insurance is the outlier: **Buy — $X** is a single click that immediately commits to a recurring premium, with no passphrase, no PIN, and not even a confirmation dialog — while a one-off $5 store item demands the passphrase. Cancelling is likewise one confirm away, and cancellation is not reversible by the student.

    Not a crash, so not urgent, but it undercuts the passphrase's purpose: a student who leaves a session open is protected on the store and blocked on transfers, yet fully exposed on the surface with recurring cost. Documented as-is in `features/student/account/pin-vs-passphrase.md`, which is the guide that made the gap visible.

22. **`waiting_period_days` is a dead insurance setting — coverage is always effective immediately.** The field is a real column with a non-negative check constraint (`app/models.py:2329,2383-2384`), is required-or-forbidden per insurance type by three separate constraints (`:2396-2405`), is validated and persisted by FEAT-CLASS-003 (`app/feats/class_configuration/feat_class_003_insurance_policy_management.py:79-120`), is editable by teachers on a labelled form field (`admin_edit_insurance_policy.html:113-115`), and is seeded with real values by the economic engine presets — **Basic policies default to a 7-day wait** (`app/services/economic_engine.py:107-110`).

    Nothing enforces it. The claim path checks the incident against the entitlement's `GRANTED` timestamp only (`app/feats/insurance_claim_feat.py:295-298` for TRANSACTION, `:437-441` for PRODUCTIVITY), rejecting anything that *predates* the purchase and nothing else. A repo-wide search finds no read of `waiting_period_days` outside the config/definition/preset write path. A teacher who configures a 7-day wait gets a policy claimable one minute after purchase.

    Compounding it, the only student-facing surface that *displays* the waiting period — `student_view_policy.html:41,67` — is unreachable: `student.view_policy` (`app/routes/student.py:1759-1761`) is referenced by zero templates. The marketplace links to `file_claim` and nothing else. So the setting is neither enforced nor visible.

    Third instance of the same pattern as #19 (dead markup) and #20 (dead `consume_pass`): a teacher-configurable, strictly-validated setting with no consumer. Worth a sweep of the settings surfaces rather than three point fixes.

    This also invalidated a published claim — `insurance-coverage.md` told students to "check the waiting period before enrolling," which has been corrected to state that coverage starts immediately.

23. **The rent status card hardcodes the label "Monthly Rent" at any frequency.** `student_rent.html:133` renders `<strong>Monthly Rent:</strong>` unconditionally above the headline amount. The **Rent Information** card 170 lines below gets this right, branching over `frequency_type` to say *per day* / *per week* / *per month* / *per N units* (`:305-308`) — so a weekly class shows an amount captioned "Monthly Rent" directly above prose stating rent is charged weekly.

    Cosmetic, and the payable total is never wrong, but it is the most prominent number on the page and it contradicts the page's own explanation. Documented as a caveat in `features/student/bills/rent-payments.md` until fixed.

    Same page, lower severity, also worth a look: the Rent Information card states the grace period twice in consecutive bullets (`:310-316`), once as *"You can pay your rent up to N days late without late fees"* and again as *"Grace period: N days after due date."*

24. **Savings interest is forecast everywhere and posted nowhere — nothing invokes the payout.** The payout command is real and correct: `_apply_monthly_savings_interest` (`app/services/ledger_service.py:658-773`) reads the class's rate from the canonical Economic Engine, computes the credit with the shared accrual engine so a runtime payout equals the UI projection (SPEC-ECON-001 §10), guards against double-crediting within the class-timezone month, and posts a pending `Interest` transaction described *Monthly Savings Interest*.

    Nothing calls it in the running app. Its only caller is the compatibility wrapper `apply_savings_interest` (`app/routes/student.py:1396-1405`), which is exported from `app/__init__.py:1008,1016` and invoked by no route, no FEAT, and no job — only by `tests/dom/class/test_interest.py` and `tests/helpers/ledger.py:133`. `init_scheduled_tasks` (`app/scheduled_tasks.py:577-615`) registers six jobs — daily limits, database maintenance, audit invariant check, rent reconciliation, automatic payroll, insurance expiry — and no interest job.

    Meanwhile the student sees the rate presented as live in three places on `student_transfer.html`: **Monthly Interest Rate** and **Estimated Monthly Interest** on the Statistics card (`:86-97`), a growing 12-month projection chart (`:110-146`), and a Transfer-tab tip reading *"Your savings account earns N% annual interest (approximately $X per monthly payout)"* (`:246-259`). Teachers can configure APY, payout frequency, and calculation type (`app/routes/admin.py:8827-8900`), and the class-health surface nudges them to turn it on (`:6897`).

    Severity is judgement-dependent — no money is lost and no balance is wrong — but it is the widest promise/behaviour gap found so far: the entire savings incentive is advertised and never paid. `features/student/banking/savings-interest.md` therefore describes the figures as projections from the class's settings and tells students a credited payout appears in Transactions as *Monthly Savings Interest*, without asserting a cadence.

25. **The projection caption and the projection series start from two different balances.** The caption interpolates `savings_balance` (`student_transfer.html:134,141`), which is the *available* balance from `get_available_balances` (`app/routes/student.py:503-507`), while the plotted series starts from `posted_savings_balance` via `get_posted_balance` (`:1349,1361-1368`) — deliberately, because the runtime payout's eligible base is the posted balance (SPEC-ECON-001 §9.2/§13).

    The two agree whenever nothing is held or pending against savings, which is the normal case, so this surfaces rarely. When they diverge, the caption states a starting balance the chart does not use. Cosmetic; the fix is to caption the value the series actually begins at.

26. **The student detail page instructs teachers to relay a Date of Birth the app never collects.** The yellow **Account Recovery / Setup** card on `student_detail.html` (~`:305`) ends with *"Student must also enter their **Date of Birth** as recorded in your roster."* There is no `date_of_birth` column anywhere in `app/models.py`. The only `dob_*` fields in the codebase belong to `StudentCompleteProfileForm` (`app/forms.py:218-226`), whose route `student.complete_profile` does not exist — a repo-wide grep finds it surviving only as a stale key in the help map at `templates/layout_student.html:180`. The live claim form (`StudentClaimAccountForm`) takes join code, first name, last name, and an optional dedupe code.

    User impact is direct: a teacher following the card's instruction will read out a value the student is never asked for, and will conclude the claim is broken when the student cannot find the field. `features/teacher/classroom/student-detail.md` carries an explicit NOTE telling teachers to ignore it.

27. **The Rent tab on the student detail page can never render.** All three rent regions on `student_detail.html` (`:147` tab button, `:210` Housing row, `:564` tab pane) are guarded on `global_rent_enabled and student.is_rent_enabled`. The route's `render_template` call (`app/routes/admin.py:4074-4094`) does not pass `global_rent_enabled`, and the context processor supplies it as a hardcoded `False` in both branches (`app/__init__.py:636-653`, commented *"Deprecated: rent is now per-teacher"*).

    The dead markup also references `student.rent_last_paid`, `student.rent_due_date`, and `student.rent_overdue`, none of which exist on `Seat` — so were the guard ever satisfied the tab would silently render Never/N/A/No. The guide documents six tabs, not seven. Same class as defects #19/#20/#22: configured, validated, and unreachable.

28. **Insurance on the student detail page always reads "None."** `app/routes/admin.py:4005` hardcodes `active_insurance = None` with the comment *"Removed legacy insurance enrollment lookup"*, so the Overview tab's Insurance row falls to its `{% else %}` branch for every student regardless of policy. This is the same root cause as the already-logged roster-CSV defect (`students-overview.md:101`), now confirmed on a second surface — the lookup was removed in both places and replaced in neither.

29. **The Hall Pass Configuration page can neither read nor write, and saving silently resets the class to defaults.** This is defect #12's schema mismatch (`pass_types` vs `pass_type_payload`) appearing again on the teacher side, in both directions, and it is worse here because the write path is destructive.

    *Read:* `hall_pass_setup.html:620` does `passTypesData = data.pass_types || []` against `GET /api/hall-pass/setup`, which returns `pass_type_payload` (`app/routes/api.py:1187,1194`). The list is therefore always `[]` and the card always renders *No pass types configured. Add one to get started.*, whatever the class has saved.

    *Write:* the page POSTs `{hall_pass_enabled, pass_types: [{name, queue_limit, simultaneous_limit, enabled}]}` (`:586-589`). `POST /api/hall-pass/setup` reads `data.get('pass_type_payload', [])` (`:1209`) and gets `[]`. The per-item validation loop (`:1216-1233`) never iterates, so the empty list passes, and `feat_save_hall_pass_setup_config` (`app/feats/attendance.py:72-112`) accepts it too — its `any(...)` guards are vacuously true over an empty list. The FEAT then retires the predecessor policy (`:98-101`) and inserts a new `IN_USE` row with `pass_type_payload=[]`. Because `HallPassSettings.get_pass_types()` (`app/models.py:862-866`) falls back to `get_default_pass_types()` when the payload is falsy, the class silently reverts to the five built-ins (Bathroom, Water Fountain, Office, Nurse, Counselor, each `max_queue` 10). The teacher sees *Configuration saved successfully!*

    Note also that the two schemas are not merely differently keyed — the field *names* are disjoint (`name`/`queue_limit`/`simultaneous_limit`/`enabled` vs the required exact key set `{pass_name, max_queue, consume_pass}`), so no rename of the outer key alone would fix the write. And there is no `simultaneous_limit` concept server-side at all: `_enforce_hall_pass_settings` (`app/feats/prod.py:145-155`) uses `max_queue` for both the global and per-destination checks. `Total Queue Limit` / `Total Simultaneous Limit` are acknowledged in a source comment (`hall_pass_setup.html:573-574`) as display-only and unenforced.

    `features/teacher/classroom/hall-pass-setup.md` documents the page but opens with the five destinations the class actually runs on and carries a CAUTION telling teachers not to press Save.

30. **Bundle quantity is decorative — students are promised N uses and receive one.** `execute_store_purchase` (`app/feats/store_purchase_feat.py:307`) loops `for unit_idx in range(quantity)`, where `quantity` is the number the student typed into the buy modal. `bundle_quantity` is never a factor, so a 5-item bundle bought once produces exactly one entitlement. The purchase modal states the opposite in so many words: `templates/student_shop.html:573-575` computes `quantity * bundleQuantity` and prints *You will get {N} total uses ({Q} bundles)*. There is no remaining-uses counter to draw down against — `app/services/entitlement_read_service.py:14` records that the service "does NOT persist mutable counters (uses_remaining, balance, etc.)", and a grep for `uses_remaining` / `quantity_remaining` finds nothing outside that comment. Outside the buy modal, `is_bundle` and `bundle_quantity` are read only for the *n bundle* badge (`admin_store.html:381-382`) and the *Bundle: n items* line on the browse card (`student_shop.html:75-78`), plus an `is_from_bundle` value assembled onto the teacher's recent-purchases namespace (`app/routes/admin.py:4835,4846`) that no template renders. Redemption is all-or-nothing: approve/reject move the whole entitlement to a terminal state (`app/routes/api.py:467-534`).

31. **Bulk discount is shown to the student and never charged.** `updateTotalPrice()` (`templates/student_shop.html:539-565`) applies `1 - (percentage/100)` once the quantity reaches the threshold, writes the reduced figure into **Total Price**, and reveals a savings line; the hint reads *Bulk discount applied!* (`:579`). The FEAT debits `policy_config.price * quantity` (`app/feats/store_purchase_feat.py:246`) with no discount term. `bulk_discount_quantity` and `bulk_discount_percentage` are parsed and range-validated in `app/services/store_policy_resolver.py:192-193,422-426` and are never applied to a price anywhere in `app/`. The student is quoted one number and charged a higher one.

32. **Collective goals neither complete nor expire.** Progress is computed live by `build_collective_progress_view()` (`app/services/store/builders.py:363-406`) over distinct students with a `GRANTED` / `PURCHASE` entitlement event (`app/routes/admin.py:4885-4903`), correctly scoped by `class_id`, and for *Whole Class Must Purchase* the target tracks class size (`admin.py:4920`). That is the whole of the feature. On reaching the target the student is told *Goal reached! Item will unlock soon.* (`student_shop.html:117`) and nothing unlocks — there is no fulfillment, notification, or teacher alert. On the deadline passing, nothing deactivates the item: `collective_goal_expires_at` is required for COLLECTIVE_GOAL (`store_policy_resolver.py:485-487`), stored under a comment claiming *"unmet goals deactivate the item on expiration"* (`app/models.py:930`), and thereafter read only to format a **Deadline** string (`builders.py:394-395`, `admin_store.html:413-416`). `app/scheduled_tasks.py` registers jobs for daily limits, database maintenance, audit invariants, rent reconciliation, payroll, and insurance expiry — none for store goals — and no lazy check exists on any page load.

    All three are documented in `features/teacher/economy/store-bundles-goals.md`, which tells teachers to price bundles as single rewards, to set bulk-discount thresholds no student will reach, and to treat a goal deadline as a date they enforce by hand.

33. **The Redemption Audit tab is not an audit log — it is the pending queue, and it loses the outcome it exists to record.** `execute_approve_redemption` and `execute_reject_redemption` both end in `db.session.delete(pending_action)` (`app/feats/entitlement_lifecycle_feat.py:107,118`), and the tab's only data source is `PendingAction` filtered to `authoritative_feat == "FEAT-STOR-002"` (`app/routes/admin.py:4943-4960`). A row therefore exists only while a request is unresolved. The **Approved** and **Rejected** options in the Action filter can never match anything, and an empty table means "nothing is waiting", not "nothing happened". The tab duplicates the Overview queue under a name that promises the opposite.

    Four further faults in the same block:

    - *Action column is meaningless.* `:4949` selects `PendingAction.authoritative_feat` as `action`, and `:4958` already filters that column to the constant `"FEAT-STOR-002"`, so `admin_store.html:814` renders the same badge on every row. The real action lives in `payload["action"]`, which the Action *filter* does query (`:4966`) — filter and column read different fields.
    - *Student filter raises.* `:4989` reads `row.student_display_name` from the `live_rows` Row objects, whose labelled columns are `id`, `entitlement_id`, `seat_id`, `class_id`, `action`, `notes`, `user_id`, `timestamp`, `source` (`:4945-4954`). No such attribute exists, so submitting the filter with any text raises `AttributeError`. The name is only assembled afterwards, at `:5004`, from the Seat's identity profile.
    - *Cartesian product.* The select list references `Seat` (`:4947`) and `ClassEconomy` (`:4951`) with no join — the only join is conditional on `audit_class` (`:4962`). The base query therefore emits an implicit cross join, multiplying every pending row by the seat and class tables and inflating both the rows shown and the *Showing N of M* count. `:4948` and `:4952` also both label a column `class_id`.
    - *Legacy badge unreachable.* `source` is the literal `"LIVE"` (`:4954`) and `inferred_rows` is initialised empty and never appended to (`:4996,5012`), so the `row.source == 'inferred_legacy'` branch at `admin_store.html:815-817` cannot fire. The **Class** dropdown is likewise inert: the query is already scoped to `selected_scope['class_id']` (`:4957`) and `class_display_label` is hardcoded to the selected class (`:5005`).

    **No separate `store-audit-log.md` was created.** The tab was already documented — wrongly — inside `features/teacher/economy/store-redemptions.md`, whose TIP actively instructed teachers to filter this tab by student name to settle disputes: the one control that errors, on the one tab that never holds an outcome. That section and TIP are rewritten in place, and the guide now points teachers at Purchase History. Same precedent as the roster bulk-actions row above: correct the guide that owns the surface rather than add a second one.

34. **Overtime is stored and never applied.** `PayrollSettings` carries `overtime_enabled`, `overtime_threshold`, `overtime_threshold_unit`, `overtime_threshold_period`, and `overtime_multiplier` (`app/models.py:1927,1939-1941`); the advanced form collects all five (`templates/admin_payroll.html:568-617`), the route parses them (`app/routes/admin.py:7714-7720`), and `upsert_payroll_settings` persists them. The pay calculation never reads any of them: `calculate_payroll_breakdown` (`app/payroll.py:166-170`) is `Decimal(total_seconds) * rate_per_second`, quantized to cents, with no threshold branch. A grep for `overtime` across `app/` returns only the model columns, the form parse, the settings-service field list, and `app/services/payroll/builders.py:198-245`, which formats `display_overtime_multiplier` for a summary panel. Same dead-setting shape as #19/#20/#22/#24/#27/#29 — but this one is a *promise about money*, so the guide tells teachers not to offer students an overtime rate.

35. **Rounding mode is stored and never applied.** `rounding_mode` (`app/models.py:1948`, default `'down'`) is collected at `templates/admin_payroll.html:679-690` with the hint *If time doesn't reach next increment*, parsed at `app/routes/admin.py:7746`, and read afterwards only by `app/services/payroll/builders.py:200,210,246` for display. Pay is computed from exact elapsed seconds and quantized to `0.01` regardless. Notably this makes the **Time Increment** dropdown (Per Second / Minute / Hour / Day) purely a data-entry unit — it is normalised to a per-minute rate at `app/routes/admin.py:7711` — rather than a billing granularity, which is what the rounding hint implies it is.

    Two display faults in the same panel, both wrong element IDs in `updateSettingsSummary()`: the rounding sentence reads `advRoundingMode` (`templates/admin_payroll.html:1133`) when the select is `advRounding` (`:682`), so it always prints *rounds down*; the overtime sentence reads `advOvertimeThresholdUnit` / `advOvertimeThresholdPeriod` (`:1156-1157`) when the selects are `advOvertimeUnit` / `advOvertimePeriod` (`:587,598`), so its guard never passes and the sentence never renders.

36. **Automatic payroll can never start.** `run_automatic_payroll_job` selects classes where `PayrollSettings.next_payroll_date` is non-NULL and due (`app/scheduled_tasks.py:372-373`), then advances the cursor by one frequency after firing (`:424`). That advance is the **only** write to the column anywhere in `app/` — saving payroll settings does not set it (neither `settings_data` dict at `app/routes/admin.py:7680-7698,7748-7767` includes it, though `_SUBMITTABLE_FIELDS` would accept it), and no FEAT or class-creation path sets it either. A class therefore sits at NULL forever and is never selected. `tests/test_automatic_payroll_job.py:61,128` arm the column by hand, which is why the job's own tests pass.

    Compounding this, the **Next Payroll** figure on the payroll page is *not* the scheduler cursor — it is `_compute_next_pay_date()` (`app/routes/admin.py:7326-7344`), derived on each page load from `first_pay_date` + `payroll_frequency_days` purely for display (`:7587` → `templates/admin_payroll.html:244-246`). So the page shows a confident upcoming payday for a run that will not happen.

    Two phantom controls in the page's own help accordion compound it further: *Auto run: When enabled, payroll runs on schedule without you clicking "Run Payroll"* (`templates/admin_payroll.html:107`) and *Attendance rules: Choose which tap types count (Start Work, Break, Done)* (`:113`). Neither control exists on the settings form.

    All three are documented in `features/teacher/economy/payroll-advanced-mode.md`; `payroll-settings.md` carries a short warning to run payroll manually.

37. **Editing an insurance policy leaves the edited version on sale.** An edit routes through `configure_insurance_definition` (`app/feats/class_configuration/feat_class_003_insurance_policy_management.py:376-424`), which validates and then calls `create_insurance_definition` (`app/services/insurance_definition_service.py:92-132`). That function does `db.session.add(row)` / `db.session.flush()` and nothing else — no predecessor is retired or hidden. The edit route passes `availability_state=row.availability_state` (`app/routes/admin.py:6209`), so an IN_USE policy yields a second IN_USE policy.

    Both rows are then listed to the teacher (`:6116`, filtered to `[IN_USE, HIDDEN]`) **and to students** (`app/routes/student.py:1424-1426`, filtered to `[IN_USE]`), and both are purchasable — `app/feats/purchase_insurance_feat.py:159` gates only on IN_USE. Contrast `app/feats/attendance.py:100`, where the same immutable-version pattern explicitly sets `predecessor.availability_state = 'RETIRED'` before inserting; the insurance path omits that step.

38. **A grouped insurance tier cannot be edited, and a hidden policy cannot be un-hidden.** Consequences of #37 rather than separate mechanisms, but both are user-visible dead ends.

    - *Grouped edit is refused.* `_enforce_tier_group_rules` (`feat_class_003_insurance_policy_management.py:306-345`) counts IN_USE rows in the group; since the original is still IN_USE, the new version collides on rank and raises `InsuranceContractViolation` (`:337-341`), surfaced as a `danger` flash on the re-rendered form (`app/routes/admin.py:6214-6216`). The rule's own docstring acknowledges it: *"the prior IN_USE tier at that rank must be retired first."* The partial unique index at `app/models.py:2422` is the DB backstop. Retiring first works, but retiring is permanent and the retired row is dropped from the list (`:6116`), so the practical path is retire-then-recreate rather than edit.
    - *No un-hide.* Grepping `availability_state=` across the routes yields only create→IN_USE (`:6157`), edit→inherit (`:6209`), hide→HIDDEN (`:6249`), retire→RETIRED (`:6277`). Nothing sets IN_USE on an existing row, and editing a HIDDEN policy inherits HIDDEN, so a hidden policy can only be brought back by building a new one.

    **No `insurance-versioning.md` was created.** `insurance-policies.md` owns the create/edit surface and was a 37-line v1 stub describing fields that do not exist ("coverage amounts", "maximum claims", an "Active Student Policies" tab), so it was rewritten in place to the real form — the three types and their conditional field sets, tier groups, the new-version contract, #37, and #38. **Do not create `insurance-versioning.md`.** Availability states, Hide vs Retire, and what they mean for policyholders stay in `insurance-enrollment.md`, which already covered them correctly.

    *Corrections made to `insurance-enrollment.md` at the same time:* it stated that coverage begins after the waiting period and that a new policyholder cannot claim on day one, and its closing TIP told teachers to settle disputes using purchase date plus waiting period. All three are wrong per defect #22 — coverage is effective at purchase and the claim path checks only that the incident does not predate it (`app/feats/insurance_claim_feat.py:295-298,437-441`). The guide also implied the waiting period is a general term when the form offers it for NON_MONETARY only (`templates/admin_edit_insurance_policy.html:110-115`). Rewritten, with pointers to `insurance-policies.md` for #37.

39. **A queued economy rebalance never activates.** Choosing **Next Payroll Run (Recommended)** routes to `queue_scheduled_policy_transitions` (`app/routes/admin.py:6846`), which writes a `PolicyTransition` in PENDING with an `effective_at`. The only code that ever activates such a transition is `activate_due_rebalances` (`app/utils/economy_rebalance.py:434-511`), and it is **never called** — a repo-wide grep finds one definition and one import (`app/routes/admin.py:103`), no call site in `app/`, `tests/`, or `app/scheduled_tasks.py`. The pending row therefore sits forever and rent never changes.

    The teacher is actively told otherwise. `templates/admin_economic_engine.html:164-169` renders an **Economy Update Scheduled** badge plus *Scheduled effective date: …* (fed by `get_pending_policy_transition_effective_at`, `app/routes/admin.py:2252`), and the radio is labelled *Next Payroll Run (Recommended)* — so the broken path is the one the UI recommends. The only thing that clears the badge is saving a policy mode, which calls `cancel_pending_policy_transitions` (`:6733`).

    Two smaller inconsistencies in the same path: the queue is written with `activation_mode=REBALANCE_ACTIVATION_NEXT_RENEWAL` (`:6852`) though the control says *Next Payroll Run*, and the success flash reads *"Scheduled economy rebalance for the renewal after the upcoming bill"* — a third description of the same timing. Independently of #39, the payroll boundary the label invokes does not arrive on its own either (defect #36).

40. **The rebalance preview can only ever contain rent.** `_build_rebalance_preview` (`app/routes/admin.py:2255-2286`) appends exactly one item type, `'rent'`, and its trailing comment records that insurance premium rebalancing was deliberately removed in the SPEC-ECON-003 migration. Fines and store items are never considered. The applier agrees: `_apply_change_list` (`app/utils/economy_rebalance.py:357-372`) branches only on `change_type == "rent"`, and `_domain_for_change` (`:72-77`) returns `None` for anything else, so a non-rent change would be silently dropped even if one were produced.

    Not a defect so much as an unfinished migration, but it is invisible from the UI: the page presents a general **Feature** column and a **Rebalance Preview** heading over what is structurally a single-setting control, while the surrounding cards recommend ranges for insurance, fines, and store tiers that the rebalance will never touch. Documented in `policy-mode-rebalancer.md` rather than left to be inferred from an empty table.

41. **A class Section is stored and editable but never displayed.** `section` is collected at creation (`templates/_class_setup_fields.html:19-20`, read at `app/routes/admin.py:9716`, persisted by `create_class`, `app/services/classroom_setup.py:91-122`) and is editable afterwards on Customizations (`app/routes/admin.py:3557-3559`). A repo-wide grep for `.section` across `templates/` returns exactly one hit — `admin_customizations.html:93`, the edit field itself. It is rendered nowhere else.

    That matters because the sidebar switcher identifies a class by `display_name or join_code` only (`app/__init__.py:833`, rendered at `templates/layout_admin.html:223`), and the fallback gate by `display_name (join_code)` (`admin_select_class_context.html:85`). Two sections of the same course are therefore indistinguishable in the one control used to move between them, while the create form's own label invites you to use Section for exactly that purpose. `class-setup.md` previously repeated that invitation ("Use it to tell periods apart") and has been corrected to send the distinction into the class name instead.

    **No `settings/class-switching.md` was created.** Class creation was already documented correctly in `features/teacher/classroom/class-setup.md` — the field table, the immutable time zone (confirmed: the `set_class_timezone` route is deleted, `app/routes/admin.py:3858-3860`), and landing in the new class on create (`:9761-9772`). Switching was the thin part, so that section was expanded in place with the three facts it omitted: the choice persists on the account rather than the session (`set_current_class` writes `last_active_class_id` *and* `last_active_seat_id`, `:3842-3848`), a failed switch surfaces an inline warning under the dropdown and changes nothing (`layout_admin.html:437-450`), and the **Select Your Class** gate is a benign fallback for an unresolvable pointer, not an error. A rename section was added, since name and section are mutable and the time zone is not. **Do not create `settings/class-switching.md`.**

42. **A support ticket's Title is required, discarded, and silently used for deduplication.** `title` is validated as mandatory (`app/routes/admin.py:9203-9204`) and then never persisted — `create_support_ticket` (`app/services/issue_service.py:7-21`) takes no title parameter, and the `Issue` model has no title column. The only thing `title` reaches is the FEAT idempotency key, `f"admin_help_support:{user_id}:{scope}:{title}"` (`admin.py:9231`), so two tickets sharing a title within one scope collapse into one submission.

    Meanwhile the My Tickets list template renders `report.title` (`templates/admin_support_tickets.html:97`), and the view model that feeds it hardcodes `'title': 'Support Ticket'` (`admin.py:9097`). Every ticket therefore displays under the same generic heading. Documented in `settings/support-tickets.md` with the practical remedy: put anything load-bearing in **What happened?**, whose first 220 characters *are* rendered, and vary the title to avoid the dedup collision.

43. **The support ticket status badge never matches its status.** The badge branches on `'new'` / `'reviewed'` / `'closed'` (`templates/admin_support_tickets.html:101`), but the canonical SPEC-TICK-001 statuses are uppercase — `OPEN`, `TEACHER_REVIEW`, `ESCALATED_TO_DEV`, `DEV_RESOLVED`, `TEACHER_FINAL_REVIEW`, `CLOSED` (`app/models.py:1718-1723`) — and the legacy values it *does* resemble are mapped away on read (`:1726-1731`). No branch ever matches, so every badge falls through to `bg-warning text-dark`: a closed ticket and a new one are the same colour. The label additionally renders `status|title`, which turns the underscored constant into *Escalated_To_Dev*.

    Minor, related, not separately numbered: support tickets are written with `class_public_id=selected_class_id` (`admin.py:9172`) — a `class_id`, not a `class_public_id`. `_support_report_views` looks the value up via `get_class_by_public_id` (`:9089-9093`), misses, and falls back to the active class's label, which happens to be correct because the form cannot file against any other class. Benign today; fragile if the scope choice is ever widened.

    **`features/teacher/settings/support-tickets.md` created** — the last teacher gap. Covers the binary class/account scope and why another class needs a Switch Class first, the opaque *We will know you as* identifiers, the five fields with their real limits, the double-submit guard, the 20-item class-filtered My Tickets list, and the six lifecycle statuses. Leads with the constraint that a student's problem must be initiated by the student (stated on the page itself at `admin_support_tickets.html:16`) and points at `classroom/student-issues.md`. Added to `settings/index.md` under a new **Help** heading.

44. **The hall pass verification link is never created until you press a button labelled as if it replaces one.** `generate_verify_token` has exactly one caller in the codebase — `rotate_teacher_hall_pass_verify_token` (`app/feats/attendance.py:116-125`), the FEAT behind **Regenerate QR**. Nothing mints a token on first use. So a teacher who has never pressed that button has no token, `verify_url` resolves to None (`app/routes/admin.py:6642-6644`), and the **Office Verification** button does not render at all. The comment immediately above, at `:6639`, reads *"Lazily generate the hall pass verification token if needed"* — the code does not do this. The feature is fully built and simply never armed, the same shape as #36 and #39.

    Documented as a workaround in the guide rather than hidden: *"If you only see **Regenerate QR**, you do not have a link yet. Select it once, confirm, and the **Office Verification** button appears."*

45. **The "QR" button produces no QR code.** The button reads *Regenerate QR* with tooltip *Regenerate Hall Pass QR* (`templates/admin_hall_pass.html:115-117`), but the `qrcode` library is imported and used only for TOTP enrollment (`app/routes/admin.py:19, 2924, 2965, 3312`). No QR image is generated for the verification link anywhere. What the button actually does is rotate a URL, which is then displayed as text to be copied. A teacher who presses it expecting something printable for the front desk gets a link.

46. **Verification times are shown to office staff as raw UTC ISO strings.** `time_out` and `return_time` are serialized with `.isoformat().replace('+00:00','Z')` (`app/routes/main.py:452,466`) and rendered unfiltered (`templates/hall_pass_verify.html:60,74`), producing `2026-09-04T14:32:11Z`. The audience for this page is front-office staff who are not CTH users, reading it under time pressure, and the value is both machine-formatted and in the wrong time zone. The **Currently Out (N minutes)** counter is the only readable time on the page; the guide tells staff to use it and ignore the rest.

    **`features/public/hall-pass-verification.md` created.** Written for two readers at once — the staff member using the form and the teacher who has to hand them the link. Covers obtaining the link, the three-field form, the three outcomes (match / *No hall pass record found for today.* / *Unable to uniquely verify.*), the three statuses, and revoking by rotating. States plainly that the page cannot leak a roster, which is the question a school office will actually ask.

---

## Carried Into Phase 3 and 4

**Phase 3 (rewrite) — ordered by user impact**
1. Fix the 8 orphaned docs first: delete or rewrite from scratch. They actively mislead.
2. Correct the stale nav paths and control names. Most are one-line fixes, but there are ~25 of them and they are the most visible errors.
3. Deepen the 12 thin docs against the pages they describe.
4. Fold in the Phase 1 metadata debt: 25 missing `description`, 8 missing `roles`.

**Phase 4 (new docs)** — 24 proposed new guides above: 12 teacher, 8 student, 4 public. The student hall-pass guide and the student-verified teacher recovery guide are the highest priority; both cover flows that are unusual, entirely undocumented, and hard to figure out unaided.

*Phase 4 progress (student), as of 2026-09-04:*

| Gap | Outcome |
|---|---|
| Hall pass workflow | ✅ `features/student/work/hall-passes.md` — new |
| Verify teacher recovery | ✅ `features/student/account/verify-teacher-recovery.md` — landed in Phase 3 |
| PIN vs passphrase | ✅ `features/student/account/pin-vs-passphrase.md` — new |
| Insurance tiers + cancellation | ✅ folded into `features/student/bills/insurance-coverage.md` (rewritten) |
| Productivity insurance claims | ✅ `features/student/bills/insurance-claims.md` — rewritten, both claim types |
| Done for the day | ✅ already in `features/student/work/start-end-work.md`; that guide also carried three claims the code disproves, now corrected — see note below |
| Rent late fees / waivers / history | ✅ already covered by `features/student/bills/rent-payments.md`; label and cross-link corrections applied |
| 12-month savings projection | ✅ `features/student/banking/savings-interest.md` — rewritten from 30 lines; surfaced defects #24 and #25 |

**All 8 student gaps are closed.** Teacher (11) and public (4) gaps are untouched.

*Corrections made to `savings-interest.md` (2026-09-04):* the previous version sent students to "the Savings section of your dashboard" for an **Interest Rate** shown as "e.g., 2% per week." Neither is true — the rate lives on the **Accounts** tab's **Statistics** card, is labelled **Monthly Interest Rate**, and is an annual rate divided by twelve; the app supports weekly and monthly *payout* frequencies but never expresses the rate per week. Its closing tip also told students to "transfer extra funds to savings before the scheduled payout day," which presumes a payout schedule that defect #24 shows does not run.

*Corrections made to `start-end-work.md` while folding in the hall-pass material (2026-09-04):* it listed **Restroom Queue** as a thing the Attendance card shows (it is defect #19's permanently hidden markup); it said picking a destination "requests a hall pass and stops your paid time" (requesting does neither — approval is required, and the clock only stops at **Leave**); and it blamed an empty destination list on the teacher not configuring destinations, when the list is always empty because of defect #12. All three came from reading the template's markup and labels rather than the JavaScript and API that drive them — the same failure mode as the `consume_pass` and `waiting_period_days` errors.

**Phase 5 (wiring)**
1. Re-point contextual help at feature guides; demote diagnostics to a secondary link.
2. Add help links to the 24 unwired pages, prioritizing account setup and recovery.
3. Remove the 4 dead map keys; add `interpretation`.
4. Promote `diagnostics/teacher/rent-itemization.md` (476 lines) and `diagnostics/teacher/analytics.md` (384 lines) into the index nav — currently reachable only via `diagnostics/teacher.md`.
5. Build `docs/self-hosting/`. (Sysadmin relocation is done — see the Sysadmin Scope Decision above.)
