# System Admin and Shared Template & Route Audit

**Last Updated:** 2026-07-21
**Scope:** System admin templates (sysadmin blueprint) + error pages + public pages  
**Total Templates Audited:** 38  

---

## Executive Summary

### ⚠️ Critical Issues Found

| Issue | Count | Status |
|-------|-------|--------|
| Orphan templates (no route) | 1 | Mark for deletion |
| Variable name mismatches | 1 | Fix in progress |
| Inline DB queries in templates | 1 | Refactor needed |

### Issue Details

#### Orphan Templates
- `system_admin_username_migration.html` — No route renders; marked for deletion
- `hall_pass_verification.html` — Removed 2026-07-21 after public verification rewired to `hall_pass_verify.html`

#### Variable Name Mismatches
- `system_admin_dashboard.html` **LINE 17:** Template uses `{{ total_teachers }}` but route passes `total_admins`
- `system_admin_dashboard.html` **LINE 116:** Template uses `{% if recent_teachers %}` but route passes `recent_admins`

#### Anti-Pattern: Inline Query
- `sysadmin_user_report_detail.html` **LINE 182:** Direct DB query in template: `{% set user_reports = report.__class__.query.filter_by(anonymous_code=report.anonymous_code).all() %}`
  - **Fix:** Move query logic to route handler

---

## Template Audit by Page

### system_admin_login.html
**Extends:** None (standalone HTML document)  
**Route(s):** `sysadmin.login` — GET|POST `/sysadmin/login` — [app/routes/system_admin.py:250](app/routes/system_admin.py#L250)
**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| form | SystemAdminLoginForm | WTForms login form with username, totp_code, submit, hidden_tag() |

**Jinja expressions:**

Line	Expression	Expects	Supplied By
8	{{ csrf_token() }}	str	[FLASK]
16	{{ static_url('css/tokens.css') }}	str	[GLOBAL]
17	{{ static_url('css/style.css') }}	str	[GLOBAL]
159	get_flashed_messages(with_categories=true)	list[tuple]	[FLASK]
171	{% if form %}	truthy check	route
173	{{ form.hidden_tag() }}	Markup	route (form)
176	{{ form.username(...) }}	Markup	route (form)
182	{{ form.totp_code(...) }}	Markup	route (form)
186	{% if turnstile_site_key %}	str/None	[CTX:global_settings]
188	{{ turnstile_site_key }}	str	[CTX:global_settings]
193	{{ form.submit(...) }}	Markup	route (form)
204	{{ url_for('student.login') }}	str	[FLASK]
212	{{ url_for('main.privacy') }}	str	[FLASK]
214	{{ url_for('main.district') }}	str	[FLASK]
216	{{ url_for('main.terms') }}	str	[FLASK]
220	{{ static_url('images/logo_sysadmin_transparent_512.png') }}	str	[GLOBAL]
228	{{ static_url('js/passkey.js') }}	str	[GLOBAL]
234	{{ url_for("sysadmin.passkey_auth_start") }}	str	[FLASK]
235	{{ url_for("sysadmin.passkey_auth_finish") }}	str	[FLASK]


---

### system_admin_dashboard.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.dashboard` — GET|POST `/sysadmin/dashboard` — [app/routes/system_admin.py:567](app/routes/system_admin.py#L567)  
**Status:** ⚠️ **VARIABLE NAME MISMATCHES** (Lines 17, 116)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| total_admins | int | Count of teacher Users |
| total_students | int | Count of student Seats |
| active_invites | int | Active admin invite codes |
| system_admin_count | int | Count of sysadmin Users |
| open_tickets | int | Open reports + escalated issues |
| recent_admins | list[User] | Last 5 registered teachers |
| recent_errors | list[RowMapping] | Last 5 error log entries |
| system_admins | list[User] | All sysadmin Users |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By | Notes |
|------|-----------|---------|-------------|-------|
| 17 | `{{ total_teachers }}` | int | **❌ MISMATCH** route passes `total_admins` | **FIX:** Change template to `{{ total_admins }}` |
| 116 | `{% if recent_teachers %}` | list | **❌ MISMATCH** route passes `recent_admins` | **FIX:** Change template to `{% if recent_admins %}` |

---

### system_admin_manage_admins.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.manage_admins` — GET `/sysadmin/admins` — [app/routes/system_admin.py:863](app/routes/system_admin.py#L863)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| admins | list[dict] | Teacher data dicts with id, username, student_count, created_at, last_login |
| current_page | str | "sysadmin_admins" |

---

### system_admin_manage_teachers.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.manage_teachers` — GET|POST `/sysadmin/manage-teachers` — [app/routes/system_admin.py:980](app/routes/system_admin.py#L980)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| form | SystemAdminInviteForm | Invite code creation form |
| active_invites | list | Active invite code objects |
| expired_invites | list | Expired invite code objects |
| used_invites | list | Used invite code objects |
| teachers | list[dict] | Teacher data dicts |
| inactivity_threshold_days | int | Days threshold for inactivity |

---

### system_admin_teacher_overview.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.teacher_overview` — GET `/sysadmin/teacher-overview` — [app/routes/system_admin.py:1079](app/routes/system_admin.py#L1079)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| teachers | list[dict] | Teacher data dicts |
| current_page | str | "teacher_overview" |
| inactivity_threshold_days | int | Days threshold for inactivity badge |

---

### system_admin_logs.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.logs` — GET `/sysadmin/logs` — [app/routes/system_admin.py:690](app/routes/system_admin.py#L690)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| logs | list[dict] | Structured log entries |
| current_page | str | "sysadmin_logs" |

---

### system_admin_logs_testing.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.logs_testing` — GET `/sysadmin/logs-testing` — [app/routes/system_admin.py:760](app/routes/system_admin.py#L760)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| recent_errors | list | Recent error log objects (empty in current impl) |
| logs_url | str | URL to sysadmin.logs |
| current_page | str | "sysadmin_logs_testing" |

---

### system_admin_error_logs.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.error_logs` — GET `/sysadmin/error-logs` — [app/routes/system_admin.py:733](app/routes/system_admin.py#L733)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| error_logs | list | Error log data (empty in current impl) |
| pagination | object/None | Pagination object |
| error_types | list | Distinct error type strings |
| current_error_type | str | Active filter value |
| current_page | str | "sysadmin_error_logs" |

---

### system_admin_network_activity.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.network_activity` — GET `/sysadmin/network-activity` — [app/routes/system_admin.py:781](app/routes/system_admin.py#L781)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| network_logs | list | Network activity log entries |
| pagination | object/None | Pagination object |
| ip_addresses | list | Distinct IP addresses for filter |
| current_ip | str | Active IP filter value |
| total_requests | int | Total request count |
| unique_ips | int | Unique IP count |
| error_type_stats | list | Error type/count tuples |
| current_page | str | "network_activity" |

---

### system_admin_passkey_settings.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.passkey_settings` — GET `/sysadmin/passkey/settings` — [app/routes/system_admin.py:550](app/routes/system_admin.py#L550)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| admin | User | Current sysadmin User object |
| credentials | list | Passkey credential objects |

---

### ❌ system_admin_username_migration.html
**Status:** ORPHAN — **Mark for deletion**  
**Route(s):** No route renders this template  
**Note:** See TEMPLATE_INTERFACE_AUDIT_2026-07-19.md for deletion tracking

---

### sysadmin_announcements.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.announcements` — GET `/sysadmin/announcements` — [app/routes/system_admin.py:1609](app/routes/system_admin.py#L1609)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| announcements | list[Announcement] | System admin announcements |

---

### sysadmin_announcement_form.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):**
- `sysadmin.announcement_create` — GET|POST `/sysadmin/announcements/create` — [app/routes/system_admin.py:1642](app/routes/system_admin.py#L1642)
- `sysadmin.announcement_edit` — GET|POST `/sysadmin/announcements/edit/<int:announcement_id>` — [app/routes/system_admin.py:1691](app/routes/system_admin.py#L1691)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| form | SystemAdminAnnouncementForm | WTForms announcement form |
| action | str | "Create" or "Edit" |
| announcement | Announcement/None | Existing announcement (edit only) |

---

### sysadmin_combined_logs.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.combined_logs` — GET `/sysadmin/combined-logs` — [app/routes/system_admin.py:633](app/routes/system_admin.py#L633)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| current_page | str | "logs" |
| active_tab | str | "errors" or "network" |
| error_logs | list | Paginated error log entries |
| error_pagination | object/None | Pagination for error tab |
| network_logs | list | Paginated network log entries |
| net_pagination | object/None | Pagination for network tab |

---

### sysadmin_escalated_issues.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.escalated_issues` — GET `/sysadmin/issues` — [app/routes/system_admin.py:1803](app/routes/system_admin.py#L1803)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| pending_issues | list[Issue] | Issues in ESCALATED_TO_DEV/elevated status |
| in_review_issues | list[Issue] | Issues in developer_review status |
| resolved_issues | list[Issue] | Issues in DEV_RESOLVED/developer_resolved status |

---

### sysadmin_view_escalated_issue.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.view_escalated_issue` — GET `/sysadmin/issues/<issue_ref>` — [app/routes/system_admin.py:1836](app/routes/system_admin.py#L1836)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| issue | Issue | The escalated Issue object |
| issue_ref | str | Opaque reference string |
| correlation_pack | object/None | Issue.correlation_pack property |
| history | list[IssueStatusHistory] | Status change history entries |

---

### sysadmin_support_tickets.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.support_tickets` — GET `/sysadmin/support` — [app/routes/system_admin.py:1171](app/routes/system_admin.py#L1171)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| current_page | str | "support_tickets" |
| active_tab | str | "reports" or "issues" |
| reports | list[SimpleNamespace] | Teacher-submitted issues |
| issues_pending | list[Issue] | Pending escalated issues |
| issues_in_review | list[Issue] | In-review escalated issues |
| issues_resolved | list[Issue] | Resolved escalated issues |

---

### sysadmin_user_reports.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.user_reports` — GET `/sysadmin/user-reports` — [app/routes/system_admin.py:1250](app/routes/system_admin.py#L1250)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| reports | list[SimpleNamespace] | Issue data |
| new_count | int | Count of new reports |
| reviewed_count | int | Count of reviewed reports |
| closed_count | int | Count of closed reports |

---

### ⚠️ sysadmin_user_report_detail.html
**Extends:** `layout_system_admin.html` ([LAYOUT:sysadmin])  
**Route(s):** `sysadmin.view_user_report` — GET `/sysadmin/user-reports/<report_ref>` — [app/routes/system_admin.py:1305](app/routes/system_admin.py#L1305)  
**Status:** ANTI-PATTERN DETECTED

**Issues:**
- **LINE 182:** Direct database query in Jinja template:
  ```jinja
  {% set user_reports = report.__class__.query.filter_by(anonymous_code=report.anonymous_code).all() %}
  ```
  - **Fix:** Move this logic to the route handler and pass `related_reports` variable

---

## Error Pages

### error_400.html
**Route(s):** Used as static error page (nginx or custom error handler)

---

### error_401.html
**Route(s):** Static error page

---

### error_403.html
**Route(s):** Static error page

---

### error_404.html
**Route(s):** Static error page

---

### error_500.html
**Route(s):** Global exception handler — [app/__init__.py:151](app/__init__.py#L151)

---

### error_503.html
**Route(s):** Static error page

---

### maintenance.html
**Route(s):** `show_maintenance_page` (before_request hook) — [app/__init__.py:454](app/__init__.py#L454)

---

## Public Pages

### offline.html
**Route(s):** `main.offline` — GET `/offline` — [app/routes/main.py:183](app/routes/main.py#L183)

---

### privacy.html
**Route(s):** `main.privacy` — GET `/privacy` — [app/routes/main.py:162](app/routes/main.py#L162)

---

### tos.html
**Route(s):** `main.terms` — GET `/terms` — [app/routes/main.py:169](app/routes/main.py#L169)

---

### district.html
**Route(s):** `main.district` — GET `/district` — [app/routes/main.py:175](app/routes/main.py#L175)

---

## Hall Pass Pages

### hall_pass_setup.html
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.hall_pass_setup` — GET `/admin/hall-pass/setup` — [app/routes/admin.py:6911](app/routes/admin.py#L6911)

---

### ❌ hall_pass_verification.html
**Status:** REMOVED — deleted 2026-07-21 after public verification rewired to `hall_pass_verify.html`
**Route(s):** No route renders this template  
**Note:** Deprecated legacy public history page collapsed into `hall_pass_verify.html` plus token-scoped API read model

---

### hall_pass_verify.html
**Extends:** None (standalone HTML document)  
**Route(s):** `main.verify_hall_pass` — GET|POST `/verify/hallpass/<teacher_public_token>` — [app/routes/main.py:222](app/routes/main.py#L222)

**Checklist Status:** `REWIRED_READ`

**Template contract:**

| Surface | Jinja / Form Contract | Current v2 Interface | Status |
|---|---|---|---|
| Class dropdown | `{% for cls in classes %}` with `<option value="{{ cls.class_id }}">{{ cls.label }}</option>` | Route resolves teacher by public `User.hall_pass_verify_token`, lists that teacher's `ClassEconomy` rows, and exposes display label from `section` + class display name while submitting backend `class_id` | `VALID` |
| Student query | `first_name`, `last_name`, `class_id` POST fields | Route validates selected `class_id` under the teacher user boundary and matches against `Seat.claim_first_name_hash` + `Seat.claim_last_name_hash` | `VALID` |
| Result display | `result.student_display`, `class_label`, `destination`, `time_out`, `status`, `elapsed_mins`, `return_time` | Route reads current-day `hall_pass_logs`, derives left/returned state from `attendance_sessions` using the canonical temporal resolver, and uses `IdentityProfile` only after a unique match for display metadata | `VALID` |
| Public capability | URL token in `/verify/hallpass/<teacher_public_token>` | Token is a public capability stored on teacher `User`; no live actor `CanonicalContext` is required for this read-only public surface | `VALID` |

---

## Components

### components/getting_started_widget.html
**Type:** Included partial (not standalone page)  
**Included in:** `layout_admin.html` (line 575)  
**Context:** Inherits variables from including template

---

## Documentation Pages

### docs/index.html
**Extends:** `base.html` ([LAYOUT:base])  
**Route(s):** `docs.index` — GET `/docs/` — [app/routes/docs.py:411](app/routes/docs.py#L411)

---

### docs/search.html
**Extends:** `base.html` ([LAYOUT:base])  
**Route(s):** `docs.search` — GET `/docs/search` — [app/routes/docs.py:657](app/routes/docs.py#L657)

---

### docs/timeline.html
**Extends:** `base.html` ([LAYOUT:base])  
**Route(s):** `docs.timeline` — GET `/docs/timeline` — [app/routes/docs.py:422](app/routes/docs.py#L422)

---

### docs/view.html
**Extends:** `base.html` ([LAYOUT:base])  
**Route(s):** `docs.view_doc` — GET `/docs/<path:doc_path>` — [app/routes/docs.py:430](app/routes/docs.py#L430)
