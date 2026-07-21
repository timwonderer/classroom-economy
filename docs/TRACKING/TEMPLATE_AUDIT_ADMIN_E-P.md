# Admin Template & Route Audit (E–P)

**Last Updated:** 2026-07-19  
**Scope:** Admin templates E–P (economy health, insurance, items, settings, payroll, etc.)  
**Total Templates Audited:** 16  

---

## Executive Summary

### ⚠️ Critical Issues Found

| Issue | Count | Status |
|-------|-------|--------|
| Orphan templates (no route) | 4 | Mark for deletion |
| Routes with abort(404) | 4 | Never render templates |
| Unused navigation partial | 1 | Mark for deletion |

### Issue Details

#### Orphan Templates / Not Rendered
- `admin_help_support.html` — Route renders `admin_support_tickets.html` instead
- `admin_nav.html` — Standalone nav partial, never included anywhere
- `admin_insurance.html` — Route aborts(404) before rendering
- `admin_edit_insurance_policy.html` — Route aborts(404) before rendering

#### Routes That Abort(404)
- `admin.insurance_management` — Aborts before rendering `admin_insurance.html`
- `admin.edit_insurance_policy` — Aborts before rendering `admin_edit_insurance_policy.html`
- `student.student_insurance` — Aborts(404) currently
- `student.file_claim` — Aborts(404) currently

---

## Template Audit by Page

### admin_economy_health.html
**Extends:** `layout_admin.html`  
**Route(s):** `admin.economy_health` — GET `/admin/economy-health` — [app/routes/admin.py:7209](app/routes/admin.py#L7209)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|----------|
| current_page | str ("economy_health") | Nav highlight |
| blocks | list | Available class blocks |
| selected_block | str | Currently selected block |
| payroll_settings | PayrollSettings or None | Payroll config for selected block |
| has_payroll_settings | bool | Whether payroll is configured |
| cwi_calc | object or None | CWI calculation result (.cwi, .notes) |
| expected_hours | float | Expected weekly hours |
| pay_rate_per_minute | float or None | Pay rate per minute |
| rent_settings | RentSettings or None | Rent configuration |
| insurance_count | int | Number of insurance policies |
| store_item_count | int | Number of store items |
| fine_count | int | Number of fines |
| banking_settings | BankingSettings or None | Banking config |
| banking_summary | dict | Banking health summary (.level, .message, .apy, .payout) |
| analysis | object or None | Economy analysis result |
| warnings_by_level | dict | Warnings keyed by critical/warning/info |
| warnings_by_feature | dict | Warnings keyed by feature |
| actionable_warning_count | int | Count of actionable warnings |
| health_warning_summary | list of dicts | Summary rows (.label, .count, .link_href, .link_label) |
| recommendations | dict or None | Pricing recommendations (.rent, .insurance_premium_weekly, .fine, .store_tiers, .min_weekly_savings) |
| snapshot | object | Balance snapshot |
| analysis_schedule | object | Analysis schedule |
| policy_modes | dict | Policy mode definitions (.label, .summary, .description) |
| policy_summary | dict | Current policy state (.mode, .overall_status, .updated_at, .categories, .has_pending_policy_transition, .profile) |
| pending_rebalance_effective_at | datetime or None | Scheduled rebalance date |
| rebalance_preview | list of dicts | Preview items (.key, .label, .current, .recommended, .apply_by_default) |
| show_rebalance_review | bool | Whether to show rebalance review form |
| feature_links | dict | Feature name to URL mapping |
| payroll_link | str | URL to payroll page |
| banking_link | str | URL to banking page |
| rent_link | str | URL to rent settings |
| insurance_link | str | URL to insurance management |
| store_link | str | URL to store management |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|  
| 2 | `{% import "macros/help.html" as help %}` | Macro file | Template filesystem |
| 107 | `{{ help.help_icon(...) }}` | help macro | [MACRO:help] |
| 109 | `{{ selected_block or "N/A" }}` | str or None | Route var |
| 117 | `{{ payroll_link }}` | str URL | Route var |
| 131 | `{{ policy_summary.overall_status }}` | str | Route var |
| 139 | `{{ policy_summary.updated_at.strftime(...) }}` | datetime | Route var |
| 145 | `{{ csrf_token() }}` | token | [FLASK] |
| 146 | `{% for mode_key, mode in policy_modes.items() %}` | dict | Route var |
| 148 | `{{ policy_summary.mode }}` | str | Route var |
| 150 | `{{ mode_key }} / {{ mode.label }} / {{ mode.summary }} / {{ mode.description }}` | str | Loop var |
| 161 | `{{ url_for('admin.economy_health', review_rebalance=1) }}` | URL | [FLASK] |
| 163 | `{{ policy_summary.has_pending_policy_transition }}` | bool | Route var |
| 167 | `{{ pending_rebalance_effective_at.strftime(...) }}` | datetime | Route var |
| 176 | `{% for category in policy_summary.categories %}` | list of dicts | Route var |
| 179-189 | `{{ category.label }}, {{ category.status }}, {{ category.warning_count }}` | str/int | Loop var |
| 197 | `{{ url_for('admin.apply_economy_rebalance') }}` | URL | [FLASK] |
| 202 | `{{ policy_summary.profile.label }}` | str | Route var |
| 216 | `{% for item in rebalance_preview %}` | list of dicts | Route var |
| 218-221 | `{{ item.key }}, {{ item.apply_by_default }}, {{ item.label }}, {{ item.current }}, {{ item.recommended }}` | various | Loop var |
| 251 | `{{ url_for('admin.economy_health') }}` | URL | [FLASK] |
| 281 | `{{ cwi_calc.cwi }}` | float | Route var |
| 288-289 | `{{ pay_rate_per_minute }}` | float | Route var |
| 295 | `{{ url_for('admin.update_expected_weekly_hours') }}` | URL | [FLASK] |
| 296 | `{{ csrf_token() }}` | token | [FLASK] |
| 298 | `{{ expected_hours }}` | float | Route var |
| 312 | `{% for note in cwi_calc.notes %}` | list of str | Route var |
| 332-338 | `{{ analysis }}, {{ actionable_warning_count }}, {{ banking_summary.level }}` | various | Route vars |
| 345-351 | `{{ warnings_by_level['critical']\|length }}, etc.` | list | Route var |
| 365 | `{% for row in health_warning_summary %}` | list of dicts | Route var |
| 367-371 | `{{ row.label }}, {{ row.count }}, {{ row.link_href }}, {{ row.link_label }}` | various | Loop var |
| 383 | `{{ banking_summary.message }}` | str | Route var |
| 383 | `{{ banking_link }}` | str | Route var |
| 398-409 | `{{ banking_summary.level }}, {{ banking_summary.message }}, {{ banking_summary.apy }}, {{ banking_summary.payout }}` | various | Route var |
| 419-428 | `{{ recommendations.rent.min }}, .max, .recommended, {{ recommendations.insurance_premium_weekly.min }}, .max, {{ recommendations.fine.min }}, .max, {{ recommendations.store_tiers.basic.min }}, .max, {{ recommendations.min_weekly_savings }}` | float | Route var |
| 426-429 | `{{ payroll_link }}, {{ rent_link }}, {{ insurance_link }}, {{ store_link }}` | str URLs | Route vars |
| 447-468 | `{% for level in [...] %}, {{ severity_map[level] }}, {% for warning in bucket %}, {{ warning.feature }}, {{ warning.message }}, {% for prefix, destination in feature_links.items() %}` | various | Route vars |
admin_edit_insurance_policy.html
**Extends:** `layout_admin.html`  
**Route(s):** `admin.edit_insurance_policy` — GET|POST `/admin/insurance/edit/<int:policy_id>` — ⚠️ **Currently aborts(404)**

**Variables from route (expected by template, not currently supplied):**

| Variable | Type | Purpose |
|----------|------|----------|
| policy | InsurancePolicy model | Policy being edited (.title, .is_active, .id, .student_policies, .claims, .created_at, .bundle_with_policy_ids, .collective_goal_type, .bulk_discount_enabled) |
| form | FlaskForm | WTForms insurance policy form with many fields |
| available_policies | list | Other active policies for bundle selection |
| tier_groups | list of dicts | Existing tier groups (.id, .name, .color, .policies) |
| payroll_settings | PayrollSettings or None | For CWI calculations |
| insurance_recommendation | dict or None | CWI-based premium recommendations (.frequency, .min, .max, .recommended, .cwi) |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|  
| 8-9 | `{{ static_url('js/economy-balance.js') }}, {{ static_url('js/insurance-badge-select.js') }}` | str | [CTX:static_url] |
| 32 | `{{ url_for('admin.insurance_management') }}` | URL | [FLASK] |
| 33 | `{{ policy.title }}` | str | Route var |
| 39 | `{{ url_for('admin.edit_insurance_policy', policy_id=policy.id) }}` | URL | [FLASK] + route var |
| 40 | `{{ form.hidden_tag() }}` | HTML | [FLASK] |
| 54-96 | `{{ form.title(...) }}, {{ form.premium(...) }}, {{ form.description(...) }}, {{ form.marketing_badge(...) }}, {{ form.claim_type(...) }}, etc.` | WTForm fields | Route var form |
| 263-278 | `{% for avail_policy in available_policies %}, {{ avail_policy.id }}, {{ avail_policy.title }}, {{ avail_policy.premium }}` | model objects | Route var |
| 325-431 | Tier grouping: `{{ form.tier_category_id.data }}, {{ form.tier_name.data }}, {% for group in tier_groups %}, {{ group.id }}, {{ group.name }}, {{ group.color }}, {% for policy_info in group.policies %}, {{ policy_info.title }}, {{ policy_info.level }}` | various | Route vars |
| 449-466 | `{{ policy.is_active }}` for status card styling | bool | Route var |
| 480 | `{{ policy.student_policies.filter_by(status='active').count() }}` | int | Route var (lazy query) |
| 489 | `{{ policy.claims.count() }}` | int | Route var (lazy query) |
| 498 | `{{ policy.created_at.strftime(...) }}` | datetime | Route var |
| 514 | `{% if insurance_recommendation %}...{{ insurance_recommendation.frequency }}...{{ insurance_recommendation.min }}...{{ insurance_recommendation.max }}...{{ insurance_recommendation.recommended }}...{{ insurance_recommendation.cwi }}` | dict | Route var |
| 531 | `{{ form.submit(...) }}` | WTForm field | Route var |
| 532 | `{{ url_for('admin.insurance_management') }}` | URL | [FLASK] |
| 571 | `{{ (payroll_settings.expected_weekly_hours ...) \| float }}` | float | Route var |
| 828-829 | `window.renderBadgeLikeSelect(...)` | JS function | insurance-badge-select.js |

---

### admin_edit_item.html

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| form | FlaskForm | Store item edit form |
| item | StoreItem | Item being edited (.name, .id, .item_type, .is_bundle, .bulk_discount_enabled) |
| current_page | str | Nav highlight ("store") |
| payroll_settings | PayrollSettings / None | For CWI economy balance check |
| selected_feature_scope | dict | Feature scope context |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 3 | `{{ item.name }}` in title block | str | Route var |
| 8-9 | `{{ static_url('js/economy-balance.js') }}` | str | [CTX:static_url] |
| 27 | `{{ item.name }}` | str | Route var |
| 30 | `{{ url_for('admin.edit_store_item', item_id=item.id) }}` | URL | [FLASK] + route var |
| 126 | `{% if item.item_type == 'collective' %}` | str | Route var |
| 177 | `{% if item.is_bundle %}` | bool | Route var |
| 205 | `{% if item.bulk_discount_enabled %}` | bool | Route var |

---

### admin_feature_disabled.html
**Extends:** `layout_admin.html`  
**Route(s):** Before-request handler — Rendered inline when feature disabled — [app/routes/admin.py:526](app/routes/admin.py#L526)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| current_page | str | Nav highlight ("feature_disabled") |
| feature_name | str | Internal feature name |
| feature_label | str | Display-friendly feature name |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 9 | `{{ feature_label }}` | str | Route var |
| 11 | `{{ url_for('admin.feature_settings') }}` | URL | [FLASK] |

---

### admin_feature_settings.html
**Extends:** `layout_admin.html`  
**Route(s):** `admin.feature_settings` — GET|POST `/admin/feature-settings` — [app/routes/admin.py:9795](app/routes/admin.py#L9795)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| current_page | str | Nav highlight ("feature_settings") |
| periods | list | All configured periods/blocks |
| period_settings | dict | Period → feature settings mapping |
| features_list | list[tuple] | (feature_id, feature_name, feature_icon, feature_desc) |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 16 | `{% if periods %}` | list | Route var |
| 38 | `{% for feature_id, feature_name, ... in features_list %}` | tuple | Route var |
| 92-114 | `{% for period in periods %}` with settings loop | dict | Route vars |
| 125 | `{{ period_settings \| tojson \| safe }}` | dict as JSON | Route var |

---

### admin_hall_pass.html
**Extends:** `layout_admin.html`  
**Route(s):** `admin.hall_pass` — GET `/admin/hall-pass` — [app/routes/admin.py:6896](app/routes/admin.py#L6896)
**PROD status:** REWIRED — Resolved 2026-07-21. Issued-pass and out-of-class read models are derived from canonical `hall_pass_logs` plus `attendance_sessions`. Pending hall-pass requests are operational, process-local workflow state; reject/cancel discards the request without a PROD write, while approve commits by calling `FEAT-PROD-002`, writing `hall_pass_logs`, and consuming entitlement.

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| pending_requests | list | Ephemeral pending hall-pass requests from operational queue |
| issued_passes | list[HallPassLog] | Issued passes waiting for leave |
| out_of_class | list[HallPassLog] | Students currently out |
| current_page | str | Nav highlight ("hall_pass") |
| verify_url | str / None | Hall pass verification URL |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 108-111 | `{% if verify_url %}, {{ verify_url }}` | str or None | Route var |
| 166-207 | `pending_requests` tab and rows | pending request rows | REWIRED — route reads process-local operational pending queue; Approve calls `/api/hall-pass/request/<request_id>/approve` and commits through `FEAT-PROD-002`; Reject calls `/api/hall-pass/request/<request_id>/reject` and performs no PROD write |
| 166-176 | `{{ issued_passes\|length }}`, `{{ out_of_class\|length }}` | int | Route vars |
| 203-262 | Loop: `{{ req.student_name }}, {{ req.reason }}` | route display row attrs | Resolved 2026-07-21: GET route builds display rows from `HallPassLog` + `IdentityProfile`; reachable leave/return buttons call `FEAT-PROD-001` attendance writes |

---

### ❌ admin_help_support.html
**Status:** ORPHAN — **Mark for deletion**  
**Route(s):** Route renders `admin_support_tickets.html` instead  
**Note:** Legacy/unused template

---

### ❌ admin_insurance.html
**Status:** ⚠️ **ABORTED ROUTE** — Route renders `abort(404)`, never renders this template  
**Extends:** `layout_admin.html`  
**Route(s):** `admin.insurance_management` — GET|POST `/admin/insurance` — [app/routes/admin.py](app/routes/admin.py)  
**Action:** Delete this orphan template or fix the route handler

---

### admin_issues_queue.html
**Extends:** `layout_admin.html`  
**Route(s):** `admin.issues_queue` — GET `/admin/issues` — [app/routes/admin.py:11023](app/routes/admin.py#L11023)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| current_page | str | Nav highlight ("issues") |
| pending_issues | list[Issue] | Open/teacher_review issues |
| resolved_issues | list[Issue] | Final review / dev resolved issues |
| escalated_issues | list[Issue] | Escalated issues |
| format_utc_iso | function | Timestamp formatting |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 116 | `{{ pending_issues\|length }}` | int | Route var |
| 179 | `{{ url_for('admin.view_issue', issue_ref=...) }}` | URL | [FLASK] + route var |
| 185-207 | Loop: `{{ issue.student_display_name }}, {{ issue.status }}` | Issue attrs | Loop var |

---

### admin_login.html
**Extends:** None (standalone HTML)  
**Route(s):** `admin.login` — GET|POST `/admin/login` — [app/routes/admin.py:2876](app/routes/admin.py#L2876)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| form | AdminLoginForm | Login form (username, totp_code, submit) |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 8 | `{{ csrf_token() }}` | token | [FLASK] |
| 158 | `{{ form.hidden_tag() }}` | HTML | [FLASK] |
| 161-162 | `{{ form.username(...) }}` | WTForm field | Route var |
| 178 | `{{ form.submit(...) }}` | WTForm field | Route var |

---

### ❌ admin_nav.html
**Status:** ORPHAN — **Mark for deletion**  
**Type:** Standalone nav partial (never included)  
**Note:** Navigation component with no parent template including it

---

### admin_passkey_settings.html
**Extends:** `layout_admin.html`  
**Route(s):** `admin.passkey_settings` — GET `/admin/passkey/settings` — [app/routes/admin.py:10958](app/routes/admin.py#L10958)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| admin | User | Current admin user |
| credentials | list | Registered passkey credentials (.authenticator_name, .created_at, .last_used, .id) |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 50 | `{% if credentials %}` | list | Route var |
| 52 | `{% for cred in credentials %}` | list | Route var |
| 57 | `{{ cred.authenticator_name or "Unnamed" }}` | str or None | Loop var |
| 101 | `{{ static_url('js/passkey.js') }}` | str | [CTX:static_url] |

---

### admin_payroll.html (1971 lines)
**Extends:** `layout_admin.html`  
**Route(s):** `admin.payroll` — GET `/admin/payroll` — [app/routes/admin.py:7705](app/routes/admin.py#L7705)

**Variables from route (key selections):**

| Variable | Type | Purpose |
|----------|------|---------|
| recent_payrolls | list[dict] | Recent payroll transactions |
| next_payroll_by_block | list[dict] | Per-block next payroll info |
| total_payroll_estimate | float | Total estimated payout |
| all_students | list | All students |
| payroll_history | list[dict] | Historical payroll entries |
| blocks | list | All available blocks |
| current_page | str | Nav highlight ("payroll") |

**Jinja expressions (representative, complex template):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 14 | `{{ static_url('js/economy-balance.js') }}` | str | [CTX:static_url] |
| 246-257 | Loop: `{{ block_info.class_label }}, {{ block_info.estimate }}` | dict attrs | Loop var |
| 975-1003 | Loop: `{{ student.full_name }}, {{ student.public_id }}` | model attrs | Loop var |
| 1667 | `{{ url_for("admin.run_payroll") }}` | URL | [FLASK] |

---

### admin_payroll_history.html
**Extends:** `layout_admin.html`  
**Route(s):** `admin.payroll_history` — GET `/admin/payroll-history` — [app/routes/admin.py:7293](app/routes/admin.py#L7293)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| payroll_history | list[dict] | Payroll records (.timestamp, .class_label, .student, .amount) |
| current_page | str | Nav highlight ("payroll_history") |
| selected_class_id | str (UUID) | Active class ID |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 12 | `{{ selected_class_id }}` | str | Route var |
| 40 | `{% for entry in payroll_history %}` | list[dict] | Route var |
| 44 | `{{ format_utc_iso(entry.timestamp) }}` | str | [GLOBAL] + loop var |

---

### ❌ admin_process_claim.html
**Status:** ⚠️ **ABORTED ROUTE** — Route renders `abort(404)`, never renders this template  
**Extends:** `layout_admin.html`  
**Route(s):** `admin.process_claim` — GET|POST `/admin/insurance/claim/<int:claim_id>` — [app/routes/admin.py](app/routes/admin.py)  
**Action:** Delete this orphan template or fix the route handler
