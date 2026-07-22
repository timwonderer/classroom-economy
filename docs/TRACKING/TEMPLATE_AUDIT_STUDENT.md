# Student Template & Route Audit

**Last Updated:** 2026-07-19  
**Scope:** Student-facing templates (student blueprint + recovery flow)  
**Total Templates Audited:** 24  

---

## Executive Summary

### ⚠️ Critical Issues Found

| Issue | Count | Status |
|-------|-------|--------|
| Orphan templates (no route) | 4 | Mark for deletion |
| Routes that abort(404) | 3 | Never render templates |
| Legacy unused templates | 3 | Being phased out |

### Issue Details

#### Orphan Templates / Not Rendered
- `student_complete_profile.html` — No route renders it
- `student_help_support.html` — Legacy; help_support() renders `student_help_support_new.html` instead
- `student/recovery/landing.html` — Route exists but redirects before rendering
- `student/recovery/reset_form.html` — No route renders it

#### Routes That Abort(404)
- `student.student_insurance` — Aborts before rendering `student_insurance_marketplace.html`
- `student.file_claim` — Aborts before rendering `student_file_claim.html`
- `student.view_policy` — Aborts before rendering `student_view_policy.html`

#### Feature Status
- Insurance marketplace, claim filing, and policy views all abort(404) currently
- Recovery flow partially implemented (landing redirects, reset_form unused)

---

## Template Audit by Page

### student_login.html
**Extends:** None (standalone HTML)  
**Route(s):** `student.login` — GET|POST `/student/login` — [app/routes/student.py:2905](app/routes/student.py#L2905)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| form | StudentLoginForm | Login form (username, pin, submit, hidden_tag) |
| setup_cta | bool | Always True; not actually used in template |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 12 | `{{ static_url('manifest.json') }}` | str | [GLOBAL] |
| 164 | `{% with messages = get_flashed_messages() %}` | list | [FLASK] |
| 176 | `{{ form.hidden_tag() }}` | Markup | WTForms |
| 190 | `{% if turnstile_site_key %}` | str/None | [CTX:global_settings] |
| 200 | `{{ url_for('student.claim_account') }}` | str | [FLASK] |

---

### student_dashboard.html
**Extends:** `layout_student.html`  
**Route(s):** `student.dashboard` — GET `/student/dashboard` — [app/routes/student.py:830](app/routes/student.py#L830)

**Variables from route (key selections):**

| Variable | Type | Purpose |
|----------|------|---------|
| student | Seat | Current student/seat object |
| student_blocks | list[str] | Class display labels for the current class context |
| period_states | dict | Per-block tap/attendance state |
| checking_balance | float | Scoped checking balance |
| savings_balance | float | Scoped savings balance |
| recent_transactions | list[Transaction] | Last 5 transactions |
| pending_recovery_code | StudentRecoveryCode / None | Pending teacher recovery request |
| announcements | list[Announcement] | Active announcements |
| scoped_total_earnings | float | Lifetime earnings for seat in class |

**Jinja expressions (representative, complex template):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 2 | `{% import "macros/help.html" as help %}` | macro | [MACRO:help] |
| 11 | `{{ student_display_first_name }}` | str | route display metadata |
| 36 | `{{ period_states_json\|safe }}` | str | route (JSON) — REWIRED_READ from canonical `attendance_sessions` state projection |
| 157 | `{{ hall_pass_balance }}` | int | Entitlement projection: grants/purchases minus consumed approved `hall_pass_logs` |
| 189-221 | `Start Work` and contextual `Break` button + break modal | contextual controls | REWIRED — `Break` opens teacher-configured hall-pass destinations from `HallPassSettings`; destination selection creates ephemeral pending request; `Done for the day` writes `inactive/done_for_day` through `FEAT-PROD-001`; after approval the same button becomes `Leave`, then `Return` after checkout |
| 220 | `{{ "%.2f"\|format(checking_balance) }}` | str | route |
| 359 | `{{ current_class_id\|tojson }}` | JSON str | route + Jinja |

---

### student_shop.html
**Extends:** `layout_student.html`  
**Route(s):** `student.shop` — GET `/student/shop` — [app/routes/student.py:1519](app/routes/student.py#L1519)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| student | Seat | Current seat |
| items | list[StoreItem] | Available store items |
| student_items | list[StudentItem] | Student's purchased items |
| has_paid_rent | bool | Whether student has paid rent |
| class_size | int | Number of students in class |
| collective_progress | dict | Progress data for collective items |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 18 | `{{ student_items\|length }}` | int | route |
| 43 | `{{ item.name }}` | str | model |
| 69 | `{{ "%.2f"\|format(item.price) }}` | str | model |
| 137 | `{{ item.description \| markdown }}` | Markup | [FILTER] |

---

### student_transfer.html
**Extends:** `layout_student.html`  
**Route(s):** `student.transfer` — GET|POST `/student/transfer` — [app/routes/student.py:1245](app/routes/student.py#L1245)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| student | Seat | Current seat |
| checking_balance | float | Checking balance |
| savings_balance | float | Savings balance |
| forecast_interest | float | Projected monthly interest |
| scoped_total_earnings | float | Total earnings in class |
| settings | BankingSettings / None | Banking settings |
| projection_months | list[int] | Month numbers for chart |
| projection_balances | list[float] | Projected balances for chart |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 50 | `{{ "%.2f"\|format(checking_balance) }}` | str | route |
| 124 | `{{ calculation_type }}` | str | route |
| 290 | `{{ format_utc_iso(tx.timestamp) }}` | str | [GLOBAL] |
| 484 | `{{ projection_months\|tojson }}` | JSON | route |

---

### student_payroll.html
**Extends:** `layout_student.html`  
**Route(s):** `student.payroll` — GET `/student/payroll` — [app/routes/student.py:1155](app/routes/student.py#L1155)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| student | Seat | Current seat |
| student_blocks | list[str] | Block identifiers |
| unpaid_seconds_per_block | dict[str, int] | Unpaid seconds per block |
| projected_pay_per_block | dict[str, float] | Projected pay per block |
| attendance_events | list[AttendanceSession] | Recent canonical attendance events |
| attendance_events_by_block | dict[str, list] | Attendance events grouped by block |
| attendance_start_count | int | Recent active/start count |
| attendance_inactive_count | int | Recent inactive/break/done count |
| pay_rate_per_minute | float | Pay rate per minute |
| pay_rate_table | list[tuple] | Time-to-earnings table |
| scoped_total_earnings | float | Lifetime earnings in class |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 40 | `{{ blk\|upper }}` | str | loop var |
| 60 | `{% set block_events = attendance_events_by_block[blk] %}` | list | route — REWIRED_READ from canonical `attendance_sessions` |
| 138 | `{{ unpaid_seconds_per_block.values()\|sum }}` | int | route |
| 301 | `{% for label, value in pay_rate_table %}` | tuple | route |

---

### student_rent.html
**Extends:** `layout_student.html`  
**Route(s):** `student.rent` — GET `/student/rent` — [app/routes/student.py:2431](app/routes/student.py#L2431)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| student | Seat | Current seat |
| settings | RentSettings | Rent settings for the class |
| student_blocks | list[str] | Block list |
| period_status | dict | Rent status per period |
| checking_balance | float | Checking balance |
| payment_due_date | date | Due date for current period |
| payment_history | list | Payment history rows |
| days_until_due | int / None | Days until due date |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 24 | `{% if feature_settings.rent_enabled %}` | bool | [CTX:feature_settings] |
| 47 | `{% set status = period_status[current_block] %}` | dict | route |
| 152 | `{{ payment_due_date.strftime(...) }}` | str | route |
| 223 | `{{ url_for('student.rent_pay', period=current_block) }}` | str | [FLASK] |

---

### ⚠️ student_insurance_marketplace.html
**Status:** ABORTED ROUTE — `student.student_insurance` aborts(404) before rendering  
**Extends:** `layout_student.html`  
**Route(s):** `student.student_insurance` — GET `/student/insurance` — [app/routes/student.py:1470](app/routes/student.py#L1470) **(currently abort(404))**

**Design context (unreachable variables):**

| Variable | Type | Purpose |
|----------|------|---------|
| my_policies | list[Enrollment] | Student's active insurance enrollments |
| available_policies | list[InsurancePolicy] | Available policies |
| my_claims | list[InsuranceClaim] | Student's claims |
| enrolled_tiers | set | Tier IDs already enrolled |

---

### ⚠️ student_file_claim.html
**Status:** ABORTED ROUTE — `student.file_claim` aborts(404) before rendering  
**Extends:** `layout_student.html`  
**Route(s):** `student.file_claim` — GET|POST `/student/insurance/claim/<int:policy_id>` — [app/routes/student.py:1494](app/routes/student.py#L1494) **(currently abort(404))**

---

### ⚠️ student_view_policy.html
**Status:** ABORTED ROUTE — `student.view_policy` aborts(404) before rendering  
**Extends:** `layout_student.html`  
**Route(s):** `student.view_policy` — GET `/student/insurance/policy/<int:enrollment_id>` — [app/routes/student.py:1501](app/routes/student.py#L1501) **(currently abort(404))**

---

### student_account_claim.html
**Extends:** None (standalone HTML)  
**Route(s):** `student.claim_account` — GET|POST `/student/claim-account` — [app/routes/student.py:463](app/routes/student.py#L463)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| form | StudentClaimAccountForm | Claim form (join_code, first_name, last_name, dedupe_code) |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 145 | `{% with messages = get_flashed_messages(...) %}` | list | [FLASK] |
| 160 | `{{ form.join_code(...) }}` | Markup | WTForms |
| 197 | `{{ url_for('student.login') }}` | str | [FLASK] |

---

### student_add_class.html
**Extends:** `layout_student.html`  
**Route(s):** `student.add_class` — GET|POST `/student/add-class` — [app/routes/student.py:658](app/routes/student.py#L658)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| form | WTForm | Add class form (join_code, first_name, last_name) |

---

### ❌ student_complete_profile.html
**Status:** ORPHAN — **Mark for deletion**  
**Route(s):** No active route renders this template  
**Note:** Likely replaced by newer profile completion workflow

---

### student_create_username.html
**Extends:** None (standalone HTML)  
**Route(s):** `student.create_username` — GET|POST `/student/create-username` — [app/routes/student.py:569](app/routes/student.py#L569)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| theme_prompt | str | Theme prompt for username word (from session) |
| form | WTForm | Form with write_in_word, submit, hidden_tag |

---

### student_pin_setup.html
**Extends:** None (standalone HTML)  
**Route(s):** `student.setup_pin_passphrase` — GET|POST `/student/setup-pin-passphrase` — [app/routes/student.py:600](app/routes/student.py#L600)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| username | str | Generated username (from session) |
| form | WTForm | Form with pin, passphrase, submit |

---

### student_setup_complete.html
**Extends:** None (standalone HTML)  
**Route(s):** `student.setup_complete` — GET `/student/setup-complete` — [app/routes/student.py:3168](app/routes/student.py#L3168)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| student_name | str | Student's first name (from IdentityProfile or empty) |

---

### student_select_class_context.html
**Extends:** None (standalone HTML)  
**Route(s):** `student.select_class_context` — GET|POST `/student/select-class-context` — [app/routes/student.py:3042](app/routes/student.py#L3042)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| class_options | list[dict] | Available classes (class_id, join_code, class_identifier, class_name) |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 33 | `{{ option.class_id }}` | str | route |
| 34 | `{{ option.join_code }} - {{ option.class_identifier }}` | str | route |

---

### ❌ student_help_support.html
**Status:** LEGACY — **Mark for deletion**  
**Route(s):** help_support() renders `student_help_support_new.html` instead  
**Note:** Replaced by newer help/support interface

---

### student_help_support_new.html
**Extends:** `layout_student.html`  
**Route(s):** `student.help_support` — GET `/student/help-support` — [app/routes/student.py:3179](app/routes/student.py#L3179)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| current_page | str | "help" |
| page_title | str | "Help & Support" |
| my_issues | list[Issue] | Student's submitted issues |
| help_content | dict | With keys how_to, troubleshooting |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 39 | `{% for article in help_content.how_to %}` | list | route |
| 166 | `{{ issue.category.name }}` | str | model |
| 188 | `{{ format_utc_iso(issue.submitted_at) }}` | str | route / [GLOBAL] |

---

### student_submit_issue.html
**Extends:** `layout_student.html`  
**Route(s):**
- `student.submit_general_issue` — GET|POST `/student/help-support/submit-issue` — [app/routes/student.py:3207](app/routes/student.py#L3207)
- `student.report_transaction_issue` — GET|POST `/student/help-support/transaction/<int:transaction_id>/report` — [app/routes/student.py:3262](app/routes/student.py#L3262)
- `student.report_attendance_session_issue` — GET|POST `/student/help-support/attendance-session/<int:attendance_session_id>/report` — [app/routes/student.py](app/routes/student.py)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| current_page | str | "help" |
| page_title | str | "Report an Issue" or similar |
| form | StudentIssueSubmissionForm | WTForms issue form |
| issue_type | str | "general", "transaction", or "attendance" |
| transaction | Transaction / None | Related transaction (if transaction type) |

**Jinja expressions (representative):**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 26 | `{{ url_for('student.help_support') }}` | str | [FLASK] |
| 41 | `{% if issue_type == 'transaction' and transaction %}` | str, obj | route |
| 47 | `{{ "%.2f"\|format(transaction.amount) }}` | str | route |
| 81 | `{{ form.category_id(...) }}` | Markup | WTForms |

---

### student_verify_recovery.html
**Extends:** `layout_student.html`  
**Route(s):** `student.verify_recovery` — GET|POST `/student/verify-recovery/<int:code_id>` — [app/routes/student.py:3392](app/routes/student.py#L3392)

**Variables from route:**

| Variable | Type | Purpose |
|----------|------|---------|
| recovery_code | StudentRecoveryCode | The recovery code object |
| verified | bool | Whether verification succeeded |
| generated_code | str / None | The generated 6-digit code (only on success) |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 10 | `{% if verified %}` | bool | route |
| 28 | `{{ generated_code }}` | str | route |
| 63 | `{{ recovery_code.recovery_request.expires_at.strftime(...) }}` | str | model |

---

### student/recovery/layout.html
**Extends:** None (standalone base layout)  
**Route(s):** Not rendered directly; extended by recovery sub-templates

**Note:** Serves as base layout for landing.html, account_lookup.html, reset_form.html, identity_update.html

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|------|-----------|---------|-------------|
| 5 | `{% block title %}Account Recovery{% endblock %}` | str | child |
| 117 | `{{ url_for('student.login') }}` | str | [FLASK] |
| 139 | `{% block content %}{% endblock %}` | Markup | child |

---

### ⚠️ student/recovery/landing.html
**Status:** REDIRECT ROUTE — Route redirects before rendering  
**Extends:** `student/recovery/layout.html`  
**Route(s):** `recovery.landing` — GET `/recovery/` — [app/routes/recovery.py:83](app/routes/recovery.py#L83) **(redirects to account_lookup)**

---

### student/recovery/account_lookup.html
**Extends:** `student/recovery/layout.html`  
**Route(s):** `recovery.account_lookup` — GET|POST `/recovery/lookup` — [app/routes/recovery.py:89](app/routes/recovery.py#L89)

**Variables from route:** None (renders with GET context only)

---

### ❌ student/recovery/reset_form.html
**Status:** ORPHAN — **Mark for deletion**  
**Route(s):** No active route renders this  
**Note:** Recovery flow redirects to student.create_username instead

---

### student/recovery/identity_update.html
**Extends:** `student/recovery/layout.html`  
**Route(s):** Auto-redirects to account_lookup

---

## Summary: Orphaned & Unused Templates

**Delete (4 templates):**
- `student_complete_profile.html` — No route renders it
- `student_help_support.html` — Replaced by `student_help_support_new.html`
- `student/recovery/landing.html` — Route redirects before rendering
- `student/recovery/reset_form.html` — No route renders it (recovery uses create_username)

**Fix Abort(404) Routes (3 routes):**
- `student.student_insurance` → enable or delete `student_insurance_marketplace.html`
- `student.file_claim` → enable or delete `student_file_claim.html`
- `student.view_policy` → enable or delete `student_view_policy.html`

Line	Expression	Expects	Supplied By
12	{{ static_url('manifest.json') }}	str	[GLOBAL]
20	{{ static_url('css/tokens.css') }}	str	[GLOBAL]
21	{{ static_url('css/style.css') }}	str	[GLOBAL]
164	{% with messages = get_flashed_messages() %}	list	[FLASK]
176	{{ form.hidden_tag() }}	Markup	WTForms
180	{{ form.username(...) }}	Markup	WTForms
186	{{ form.pin(...) }}	Markup	WTForms
190	{% if turnstile_site_key %}	str/None	[CTX:global_settings] (context processor)
192	{{ turnstile_site_key }}	str	[CTX:global_settings]
196	{{ form.submit(...) }}	Markup	WTForms
200	{{ url_for('student.claim_account') }}	str	[FLASK]
203	{{ url_for('recovery.account_lookup') }}	str	[FLASK]
208	{{ url_for('admin.login') }}	str	[FLASK]
215	{{ url_for('main.privacy') }}	str	[FLASK]
218	{{ url_for('main.district') }}	str	[FLASK]
220	{{ url_for('main.terms') }}	str	[FLASK]
225	{{ static_url('images/logo_student_transparent_512.png') }}	str	[GLOBAL]
248	{{ static_url('js/loading_modal.js') }}	str	[GLOBAL]
student_dashboard.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.dashboard — GET /student/dashboard — app/routes/student.py:830
Variables from route:

Variable	Type	Purpose
student	Seat (legacy Student compat)	Current student/seat object
student_blocks	list[str]	Period/block identifiers
period_states	dict	Per-block tap/attendance state
period_states_json	str (JSON)	JSON-serialized period states for JS
checking_balance	float	Scoped checking balance
savings_balance	float	Scoped savings balance
forecast_interest	float	Projected monthly interest
recent_transactions	list[Transaction]	Last 5 transactions
pending_recovery_code	`StudentRecoveryCode	None`	Pending teacher recovery request
recent_deposit	`Transaction	None`	Most recent deposit for alert
announcements	list[Announcement]	Active announcements
unique_days_tapped	int	Days tapped in this week
total_minutes_this_week	int	Total minutes this week
earnings_this_week	float	Earnings this week
spending_this_week	float	Spending this week
current_class_id	str (UUID)	Current class ID
scoped_total_earnings	float	Lifetime earnings for seat in class
Jinja expressions:

Line	Expression	Expects	Supplied By
2	{% import "macros/help.html" as help %}	macro module	[MACRO:help]
11	{{ student_display_first_name }}	str	route display metadata — REWIRED, no `student.display_first_name` dereference
36	{{ period_states_json|safe }}	str	route — REWIRED_READ from canonical attendance state projection
39	{% if pending_recovery_code %}	truthy	route
49	{{ pending_recovery_code.recovery_request.expires_at.strftime(...) }}	str	route
52	{{ url_for('student.verify_recovery', code_id=pending_recovery_code.id) }}	str	[FLASK]
57	{{ url_for('student.dismiss_recovery', code_id=pending_recovery_code.id) }}	str	[FLASK]
59	{{ csrf_token() }}	str	[FLASK]
73	{{ "%.2f"|format(recent_deposit.amount) }}	str	route
82	{{ announcement.get_priority_class() }}	str	model method
84	{{ announcement.get_priority_icon() }}	str	model method
87	{{ announcement.message|nl2br|safe }}	Markup	[FILTER]
108	{{ help.help_icon(...) }}	Markup	[MACRO:help]
114	{{ unique_days_tapped }}	int	route
121	{{ total_minutes_this_week }}	int	route
128	{{ "%.0f"|format(earnings_this_week) }}	str	route
136	{{ "%.0f"|format(spending_this_week) }}	str	route
157	{{ hall_pass_balance }}	int	route — REWIRED_READ from entitlement grant/purchase records minus approved `hall_pass_logs` consumption
220	{{ "%.2f"|format(checking_balance) }}	str	route
222	{{ url_for('student.transfer') }}	str	[FLASK]
225	{{ url_for('student.payroll') }}	str	[FLASK]
246	{{ "%.2f"|format(savings_balance) }}	str	route
249	{{ "%.2f"|format(forecast_interest) }}	str	route
293	{{ format_utc_iso(t.timestamp) }}	str	[GLOBAL]
303	{{ url_for('student.report_transaction_issue', transaction_id=t.id) }}	str	[FLASK]
359	{{ current_class_id|tojson }}	JSON str	route + Jinja builtin
405	{{ static_url('js/attendance.js') }}	str	[GLOBAL] — REWIRED_CLIENT_JS: contextual `Start Work`, `Break`, `Leave`, and `Return`; no deleted `/api/student-status/reconcile` call
student_shop.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.shop — GET /student/shop — app/routes/student.py:1519
Variables from route:

Variable	Type	Purpose
student	Seat	Current seat (aliased as seat)
items	list[StoreItem]	Available store items
student_items	list[StudentItem]	Student's purchased items
has_paid_rent	bool	Whether student has paid rent
rent_item_types_by_store_id	dict[int, list[str]]	Rent item types per store item
rent_free_uses	dict[int, int]	Remaining free uses per item
class_size	int	Number of students in class
current_block	str	Current block/period
collective_progress	dict	Progress data for collective items
Jinja expressions:

Line	Expression	Expects	Supplied By
18	{{ student_items|length }}	int	route
31-38	{% set rent_item_types = ... %} etc.	various	route data + Jinja logic
43	{{ item.name }}	str	model
69	{{ "%.2f"|format(item.price) }}	str	model
102	{{ collective_progress.get(item.id, ...) }}	dict	route
107	{{ class_size }}	int	route
137	{{ (item.description or '...') | markdown }}	Markup	[FILTER]
222	{{ format_utc_iso(student_item.purchase_date) }}	str	[GLOBAL]
249	{{ (student_item.store_item.description or '...') | markdown }}	Markup	[FILTER]
student_transfer.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.transfer — GET|POST /student/transfer — app/routes/student.py:1245
Variables from route:

Variable	Type	Purpose
student	Seat	Current seat
transactions	list[Transaction]	All transactions
checking_transactions	list[Transaction]	Checking account transactions
savings_transactions	list[Transaction]	Savings account transactions
checking_balance	float	Checking balance
savings_balance	float	Savings balance
forecast_interest	float	Projected monthly interest
scoped_total_earnings	float	Total earnings in class
settings	`BankingSettings	None`	Banking settings
calculation_type	str	"simple" or "compound"
compound_frequency	str	e.g. "monthly"
projection_months	list[int]	Month numbers for chart
projection_balances	list[float]	Projected balances for chart
transfer_token	str	CSRF-like transfer token
Jinja expressions:

Line	Expression	Expects	Supplied By
50	{{ "%.2f"|format(checking_balance) }}	str	route
58	{{ "%.2f"|format(savings_balance) }}	str	route
65	{{ "%.2f"|format(checking_balance + savings_balance) }}	str	route
83	{{ "%.2f"|format(scoped_total_earnings) }}	str	route
89	{{ "%.2f"|format(settings.savings_monthly_rate) }}	str	route
96	{{ "%.2f"|format(forecast_interest) }}	str	route
124	{{ "%.2f"|format(savings_balance) }}	str	route
124	{{ "%.2f"|format((settings.savings_apy if settings else 4.5)) }}	str	route
124	{{ calculation_type }}	str	route
125	{{ compound_frequency }}	str	route
153	{{ url_for('student.dashboard') }}	str	[FLASK]
290	{{ format_utc_iso(tx.timestamp) }}	str	[GLOBAL]
309	{{ url_for('student.report_transaction_issue', transaction_id=tx.id) }}	str	[FLASK]
399	{{ csrf_token() }}	str	[FLASK]
400	{{ transfer_token }}	str	route
484	{{ projection_months|tojson }}	JSON	route
484	{{ projection_balances|tojson }}	JSON	route
student_payroll.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.payroll — GET /student/payroll — app/routes/student.py:1155
Variables from route:

Variable	Type	Purpose
student	Seat	Current seat
student_blocks	list[str]	Block identifiers
unpaid_seconds_per_block	dict[str, int]	Unpaid seconds per block
projected_pay_per_block	dict[str, float]	Projected pay per block
period_states	dict	Per-block status
attendance_events	list[AttendanceSession]	Recent canonical attendance events
attendance_events_by_block	dict[str, list]	Events grouped by block
attendance_start_count	int	Recent active/start event count
attendance_inactive_count	int	Recent inactive/break/done event count
pay_rate_per_minute	float	Pay rate per minute
pay_rate_table	list[tuple[str, float]]	Time-to-earnings table
scoped_total_earnings	float	Lifetime earnings in class
Jinja expressions:

Line	Expression	Expects	Supplied By
40	{{ blk|upper }}	str	loop var
41	{% set state = period_states[blk] %}	dict	route
54	{{ (unpaid_seconds_per_block[blk] // 3600)|string + ... }}	str	route
60	{% set block_events = attendance_events_by_block[blk] ... %}	list	route — REWIRED_READ from canonical attendance_sessions
77	{{ format_utc_iso(event.timestamp) }}	str	[GLOBAL]
96	{{ url_for('student.report_attendance_session_issue', attendance_session_id=event.id) }}	str	[FLASK] — REWIRED to canonical AttendanceSession lookup by `target_seat_id + class_id`
138	{{ unpaid_seconds_per_block.values()|sum }}	int	route
148	{{ "%.2f"|format(projected_pay_per_block.values()|sum) }}	str	route
154	{{ "%.2f"|format(scoped_total_earnings) }}	str	route
222	{{ attendance_start_count }}	int	route — REWIRED_READ from canonical attendance_sessions
228	{{ attendance_inactive_count }}	int	route — REWIRED_READ from canonical attendance_sessions
289	{{ "%.2f"|format(pay_rate_per_minute) }}	str	route
301	{% for label, value in pay_rate_table %}	tuple	route
319	{% if last_payroll_event %}	datetime/None	route — REWIRED_READ from payroll_events
329	{{ last_payroll_event.recorded_at.strftime(...) }}	str	route — REWIRED_READ from payroll_events
335	{{ days_since_last_payroll }}	int	route — computed through canonical_temporal_resolver
student_rent.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.rent — GET /student/rent — app/routes/student.py:2431
Variables from route:

Variable	Type	Purpose
student	Seat	Current seat (aliased from seat)
settings	RentSettings	Rent settings for the class
student_blocks	list[str]	Block list
period_status	dict	Rent status per period
current_block	str	Current block
checking_balance	float	Checking balance
savings_balance	float	Savings balance
payment_due_date	date	Due date for current period
grace_end_date	date	Grace period end
grace_end_date_for_status	date	Grace end for display
payment_history	list	Payment history rows
rent_items	list	Items included in rent
days_until_due	`int	None`	Days until due date
Jinja expressions:

Line	Expression	Expects	Supplied By
24	{% if feature_settings.rent_enabled and feature_settings.insurance_enabled %}	bool	[CTX:feature_settings]
29	{{ url_for('student.rent') }}	str	[FLASK]
34	{{ url_for('student.student_insurance') }}	str	[FLASK]
39-42	{{ current_class_context.teacher_name }} / {{ current_class_context.block_display }}	str	[CTX:class_context]
47	{% set status = period_status[current_block] %}	dict	route
101	{{ current_block|upper }}	str	route
111	{{ "%.2f"|format(settings.rent_amount) }}	str	route
152	{{ payment_due_date.strftime('%B %d, %Y') }}	str	route
182	{{ student.display_first_name }}	str	model
199	{{ grace_end_date_for_status.strftime(...) }}	str	route
223	{{ url_for('student.rent_pay', period=current_block) }}	str	[FLASK]
224	{{ csrf_token() }}	str	[FLASK]
271	{{ settings.due_day_of_month }}	int	route
326	{% for payment in payment_history %}	list	route
student_insurance_marketplace.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.student_insurance — GET /student/insurance — app/routes/student.py:1470 (currently abort(404))
Variables from route (as designed, currently unreachable):

Variable	Type	Purpose
my_policies	list[Enrollment]	Student's active insurance enrollments
available_policies	list[InsurancePolicy]	Ungrouped available policies
tier_groups	dict	Tiered policy groups
my_claims	list[InsuranceClaim]	Student's claims
can_purchase	dict[int, bool]	Purchasability per policy
enrolled_tiers	set	Tier IDs already enrolled
repurchase_blocks	dict[int, int]	Days until repurchase allowed
now	datetime	Current time
Jinja expressions:

Line	Expression	Expects	Supplied By
24	{% if feature_settings.rent_enabled and feature_settings.insurance_enabled %}	bool	[CTX:feature_settings]
39-42	{{ current_class_context.teacher_name }} / {{ current_class_context.block_display }}	str	[CTX:class_context]
54	{{ my_policies|length }}	int	route
68	{{ my_claims|length }}	int	route
84	{{ enrollment.policy.description | markdown }}	Markup	[FILTER]
91	{{ "%.2f"|format(enrollment.policy.premium) }}	str	model
153	{% if enrollment.coverage_start_date > now %}	bool	route
160	{{ url_for('student.file_claim', policy_id=enrollment.policy.id) }}	str	[FLASK]
165	{{ url_for('student.view_policy', enrollment_id=enrollment.id) }}	str	[FLASK]
169	{{ url_for('student.cancel_insurance', enrollment_id=enrollment.id) }}	str	[FLASK]
171	{{ csrf_token() }}	str	[FLASK]
302	{{ (policy.description or '...') | markdown }}	Markup	[FILTER]
357	{{ url_for('student.purchase_insurance', policy_id=policy.id) }}	str	[FLASK]
student_file_claim.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.file_claim — GET|POST /student/insurance/claim/<int:policy_id> — app/routes/student.py:1494 (currently abort(404))
Variables from route (as designed):

Variable	Type	Purpose
form	FlaskForm	Claim submission form
policy	InsurancePolicy	The policy being claimed against
enrollment	Enrollment	Student's enrollment
contract_title	str	Policy title
contract_description	str	Policy description
claim_type	str	"transaction_monetary", "non_monetary", or "legacy_monetary"
contract_claim_time_limit_days	int	Days to file claim
contract_max_claim_amount	`float	None`	Max claim amount
contract_max_claims_count	`int	None`	Max claims per period
contract_max_claims_period	str	Period for claim limit
eligible_transactions	list	Eligible transactions (TXN type)
claims_this_period	list	Claims in current period
remaining_period_cap	`float	None`	Remaining cap
errors	list[str]	Validation errors
now	datetime	Current time
Jinja expressions:

Line	Expression	Expects	Supplied By
23	{{ contract_title }}	str	route
38	{{ url_for('student.file_claim', policy_id=policy.id) }}	str	[FLASK]
39	{{ form.hidden_tag() }}	Markup	WTForms
40	{% set is_transaction = claim_type == 'transaction_monetary' %}	bool	route
52	{{ form.transaction_id.label(...) }} / {{ form.transaction_id(...) }}	Markup	WTForms
79	{{ form.description.label(...) }} / {{ form.description(...) }}	Markup	WTForms
135	{{ url_for('student.student_insurance') }}	str	[FLASK]
149	{{ contract_description | markdown }}	Markup	[FILTER]
179	{{ enrollment.coverage_start_date.strftime(...) }}	str	model
student_view_policy.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.view_policy — GET /student/insurance/policy/<int:enrollment_id> — app/routes/student.py:1501 (currently abort(404))
Variables from route (as designed):

Variable	Type	Purpose
student	Seat	Current seat
enrollment	Enrollment	Insurance enrollment with contract fields
claims	list[InsuranceClaim]	Claims for this policy
now	datetime	Current time
Jinja expressions:

Line	Expression	Expects	Supplied By
4	{% set page_title = enrollment.contract_title %}	str	route
19	{{ enrollment.contract_description | markdown }}	Markup	[FILTER]
25	{{ "%.2f"|format(enrollment.policy.premium) }}	str	model
27	{{ 'Enabled' if enrollment.policy.autopay else 'Disabled' }}	str	model
37	{{ enrollment.purchase_date.strftime(...) }}	str	model
69	{{ enrollment.contract_max_claim_amount }}	float	model
87	{{ enrollment.next_payment_due.strftime(...) }}	str	model
119	{{ claim.incident_date.strftime(...) }}	str	model
189-196	{% set in_waiting_period = ... %}	bool	route
196	{{ url_for('student.file_claim', policy_id=enrollment.policy.id) }}	str	[FLASK]
248	{{ url_for('student.cancel_insurance', enrollment_id=enrollment.id) }}	str	[FLASK]
249	{{ csrf_token() }}	str	[FLASK]
student_account_claim.html
Extends: None (standalone HTML document)
Route(s): student.claim_account — GET|POST /student/claim-account — app/routes/student.py:463
Variables from route:

Variable	Type	Purpose
form	StudentClaimAccountForm	Claim form (join_code, first_name, last_name, dedupe_code)
Jinja expressions:

Line	Expression	Expects	Supplied By
10	{{ static_url('css/tokens.css') }}	str	[GLOBAL]
11	{{ static_url('css/style.css') }}	str	[GLOBAL]
145	{% with messages = get_flashed_messages(category_filter=["claim"]) %}	list	[FLASK]
156	{{ form.hidden_tag() }}	Markup	WTForms
160	{{ form.join_code(...) }}	Markup	WTForms
162	{% for error in form.join_code.errors %}	list	WTForms
169	{{ form.first_name(...) }}	Markup	WTForms
177	{{ form.last_name(...) }}	Markup	WTForms
185	{{ form.dedupe_code(...) }}	Markup	WTForms
197	{{ url_for('student.login') }}	str	[FLASK]
200	{{ url_for('main.privacy') }}	str	[FLASK]
202	{{ url_for('main.district') }}	str	[FLASK]
204	{{ url_for('main.terms') }}	str	[FLASK]
209	{{ static_url('images/logo_student_transparent_512.png') }}	str	[GLOBAL]
student_add_class.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.add_class — GET|POST /student/add-class — app/routes/student.py:658
Variables from route:

Variable	Type	Purpose
form	WTForm	Add class form (join_code, first_name, last_name)
Jinja expressions:

Line	Expression	Expects	Supplied By
24	{% with messages = get_flashed_messages(with_categories=true) %}	list	[FLASK]
36	{{ form.hidden_tag() }}	Markup	WTForms
43	{{ form.join_code(...) }}	Markup	WTForms
57	{{ form.first_name(...) }}	Markup	WTForms
71	{{ form.last_name(...) }}	Markup	WTForms
85	{{ url_for('student.dashboard') }}	str	[FLASK]
student_complete_profile.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): No active route found. Template exists but no route renders it.
Variables from route (inferred from template):

Variable	Type	Purpose
form	obj	Form with first_name, last_name, dob_day, dob_year data attrs
student	Seat	Current student
confirmed	bool	Whether in confirmation step
confirm_data	dict	Data for confirmation step (first_name, last_name, dob_display, dob_month, dob_day, dob_year)
max_birth_year	int	Max allowed birth year
Jinja expressions:

Line	Expression	Expects	Supplied By
20	{% if not confirmed %}	bool	route
22	{{ url_for('student.complete_profile') }}	str	[FLASK]
23	{{ csrf_token() }}	str	[FLASK]
30	{{ form.first_name.data or student.display_first_name }}	str	route
37	{{ form.last_name.data or '' }}	str	route
71	{{ max_birth_year or 2020 }}	int	route
97	{{ confirm_data.first_name }}	str	route
99	{{ confirm_data.last_name }}	str	route
103	{{ confirm_data.dob_display }}	str	route
108	{{ url_for('student.complete_profile') }}	str	[FLASK]
109	{{ csrf_token() }}	str	[FLASK]
152	{{ max_birth_year or 2020 }}	int	route
student_create_username.html
Extends: None (standalone HTML document)
Route(s): student.create_username — GET|POST /student/create-username — app/routes/student.py:569
Variables from route:

Variable	Type	Purpose
theme_prompt	str	Theme prompt for username word (from session)
form	WTForm	Form with write_in_word, submit, hidden_tag
Jinja expressions:

Line	Expression	Expects	Supplied By
13	{{ static_url('manifest.json') }}	str	[GLOBAL]
14	{{ static_url('images/icon-192.png') }}	str	[GLOBAL]
18	{{ static_url('css/tokens.css') }}	str	[GLOBAL]
19	{{ static_url('css/style.css') }}	str	[GLOBAL]
172	{% with messages = get_flashed_messages(category_filter=["setup"]) %}	list	[FLASK]
187	{{ theme_prompt }}	str	route
203	{{ form.hidden_tag() }}	Markup	WTForms
207	{{ form.write_in_word(...) }}	Markup	WTForms
213	{{ form.submit(...) }}	Markup	WTForms
217	{{ url_for('main.privacy') }}	str	[FLASK]
219	{{ url_for('main.district') }}	str	[FLASK]
221	{{ url_for('main.terms') }}	str	[FLASK]
225	{{ static_url('images/logo_student_transparent_512.png') }}	str	[GLOBAL]
student_pin_setup.html
Extends: None (standalone HTML document)
Route(s): student.setup_pin_passphrase — GET|POST /student/setup-pin-passphrase — app/routes/student.py:600
Variables from route:

Variable	Type	Purpose
username	str	Generated username (from session)
form	WTForm	Form with pin, passphrase, submit, hidden_tag
Jinja expressions:

Line	Expression	Expects	Supplied By
12	{{ static_url('manifest.json') }}	str	[GLOBAL]
13	{{ static_url('images/icon-192.png') }}	str	[GLOBAL]
18	{{ static_url('css/tokens.css') }}	str	[GLOBAL]
19	{{ static_url('css/style.css') }}	str	[GLOBAL]
239	{{ username }}	str	route
244	{% with messages = get_flashed_messages(category_filter=['setup']) %}	list	[FLASK]
267	{{ form.hidden_tag() }}	Markup	WTForms
272	{{ form.pin(...) }}	Markup	WTForms
281	{{ form.passphrase(...) }}	Markup	WTForms
293	{{ form.submit(...) }}	Markup	WTForms
299	{{ url_for('main.privacy') }}	str	[FLASK]
301	{{ url_for('main.district') }}	str	[FLASK]
303	{{ url_for('main.terms') }}	str	[FLASK]
307	{{ static_url('images/logo_student_transparent_512.png') }}	str	[GLOBAL]
student_setup_complete.html
Extends: None (standalone HTML document)
Route(s): student.setup_complete — GET /student/setup-complete — app/routes/student.py:3168
Variables from route:

Variable	Type	Purpose
student_name	str	Student's first name (from IdentityProfile or empty)
Jinja expressions:

Line	Expression	Expects	Supplied By
12	{{ static_url('css/tokens.css') }}	str	[GLOBAL]
13	{{ static_url('css/style.css') }}	str	[GLOBAL]
78	{{ student_name }}	str	route
80	{{ url_for('student.dashboard') }}	str	[FLASK]
student_select_class_context.html
Extends: None (standalone HTML document)
Route(s): student.select_class_context — GET|POST /student/select-class-context — app/routes/student.py:3042
Variables from route:

Variable	Type	Purpose
class_options	list[dict]	Available classes with class_id, join_code, class_identifier, class_name
Jinja expressions:

Line	Expression	Expects	Supplied By
7	{{ url_for('static', filename='css/style.css') }}	str	[FLASK]
18	{% with messages = get_flashed_messages(with_categories=true) %}	list	[FLASK]
26	{{ url_for('student.select_class_context') }}	str	[FLASK]
27	{{ csrf_token() }}	str	[FLASK]
33	{{ option.class_id }}	str	route
34	{{ option.join_code }} - {{ option.class_identifier }}	str	route
45	{{ option.class_name }}	str	route
student_help_support.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): No active route. The student.help_support route at line 3179 renders student_help_support_new.html instead. This template is legacy/unused.
Variables from route (as designed in template):

Variable	Type	Purpose
help_content	dict	With keys how_to, troubleshooting (lists of articles)
my_reports	list	Student's bug reports
Jinja expressions:

Line	Expression	Expects	Supplied By
40	{% for article in help_content.how_to %}	list	route
49	{{ article.content | safe }}	Markup	route
67	{% for article in help_content.troubleshooting %}	list	route
100	{{ url_for('student.help_support') }}	str	[FLASK]
101	{{ csrf_token() }}	str	[FLASK]
177	{{ format_utc_iso(report.submitted_at) }}	str	[GLOBAL]
195	{{ "%.2f"|format(report.reward_amount) }}	str	model
student_help_support_new.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.help_support — GET /student/help-support — app/routes/student.py:3179
Variables from route:

Variable	Type	Purpose
current_page	str	"help"
page_title	str	"Help & Support"
my_issues	list[Issue]	Student's submitted issues
help_content	dict	With keys how_to, troubleshooting
format_utc_iso	callable	UTC ISO formatter
Jinja expressions:

Line	Expression	Expects	Supplied By
39	{% for article in help_content.how_to %}	list	route
48	{{ article.content | safe }}	Markup	route
66	{% for article in help_content.troubleshooting %}	list	route
105	{{ url_for('student.submit_general_issue') }}	str	[FLASK]
166	{{ issue.category.name }}	str	model
167	{{ issue.related_transaction_id }}	int	model
179	{{ issue.get_student_visible_status() }}	str	model method
183	{{ issue.student_explanation[:150] }}	str	model
188	{{ format_utc_iso(issue.submitted_at) }}	str	route / [GLOBAL]
student_submit_issue.html
Extends: layout_student.html ([LAYOUT:student])
Route(s):

student.submit_general_issue — GET|POST /student/help-support/submit-issue — app/routes/student.py:3207
student.report_transaction_issue — GET|POST /student/help-support/transaction/<int:transaction_id>/report — app/routes/student.py:3262
student.report_attendance_session_issue — GET|POST /student/help-support/attendance-session/<int:attendance_session_id>/report — app/routes/student.py — REWIRED to canonical AttendanceSession lookup by `target_seat_id + class_id`; legacy `tap_event` route terminology removed
Variables from route:

Variable	Type	Purpose
current_page	str	"help"
page_title	str	"Report an Issue" or similar
form	StudentIssueSubmissionForm	WTForms issue form
issue_type	str	"general", "transaction", or "attendance"
transaction	`Transaction	None`	Related transaction (if transaction type)
show_recent_error_option	bool	Whether to show "include recent error" checkbox
Jinja expressions:

Line	Expression	Expects	Supplied By
26	{{ url_for('student.help_support') }}	str	[FLASK]
41	{% if issue_type == 'transaction' and transaction %}	str, obj	route
47	{{ "%.2f"|format(transaction.amount) }}	str	route
48	{{ transaction.account_type|title }}	str	model
49	{{ transaction.description }}	str	model
52	{{ format_utc_iso(transaction.timestamp) }}	str	[GLOBAL]
77	{{ form.csrf_token }}	Markup	WTForms
81	{{ form.category_id.label(...) }}	Markup	WTForms
82	{{ form.category_id(...) }}	Markup	WTForms
93	{{ form.explanation.label(...) }}	Markup	WTForms
94	{{ form.explanation(...) }}	Markup	WTForms
107	{{ form.expected_outcome.label(...) }}	Markup	WTForms
108	{{ form.expected_outcome(...) }}	Markup	WTForms
120	{% if show_recent_error_option %}	bool	route
136	{{ form.submit(...) }}	Markup	WTForms
155	{{ form.explanation.id }}	str	WTForms
157	{{ form.expected_outcome.id }}	str	WTForms
student_verify_recovery.html
Extends: layout_student.html ([LAYOUT:student])
Route(s): student.verify_recovery — GET|POST /student/verify-recovery/<int:code_id> — app/routes/student.py:3392
Variables from route:

Variable	Type	Purpose
recovery_code	StudentRecoveryCode	The recovery code object
verified	bool	Whether verification succeeded
generated_code	`str	None`	The generated 6-digit code (only on success)
Jinja expressions:

Line	Expression	Expects	Supplied By
10	{% if verified %}	bool	route
28	{{ generated_code }}	str	route
38	{{ url_for('student.dashboard') }}	str	[FLASK]
63	{{ recovery_code.recovery_request.expires_at.strftime(...) }}	str	model
67	{{ csrf_token() }}	str	[FLASK]
89	{{ url_for('student.dashboard') }}	str	[FLASK]
student/recovery/layout.html
Extends: None (standalone HTML document; serves as base layout for recovery sub-templates)
Route(s): Not rendered directly. Extended by landing.html, account_lookup.html, reset_form.html, identity_update.html.
Variables from route: None directly; child templates supply content.

Jinja expressions:

Line	Expression	Expects	Supplied By
5	{% block title %}Account Recovery{% endblock %}	str	child
9	{{ static_url('css/tokens.css') }}	str	[GLOBAL]
10	{{ static_url('css/style.css') }}	str	[GLOBAL]
117	{{ url_for('student.login') }}	str	[FLASK]
122	{% block header %}Recover Account{% endblock %}	str	child
123	{% block subheader %}...{% endblock %}	str	child
126	{% with messages = get_flashed_messages(with_categories=true) %}	list	[FLASK]
139	{% block content %}{% endblock %}	Markup	child
142	{{ static_url('images/logo_student_transparent_512.png') }}	str	[GLOBAL]
student/recovery/landing.html
Extends: student/recovery/layout.html
Route(s): recovery.landing — GET /recovery/ — app/routes/recovery.py:83 (redirects to account_lookup)
Variables from route: None (this route redirects; template is not actually rendered).

Jinja expressions:

Line	Expression	Expects	Supplied By
10	{{ url_for('recovery.account_lookup') }}	str	[FLASK]
student/recovery/account_lookup.html
Extends: student/recovery/layout.html
Route(s): recovery.account_lookup — GET|POST /recovery/lookup — app/routes/recovery.py:89
Variables from route: None (GET renders with no extra context).

Jinja expressions:

Line	Expression	Expects	Supplied By
9	{{ csrf_token() }}	str	[FLASK]
student/recovery/reset_form.html
Extends: student/recovery/layout.html
Route(s): No active route renders this template. The recovery flow redirects to student.create_username instead of rendering a reset form. This template is legacy/unused.
Variables from route: None.

Jinja expressions:

Line	Expression	Expects	Supplied By
9	{{ csrf_token() }}	str	[FLASK]
student/recovery/identity_update.html
Extends: student/recovery/layout.html
Route(s): No active route renders this template. This is a stub that auto-redirects to account_lookup.
Variables from route: None.

Jinja expressions:

Line	Expression	Expects	Supplied By
11	{{ url_for('recovery.account_lookup') }}	str	[FLASK]
12	{{ url_for('recovery.account_lookup') }}	str	[FLASK]
Summary of orphaned/unused templates
student_complete_profile.html -- no route renders it
student_help_support.html -- legacy; help_support() route renders student_help_support_new.html instead
student/recovery/landing.html -- route exists but always redirects before rendering
student/recovery/reset_form.html -- no route renders it (recovery flow uses create_username instead)
student/recovery/identity_update.html -- no route renders it; self-redirects via JS
