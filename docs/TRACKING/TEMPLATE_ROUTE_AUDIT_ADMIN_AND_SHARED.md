# Teacher/Admin Template & Route Audit

**Last Updated:** 2026-07-20  
**Scope:** Admin teacher-facing templates under `templates/` in `classroom-economy`  
**Total Templates Audited:** 19  

---

## Executive Summary

### ⚠️ Issues Found

| Issue | Count | Status |
|-------|-------|--------|
| Orphan templates / dead routes | 4 | Mark for deletion or cleanup |
| Route/template variable mismatches | 2 | Fix in progress |
| Route redirects instead of rendering | 1 | Template is dead |
| Template depends on stale or unseen context | 1 | Verify or reconcile |

### Issue Details

#### Orphan / Dead Templates
- `admin_shadow_onboard.html` - no matching route renders it
- `admin_transactions.html` - `admin.transactions` redirects to `admin.banking`
- `admin_view_student_policy.html` - route aborts 404 before render
- `admin_setup_recovery.html` - renders, but contains no Jinja dependencies and is effectively static

#### Variable Mismatches / Stale Context
- `admin_support_tickets.html` - template expects `class_scope_options` and `entry.scope_join_code`, but the route shown only supplies `selected_class_id`, `my_reports`, `help_content`, and `format_utc_iso`
- `admin_username_migration.html` - route supplies `current_username`; template uses `current_username` in the current checkout, so keep this aligned if legacy variants remain

---

## Template Audit by Page

### `admin_recover.html`
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.recover` - GET|POST `/admin/recover` - [app/routes/admin.py:3138](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3138)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `form` | `AdminRecoveryForm` | CSRF and form validation wrapper |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 9 | `{{ static_url('css/tokens.css') }}` | `str` | `[GLOBAL] static_url` |
| 10 | `{{ static_url('css/style.css') }}` | `str` | `[GLOBAL] static_url` |
| 172 | `{% with messages = get_flashed_messages(with_categories=true) %}` | `list[tuple]` | `[FLASK]` |
| 175 | `{% for category, message in messages %}` | iterable | `[FLASK]` |
| 177-179 | category branching | `str` | `[FLASK]` |
| 181 | `{{ message }}` | `str` | `[FLASK]` |
| 198 | `{{ url_for('admin.recover') }}` | `str` | `[FLASK]` |
| 199 | `{{ form.csrf_token if form and form.csrf_token }}` | CSRF field | route `form` |
| 227 | `{{ url_for('admin.login') }}` | `str` | `[FLASK]` |
| 231 | `{{ static_url('images/logo_teacher_transparent_512.png') }}` | `str` | `[GLOBAL] static_url` |

### `admin_recovery_saved.html`
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.save_recovery_progress` - POST `/admin/save-recovery-progress` - [app/routes/admin.py:3517](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3517)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `resume_pin` | `str` | Resume PIN shown once to teacher |
| `codes_saved` | `int` | Number of recovery codes already saved |
| `recovery_request` | `RecoveryRequest` | Expiration timestamp display |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 13 | `{{ static_url('css/tokens.css') }}` | `str` | `[GLOBAL] static_url` |
| 14 | `{{ static_url('css/style.css') }}` | `str` | `[GLOBAL] static_url` |
| 89 | `{{ codes_saved }}` | `int` | route |
| 89 | `{{ recovery_request.expires_at.strftime(...) }}` | datetime | route |
| 94 | `{{ resume_pin }}` | `str` | route |
| 102 | `{{ recovery_request.expires_at.strftime(...) }}` | datetime | route |
| 117 | `{{ url_for('admin.login') }}` | `str` | `[FLASK]` |

### `admin_recovery_status.html`
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.recovery_status` - GET `/admin/recovery-status` - [app/routes/admin.py:3302](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3302)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `recovery_request` | `RecoveryRequest` | Request metadata and expiration |
| `codes` | `list[RecoveryCode]` | Student code status list |
| `verified_count` | `int` | Progress numerator |
| `total_count` | `int` | Progress denominator |
| `all_verified` | `bool` | Controls next-step CTA |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 13 | `{{ static_url('css/tokens.css') }}` | `str` | `[GLOBAL] static_url` |
| 14 | `{{ static_url('css/style.css') }}` | `str` | `[GLOBAL] static_url` |
| 108 | `get_flashed_messages(with_categories=true)` | list | `[FLASK]` |
| 132 | `{{ recovery_request.expires_at.strftime(...) }}` | datetime | route |
| 139 | `{{ (verified_count / total_count * 100) if total_count > 0 else 0 }}` | number | route |
| 140 | `{{ verified_count }}` | `int` | route |
| 142 | `{{ total_count }}` | `int` | route |
| 143 | `{{ verified_count }} / {{ total_count }} Verified` | ints | route |
| 150 | `{% for code in codes %}` | iterable | route |
| 151 | `{% if code.code_hash %}` | truthy check | route |
| 154 | `{{ loop.index }}` | loop index | Jinja |
| 157 | `{{ code.verified_at.strftime(...) if code.verified_at else 'recently' }}` | datetime/None | route |
| 160 | `{{ code.notified_at.strftime(...) }}` | datetime | route |
| 169 | `{% if all_verified %}` | bool | route |
| 174 | `{{ url_for('admin.reset_credentials') }}` | `str` | `[FLASK]` |
| 190 | `{{ url_for('admin.login') }}` | `str` | `[FLASK]` |
| 199 | `{% if not all_verified %}` | bool | route |

### `admin_rent_settings.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.rent_settings` - GET|POST `/admin/rent-settings` - [app/routes/admin.py:6498](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:6498)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `settings` | rent settings object | Current rent configuration |
| `total_students` | `int` | Summary count |
| `active_waivers` | `list` | Waivers table |
| `all_students` | `list` | Used for waiver form select |
| `payroll_warning` | `str\|None` | Warning banner |
| `payroll_settings` | object | Used in rent/preview JS and warning text |
| `settings_block` | `str` | Active block scope |
| `teacher_blocks` | `list` | Available blocks |
| `class_labels_by_block` | `dict` | Display labels |
| `join_codes_by_block` | `dict` | Join codes by block |
| `rent_items` | `list` | Rent-linked items list |
| `rent_active_for_period` | `bool` | Controls feature state messaging |
| `period_label` | `str` | Frequency label |
| `rent_status_counts` | object/dict | Current/late counts |
| `rent_status_total` | `int` | Student total |
| `payment_log` | `list` | Paid rent entries |
| `unpaid_rent_log` | `list` | Unpaid rent entries |
| `current_period_start` | datetime\|None | Current period display |
| `current_period_end` | datetime\|None | Current period display |
| `next_due_date` | datetime\|None | Next due date display |
| `student_past_due_json` | `dict` | JS data payload |
| `current_coverage_due_date` | datetime\|None | Waiver scope controls |
| `upcoming_coverage_due_date` | datetime\|None | Waiver scope controls |
| `selected_feature_scope` | object | Used in JS and header display |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 1 | `{% extends "layout_admin.html" %}` | parent template | layout |
| 27 | `{{ static_url('js/economy-balance.js') }}` | `str` | `[GLOBAL] static_url` |
| 169 | `{% if settings.is_enabled %}` | bool | route |
| 176, 184, 192, 200 | `{{ rent_status_counts.* }}` | numbers | route |
| 235 | `class="card-header {% if settings.is_enabled %}...` | bool | route |
| 243-260 | `settings.rent_amount`, `settings.frequency_type`, `settings.custom_frequency_value`, `settings.late_penalty_amount`, `settings.late_penalty_type`, `settings.late_penalty_frequency_days` | numbers/strings | route |
| 266-295 | due date and period fields | dates/ints | route |
| 301-307 | feature badges | bools/ints | route |
| 310 | `{{ rent_status_total }}` | `int` | route |
| 331 | `{{ payment_log|length }}` | `int` | route |
| 336 | `{{ unpaid_rent_log|length }}` | `int` | route |
| 356-369 | `payment_log` iteration | list | route |
| 359, 396 | `{{ student_detail_url(row.actor_public_id) }}` | `str` | `[GLOBAL] student_detail_url` |
| 365-369 | `row.*` fields | object fields | route |
| 381-415 | `unpaid_rent_log` iteration | list | route |
| 405-410 | `row.unpaid_months`, `row.months_behind` | list/int | route |
| 432, 878, 900, 1024 | `csrf_token()` | `str` | `[FLASK]` |
| 441-442, 483, 491, 495, 497, 506, 511, 518, 520, 522, 533, 557, 566, 590, 597, 607, 609, 616, 619, 643, 652, 655, 663, 675, 680, 681, 686, 689, 691, 705, 706, 721, 726, 727, 731, 737, 742, 743, 748, 749, 763-779, 784-821 | `settings`, `rent_items`, `all_students`, `active_waivers`, `current_coverage_due_date`, `selected_feature_scope`, `class_labels_by_block`, `join_codes_by_block` and related values | route |
| 1008-1017 | `format_utc_iso(waiver.waiver_start_date)`, `format_utc_iso(waiver.waiver_end_date)` | datetime | `[GLOBAL] format_utc_iso` |
| 1048 | `{{ student_past_due_json | tojson }}` | JSON | route |
| 1240 | `payroll_settings.expected_weekly_hours` fallback logic | number | route |
| 1244 | `{{ selected_feature_scope.block or "" }}` | `str` | route |
| 1273 | `{{ rent_items| length }}` | `int` | route |

### `admin_reset_credentials.html`
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.reset_credentials` - GET|POST `/admin/reset-credentials` - [app/routes/admin.py:3341](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3341)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `form` | `AdminResetCredentialsForm` | CSRF and form handling |
| `show_qr` | `bool` | Switches between recovery-code step and TOTP step |
| `qr_b64` | `str` | QR image payload |
| `totp_secret` | `str` | Manual TOTP code display |
| `new_username` | `str` | Username shown in confirmation step |
| `saved_codes` | `list[str]` | Partial progress restore |
| `saved_username` | `str` | Restored username |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 10 | `{{ static_url('css/tokens.css') }}` | `str` | `[GLOBAL] static_url` |
| 11 | `{{ static_url('css/style.css') }}` | `str` | `[GLOBAL] static_url` |
| 160 | `get_flashed_messages(with_categories=true)` | list | `[FLASK]` |
| 157, 170, 223, 310 | `show_qr` branches | bool | route |
| 180 | `{{ url_for('admin.reset_credentials') }}` | `str` | `[FLASK]` |
| 181 | `{{ form.csrf_token if form and form.csrf_token }}` | CSRF field | route `form` |
| 206 | `{{ saved_username or '' }}` | `str` | route |
| 217 | `{{ url_for('admin.save_recovery_progress') }}` | `str` | `[FLASK]` |
| 218 | `{{ form.csrf_token if form and form.csrf_token }}` | CSRF field | route `form` |
| 223-247 | `saved_codes|tojson` and client-side prefill | list | route |
| 318 | `{{ qr_b64 }}` | `str` | route |
| 320 | `{{ totp_secret }}` | `str` | route |
| 323 | `{{ url_for('admin.confirm_reset') }}` | `str` | `[FLASK]` |
| 324 | `{{ form.csrf_token if form and form.csrf_token }}` | CSRF field | route `form` |
| 351, 353, 355, 357 | footer links | route/FLASK |
| 361 | `{{ static_url('images/logo_teacher_transparent_512.png') }}` | `str` | `[GLOBAL] static_url` |

### `admin_resume_credentials.html`
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.resume_credentials` - GET|POST `/admin/resume-credentials` - [app/routes/admin.py:3565](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3565)

**Variables from route:** none required on render

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 10 | `{{ static_url('css/tokens.css') }}` | `str` | `[GLOBAL] static_url` |
| 11 | `{{ static_url('css/style.css') }}` | `str` | `[GLOBAL] static_url` |
| 127 | `get_flashed_messages(with_categories=true)` | list | `[FLASK]` |
| 142 | `{{ url_for('admin.resume_credentials') }}` | `str` | `[FLASK]` |
| 160 | `{{ url_for('admin.login') }}` | `str` | `[FLASK]` |
| 166, 168, 170 | privacy/district/terms links | `[FLASK]` |
| 174 | `{{ static_url('images/logo_teacher_transparent_512.png') }}` | `str` | `[GLOBAL] static_url` |

### `admin_select_class_context.html`
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.select_class_context` - GET|POST `/admin/select-class-context` - [app/routes/admin.py:2545](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:2545)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `class_options` | `list[dict]` | Validated class choices |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 8 | `{{ static_url('css/tokens.css') }}` | `str` | `[GLOBAL] static_url` |
| 9 | `{{ static_url('css/style.css') }}` | `str` | `[GLOBAL] static_url` |
| 70 | `get_flashed_messages(with_categories=true)` | list | `[FLASK]` |
| 81 | `{{ csrf_token() }}` | `str` | `[FLASK]` |
| 86-88 | `class_options` iteration | list | route |
| 95 | `{{ url_for('admin.onboarding') }}` | `str` | `[FLASK]` |

### `admin_settings.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.settings` - GET|POST `/admin/settings` - [app/routes/admin.py:3611](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3611)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `admin` | `User` | Current teacher account |
| `blocks` | `list` | Block/class label rows |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 1 | `{% extends "layout_admin.html" %}` | parent template | layout |
| 18 | `{{ url_for('admin.settings') }}` | `str` | `[FLASK]` |
| 19 | `{{ csrf_token() }}` | `str` | `[FLASK]` |
| 37 | `{{ admin.display_name or '' }}` | `str` | route |
| 38 | `{{ admin.teacher_public_id or admin.get_display_name() }}` | `str` | route |
| 42 | `{{ admin.teacher_public_id or admin.get_display_name() }}` | `str` | route |
| 49-63 | `blocks` iteration / `block_data.block` / `block_data.class_label` | list | route |
| 74 | `{{ admin.teacher_public_id or admin.get_display_name() }}` | `str` | route |
| 79 | `{{ admin.created_at.strftime(...) if admin.created_at else 'N/A' }}` | datetime | route |
| 83 | `{{ admin.last_login.strftime(...) if admin.last_login else 'N/A' }}` | datetime | route |
| 153 | `{{ csrf_token() }}` in JS header | `str` | `[FLASK]` |
| 160 | `{{ url_for("admin.dashboard") }}` | `str` | `[FLASK]` |

### `admin_setup_recovery.html`
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.setup_recovery` - GET|POST `/admin/setup-recovery` - [app/routes/admin.py:3601](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3601)

**Variables from route:** none

**Jinja expressions:** none beyond static HTML shell

### `admin_shadow_onboard.html`
**Extends:** `layout_admin.html`  
**Route(s):** None. No route in the current codebase renders this template.  
**Status:** Orphan template

**Variables from route:** none

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 40-47 | `get_flashed_messages(with_categories=true)` loop | list | `[FLASK]` |
| 52, 58, 95 | `join_code` | `str` | would-be route input |
| 95 | `url_for('admin.shadow_student_onboard', join_code=join_code)` | `str` | no matching route exists |
| 99-109 | `request.form.get(...)` | form fields | `[FLASK]` |

**Note:** This file is referenced in the tracking audit as dead/orphaned.

### `admin_signup.html`
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.signup` - GET|POST `/admin/signup` - [app/routes/admin.py:2952](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:2952)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `form` | `AdminSignupForm` | CSRF and signup form |
| `turnstile_site_key` | `str\|None` | Cloudflare Turnstile key |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 8 | `{{ static_url('css/tokens.css') }}` | `str` | `[GLOBAL] static_url` |
| 9 | `{{ static_url('css/style.css') }}` | `str` | `[GLOBAL] static_url` |
| 90 | `get_flashed_messages(with_categories=true)` | list | `[FLASK]` |
| 100 | `{{ url_for('admin.signup') }}` | `str` | `[FLASK]` |
| 101 | `{{ form.csrf_token if form and form.csrf_token }}` | CSRF field | route `form` |
| 106 | `{{ turnstile_site_key }}` | `str\|None` | route/config |
| 115-118 | footer links | `[FLASK]` |
| 139-141 | terms/privacy/district links | `[FLASK]` |
| 110 | `{{ static_url('images/logo_teacher_transparent_512.png') }}` | `str` | `[GLOBAL] static_url` |

### `admin_signup_totp.html`
**Extends:** None (standalone HTML document)  
**Route(s):** `admin.signup` - GET|POST `/admin/signup` - [app/routes/admin.py:3031](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3031), [app/routes/admin.py:3058](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3058), [app/routes/admin.py:3087](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3087)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `form` | `AdminTOTPConfirmForm` | Hidden username + CSRF |
| `qr_b64` | `str` | QR code image payload |
| `totp_secret` | `str` | Manual TOTP secret display |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 10 | `{{ static_url('css/tokens.css') }}` | `str` | `[GLOBAL] static_url` |
| 11 | `{{ static_url('css/style.css') }}` | `str` | `[GLOBAL] static_url` |
| 159 | `get_flashed_messages(with_categories=true)` | list | `[FLASK]` |
| 162-164 | flash category branch | `str` | `[FLASK]` |
| 219 | `{{ qr_b64 }}` | `str` | route |
| 221 | `{{ totp_secret }}` | `str` | route |
| 263 | `{{ form.hidden_tag() }}` | WTForms markup | route `form` |
| 264 | `{{ form.username(type="hidden") }}` | WTForms field | route `form` |
| 272-276 | privacy/district/terms links | `[FLASK]` |
| 280 | `{{ static_url('images/logo_teacher_transparent_512.png') }}` | `str` | `[GLOBAL] static_url` |

### `admin_store.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.store_management` - GET|POST `/admin/store` - [app/routes/admin.py:5275](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:5275), rendered at [app/routes/admin.py:5619](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:5619)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `form` | `StoreItemForm` | Store item editor |
| `items` | `list[StoreItem]` | Existing items |
| `current_page` | `str` | Navigation state |
| `total_items` | `int` | Overview stat |
| `active_items` | `int` | Overview stat |
| `total_purchases` | `int` | Overview stat |
| `pending_redemptions` | `list[StorePurchase]` | Approval queue |
| `recent_purchases` | `list[StorePurchase]` | Purchase history |
| `class_labels_by_block` | `dict` | Block label display |
| `rent_managed_item_ids` | `set[int]` | Rent-linked item highlighting |
| `collective_progress_by_item` | `dict` | Collective-goal progress |
| `audit_rows` | `list` | Redemption audit rows |
| `audit_total` | `int` | Audit count |
| `audit_page` | `int` | Audit page |
| `audit_total_pages` | `int` | Audit pagination |
| `audit_class_options` | `list[str]` | Audit class filter options |
| `audit_student` | `str` | Filter value |
| `audit_class` | `str` | Filter value |
| `audit_action` | `str` | Filter value |
| `audit_start_date` | `str` | Filter value |
| `audit_end_date` | `str` | Filter value |
| `feature_options` | `list[dict]` | Feature scope options |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 2 | `{% import "macros/help.html" as help %}` | macro namespace | template import |
| 9 | `class_label(block)` macro | `str` | in-template macro |
| 17, 127, 131 | `url_for('docs.view_doc', ...)` | `str` | `[FLASK]` |
| 24-25 | `static_url('js/economy-balance.js')`, `static_url('js/item-form-economy.js')` | `str` | `[GLOBAL] static_url` |
| 245, 306, 720, 821 | `format_utc_iso(...)` | datetime | `[GLOBAL] format_utc_iso` |
| 248, 248-249 | `markdown` filter | `str` | `[FILTER] markdown` |
| 359, 396, 465, 477, 596 | `student_detail_url(...)` | `str` | `[GLOBAL] student_detail_url` |
| 427 | `class_label(block)` | macro call | template macro |
| 432, 880, 906 | `csrf_token()` | `str` | `[FLASK]` |
| 1048 | `student_past_due_json | tojson` | JSON | route |
| 1108, 1144 | JS references / markdown editor init | route/template logic |
| Many | `form.*` fields | WTForms | route |
| Many | `items`, `pending_redemptions`, `recent_purchases`, `collective_progress_by_item`, `audit_rows`, `audit_class_options`, `feature_options` | collections | route |

### `admin_students.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.students` - GET `/admin/students` - [app/routes/admin.py:3945](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:3945), rendered at [app/routes/admin.py:4114](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:4114)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `students` | `list[Seat]` | Claimed seats in the active canonical class |
| `claimed_students` | `list[Seat]` | Claimed seats rendered in the active class roster |
| `unclaimed_seats` | `list[Seat]` | Pending seats in the active canonical class |
| `class_display_label` | `str` | Display-only label assembled from `ClassEconomy.section` + `ClassEconomy.display_name` |
| `current_class_id` | `str` | Canonical active class scope |
| `current_class_section` | `str\|None` | Display-only class section label |
| `current_class_display_name` | `str\|None` | Display-only class name |
| `current_class_join_code` | `str\|None` | Display join code read from `ClassEconomy.join_code` |
| `student_balances_by_seat_id` | `dict` | Checking/savings/earnings by canonical `seat_id` |
| `student_rent_privileges_by_seat_id` | `dict` | Per-seat privilege list |
| `student_hall_pass_balances_by_seat_id` | `dict` | Derived hall-pass entitlement balances by canonical `seat_id` |
| `timezone_choices` | `list[str]` | Timezone selector options |
| `pending_class_timezone_confirmations` | `list` | Pending timezone confirmations |
| `single_context_mode` | `bool` | Context behavior flag |
| `current_page` | `str` | Navigation state |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 86 | `static_url('css/style.css')` | `str` | `[GLOBAL] static_url` |
| 327, 681, 711, 744, 820, 945 | `url_for(...)` for export/template/upload/add/edit/delete | `str` | `[FLASK]` |
| 712, 745, 829, 954 | `csrf_token()` | `str` | `[FLASK]` |
| 465, 477, 596 | `student_detail_url(student.public_id)` | `str` | `[GLOBAL] student_detail_url` |
| 609 | `student_hall_pass_balances_by_seat_id.get(student.id, 0)` | number | REWIRED_READ from entitlement projection minus consumed `hall_pass_logs`; scoped by canonical `seat_id`, not block |
| roster bulk hall-pass action | `bulkUpdateHallPass()` → `/admin/students/bulk-adjust-hall-pass-entitlements` | API action | REWIRED_WRITE to entitlement add/remove semantics only; `set balance` was removed because available hall-pass count is derived from append-only entitlement and consumption events |
| 526-531, 1614-1690 | Bulk Start Work / Break actions | API POST body with `seat_ids` | REWIRED_WRITE to `admin.tap_in_students` / `admin.tap_out_students`, which call `FEAT-PROD-001`; no block or period scope is submitted |
| roster/edit rows | `student.identity_profile.first_name`, `.last_name`, `.notes`, `.full_name` | `IdentityProfile` on each current-class `Seat` | route query joins `IdentityProfile`; edit route writes only first name, last name, notes, reset code, and seat claim-name hashes |
| roster context | `class_display_label`, `current_class_join_code`, `claimed_students`, `unclaimed_seats`, `student_balances_by_seat_id`, `student_rent_privileges_by_seat_id`, `student_hall_pass_balances_by_seat_id`, `timezone_choices`, `pending_class_timezone_confirmations` | route | route |
| 728, 731, 763-821, 945 etc. | `loop.index`, `loop.index0` and current-class iteration | Jinja | Jinja loop context |
| 880+ | modal/delete form actions | `[FLASK]` |

**Migration disposition:** COLLAPSED/REWIRED — block-grouped roster tabs and block movement UI were removed now. `admin_students.html` is a single active-class roster keyed by canonical `class_id` and `seat_id`. Edit Student is limited to `IdentityProfile` first name, last name, notes, and account reset; name edits also refresh `Seat.claim_first_name_hash` and `Seat.claim_last_name_hash`.

### `admin_support_tickets.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.help_support` - GET|POST `/admin/help-support` - [app/routes/admin.py:9571](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:9571), rendered at [app/routes/admin.py:9759](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:9759)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `selected_class_id` | `str\|None` | Current class context |
| `my_reports` | `list` | Teacher’s own reports |
| `help_content` | object | Help articles |
| `format_utc_iso` | callable | Timestamp formatter |
| `class_scope_options` | not shown in route | Template expects this, but the shown route does not provide it |
| `scope_join_code` | not shown in route | Template references `entry.scope_join_code`, but route does not provide it |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 18 | `url_for('admin.help_support')` | `str` | `[FLASK]` |
| 19 | `csrf_token()` | `str` | `[FLASK]` |
| 23 | `class_scope_options` | list | not supplied by shown route |
| 24 | `selected_class_id` | `str\|None` | route |
| 79-95 | `my_reports` iteration | list | route |
| 86 | `entry.class_label` | `str` | route object |
| 86 | `entry.scope_join_code` | `str\|None` | not supplied by shown route |
| 89 | `report.status` | `str` | route object |
| 92 | `format_utc_iso(report.submitted_at)` | callable | route |
| 93 | `entry.issue_category` / `report.report_type` | `str` | route object |
| 95 | `entry.clean_description` | `str` | route object |
| 116 | `url_for('admin.help_support')` | `str` | `[FLASK]` |

**Note:** This template is partially stale relative to the route body shown.

### `admin_transactions.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.transactions` - GET `/admin/transactions` - [app/routes/admin.py:6776](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:6776)

**Status:** route redirects to `admin.banking` and never renders this template.

**Variables from route:** none

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 14, 24, 27, 30, 80 | `request.args.get(...)` / `request.args.items()` | query args | `[FLASK]` |
| 54 | `format_utc_iso(tx.timestamp)` | datetime | `[GLOBAL] format_utc_iso` |
| 50-72 | `transactions`, `page`, `total_pages` | collections/ints | no current route render |

**Status:** dead/orphaned relative to current route behavior.

### `admin_username_migration.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.username_migration` - GET|POST `/admin/username-migration` - [app/routes/admin.py:2879](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:2879), rendered at [app/routes/admin.py:2944](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:2944)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `current_username` | `str` | Existing username display |
| `no_recovery_warning` | `bool` | Warning banner |
| `student_count` | `int` | Recovery warning support |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 21 | `no_recovery_warning` | bool | route |
| 30 | `current_username` | `str` | route |
| 34 | `url_for('admin.username_migration')` | `str` | `[FLASK]` |
| 35 | `csrf_token()` | `str` | `[FLASK]` |
| 42 | `url_for('admin.username_migration')` | `str` | `[FLASK]` |
| 43 | `csrf_token()` | `str` | `[FLASK]` |

### `admin_view_issue.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.view_issue` - GET `/admin/issues/<issue_ref>` - [app/routes/admin.py:11033](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:11033), rendered at [app/routes/admin.py:11052](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:11052)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `issue` | `Issue` | Full issue record |
| `issue_ref` | `str` | Opaque issue ref |
| `format_utc_iso` | callable | Timestamp formatter |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 8 | `url_for('admin.issues_queue')` | `str` | `[FLASK]` |
| 24-30 | `issue.status` branches | `str` | route |
| 40 | `issue.student_display_name` | `str` | route |
| 41-43 | `issue.class_label` | `str\|None` | route |
| 52 | `issue.category.name` | object | route |
| 53 | `issue.issue_type` | `str` | route |
| 62 | `issue.student_explanation` | `str` | route |
| 66-73 | `issue.student_expected_outcome` | `str\|None` | route |
| 83, 91 | `format_utc_iso(issue.submitted_at)`, `format_utc_iso(issue.teacher_reviewed_at)` | datetime | `[GLOBAL] format_utc_iso` |
| 100-141 | `issue.context_snapshot.transaction.*` | nested object | route snapshot |
| 156-178 | `issue.context_snapshot.balances.*` | nested object | route snapshot |
| 181-207 | `issue.context_snapshot.recent_transactions` | list | route snapshot |
| 213-241 | `issue.resolution_actions` | queryable relationship | route |
| 232, 349, 351, 372, 390, 416 | `format_utc_iso(...)` | datetime | `[GLOBAL] format_utc_iso` |
| 257 | `url_for('admin.resolve_issue', issue_ref=issue_ref)` | `str` | `[FLASK]` |
| 258 | `csrf_token()` | `str` | `[FLASK]` |
| 312 | `url_for('admin.close_issue', issue_ref=issue_ref)` | `str` | `[FLASK]` |
| 313 | `csrf_token()` | `str` | `[FLASK]` |
| 442 | `url_for('admin.escalate_issue', issue_ref=issue_ref)` | `str` | `[FLASK]` |
| 443 | `csrf_token()` | `str` | `[FLASK]` |
| 406-424 | `issue.status_history` | list | route |

### `admin_view_student_policy.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.view_student_policy` - GET `/admin/insurance/student-policy/<enrollment_id>` - [app/routes/admin.py:6760](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:6760)

**Status:** route aborts 404 before render; template is dead/orphaned.

**Variables from route:** none in current execution path

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 8 | `student.full_name`, `enrollment.contract_title` | strings | would-be route |
| 21 | `enrollment.contract_description | markdown` | markdown text | `[FILTER] markdown` |
| 27-29 | `student`, `enrollment.policy.*` | objects | would-be route |
| 31-53 | enrollment status / dates / payment state | objects | would-be route |
| 70-89 | policy terms | objects | would-be route |
| 115-139 | claims table + `url_for('admin.process_claim', claim_id=claim.id)` | list + `[FLASK]` | would-be route |
| 163 | `student_detail_url(seat.public_id)` | `str` | `[GLOBAL] student_detail_url` |
| 166 | `url_for('admin.insurance_management')` | `str` | `[FLASK]` |
| 181-192 | `policy.claim_type`, `enrollment.policy.no_repurchase_after_cancel` | objects | would-be route |

### `student_detail.html`
**Extends:** `layout_admin.html`  
**Route(s):** `admin.student_detail_public` - GET `/admin/students/<actor_public_id>` - [app/routes/admin.py:4211](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:4211), rendered at [app/routes/admin.py:4394](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py:4394)

**PROD status:** REWIRED_READ

- Recent attendance summary and history are rewired to canonical `attendance_sessions` display rows.
- Hall-pass balance display is rewired to the derived entitlement projection (`entitlement` grants/purchases minus consumed approved `hall_pass_logs`) through `hall_pass_balance`; the template no longer dereferences `student.hall_passes`.
- Seat-level tap settings UI was removed; tap enablement is not seat-level PROD truth.
- Legacy tap-entry management UI was removed; v2 attendance rows are immutable forever facts and have no delete, soft-delete, mark-deleted, or edit/correction surface.
- If a teacher needs to correct an already-paid attendance outcome, the canonical correction path is payroll reversal, not attendance-row mutation.
- Legacy `/api/admin/tap-entries/*`, `/api/admin/student-block-settings`, and `/api/admin/block-tap-settings` API paths were deleted after this template stopped referencing them.
- Resolved 2026-07-22: Payroll tab now reads canonical `payroll_event` rows and Ledger amounts by `correlation_id` through the shared payroll-event display builder instead of filtering legacy `Transaction.type` values.
- Resolved 2026-07-22: Join-code display now uses the current class label plus `ClassEconomy.join_code`; it no longer derives account-recovery join-code display from `student.block`.

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| `student` | `Seat` | Student detail object |
| `reset_code_is_active` | `bool` | Shows reset code section |
| `join_codes` | `dict[str,str]` | Class-section join codes |
| `transactions` | `list[Transaction]` | Financial history |
| `student_items` | `list[StorePurchase]` | Store purchase history |
| `latest_attendance_event` | object\|None | Attendance summary from canonical `attendance_sessions` |
| `attendance_events` | `list` | Attendance history display rows from canonical `attendance_sessions` |
| `payroll_event_history` | `list[dict]` | Payroll event display rows from canonical `payroll_event` plus Ledger amount lookup by `correlation_id` |
| `active_insurance` | object\|None | Insurance summary |
| `scoped_checking_balance` | number | Current checking balance |
| `scoped_savings_balance` | number | Current savings balance |
| `scoped_total_earnings` | number | Net total from `payroll_event_history` amounts |
| `hall_pass_balance` | number | Derived hall-pass entitlement balance |
| `current_join_code` | `None` | Present for layout consistency |
| `current_class_id` | `str` | Active class scope |
| `rent_privileges` | `list` | Rent-related privileges |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 1 | `{% extends "layout_admin.html" %}` | parent template | layout |
| 33 | `url_for('admin.students')` | `str` | `[FLASK]` |
| 37-43 | `student.full_name`, `student.is_teacher_shadow` | object fields | route |
| 60, 71, 81 | `scoped_checking_balance`, `scoped_savings_balance`, `scoped_total_earnings` | numbers | route |
| 91 | `hall_pass_balance` | number | REWIRED_READ from entitlement projection minus consumed `hall_pass_logs` |
| 99-124 | `rent_privileges` iteration | list | route |
| 138, 144 | `transactions|length`, `student_items|length` | int | route |
| 153, 215, 619 | `global_rent_enabled and student.is_rent_enabled` | bool | route/template globals |
| 190-236, 255-300 | `join_codes.items()` | dict | REWIRED_READ from current `ClassEconomy.join_code` keyed by class display label; no `student.block` derivation |
| 240-277 | `reset_code_is_active`, `student.reset_code`, `student.reset_code_expires_at` | object fields | route |
| 280-312 | `student.has_completed_setup`, `student.recovery_status` | object fields | route |
| 325-356 | `latest_attendance_event.*` and `format_utc_iso(...)` | object + `[GLOBAL] format_utc_iso` | REWIRED_READ from canonical `attendance_sessions` display row |
| 374-426 | `transactions` iteration, void button, `format_utc_iso(tx.timestamp)` | route + `[GLOBAL] format_utc_iso` |
| 446-499 | `student_items` iteration | route |
| removed | former `student_blocks_settings.items()` tap-toggle block | Removed UI | COLLAPSED — seat-level tap enablement is not PROD v2 truth |
| removed | former Manage Tap Entries UI and delete/load actions | Removed UI | COLLAPSED — attendance rows are immutable in v2; correction after payroll is handled by payroll reversal |
| 567-607 | `attendance_events|sort(...)` and `format_utc_iso(tap.timestamp)` | route / `[GLOBAL] format_utc_iso` | REWIRED_READ from canonical `attendance_sessions` display rows |
| 619-668 | rent section fields (`student.rent_last_paid`, `student.rent_due_date`, `student.rent_overdue`) | route |
| 679-732 | earnings summary and `payroll_event_history` rows | REWIRED_READ from canonical `payroll_event` plus Ledger amount lookup by `correlation_id`; no legacy `Transaction.type == payroll/bonus` filters |
| 748-857 | hall-pass entitlement form / student edit modal | route; hall-pass balance uses `hall_pass_balance`, not `student.hall_passes`; form can add grants or remove unconsumed grant correlations, not set an arbitrary balance |
| 980 | `student.id` in JS | route |
