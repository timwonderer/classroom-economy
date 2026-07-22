# Admin and Analytics Template & Route Audit

**Last Updated:** 2026-07-20  
**Scope:** Admin templates (admin + analytics blueprints)  
**Total Templates Audited:** 12

---

## Template Audit by Page

### `admin_account_delete.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** `admin.account_delete` — `GET, POST /admin/account-delete` — [`app/routes/admin.py:9504-9507`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py#L9504-L9507)

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `current_page` | `str` | Layout/navigation state |
| `admin_username` | `str` | Used for the hidden gate phrase and DOM data attribute |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 26 | `{{ url_for('admin.account_delete') }}` | Endpoint `admin.account_delete` | [FLASK] |
| 26 | `{{ admin_username }}` | Teacher username string | Route kwarg `admin_username` |
| 27 | `{{ csrf_token() }}` | CSRF token string | [FLASK] `csrf_token()` |
| 95 | `deletionRequestForm.dataset.adminUsername` | `data-admin-username` attribute from line 26 | Template-rendered DOM attribute |
| 95 | `` `CONFIRM DELETE ${adminUsername} ACCOUNT`.toUpperCase() `` | JS string built from username | Derived from `admin_username` |

---

### `admin_analytics_dashboard.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** `analytics.dashboard` — `GET /admin/analytics/` — [`app/routes/analytics.py:192-194`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/analytics.py#L192-L194)

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `snapshot` | analytics snapshot object | Main dashboard metrics |
| `alerts` | `list` | Alert set used to build `alert_lookup` |
| `events` | `list` | Recent analytics events |
| `window_type` | `str` | Selected time window |
| `window_start` | `datetime` | Window start label |
| `window_end` | `datetime` | Window end label |
| `join_code` | `str` | Current class display code |
| `available_classes` | `list` | Class selector options |
| `current_class_label` | `str` | Active class label |
| `current_page` | `str` | Layout/navigation state |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 8 | `{{ url_for('analytics.dashboard', window='week') }}` | Endpoint `analytics.dashboard` | [FLASK] `url_for()` |
| 9 | `{% if window_type == 'week' %}...{% endif %}` | `window_type: str` | Route kwarg `window_type` |
| 12 | `{{ url_for('analytics.dashboard', window='month') }}` | Endpoint `analytics.dashboard` | [FLASK] `url_for()` |
| 13 | `{% if window_type == 'month' %}...{% endif %}` | `window_type: str` | Route kwarg `window_type` |
| 30 | `{% if not snapshot %}` | Snapshot object or falsey | Route kwarg `snapshot` |
| 43-45 | `{% if window_type == 'week' %}...{% elif window_type == 'month' %}...{% else %}...{% endif %} of {{ window_start|format_datetime('%b %d') }} to {{ window_end|format_datetime('%b %d, %Y') }}` | `window_type: str`, `window_start/window_end: datetime` | Route kwargs |
| 58 | `{{ "%.2f"|format(snapshot.cwi_value) }}` | Numeric metric | `snapshot` |
| 67 | `{% set alert_lookup = namespace(participation=None, velocity=None, cwi=None, budget=None) %}` | Template-local namespace | Template-local |
| 68-77 | `{% for alert in alerts %} ... {% if alert.alert_key == ... %}` | Alert collection | Route kwarg `alerts` |
| 108 | `{% if snapshot.participation_rate >= 70 %}...{% endif %}` | Numeric rate | `snapshot` |
| 109 | `{{ "%.1f"|format(snapshot.participation_rate) }}%` | Numeric rate | `snapshot` |
| 111 | `{{ snapshot.active_students }} of {{ snapshot.total_students }}` | Counts | `snapshot` — REWIRED_READ from canonical `AttendanceSession.target_seat_id` + `timestamp`; no legacy `seat_id`, `started_at`, or soft-delete attendance fields |
| 114-127 | `{% if snapshot.participation_trend %}...{% endif %}` | Trend string | `snapshot` |
| 132-167 | `alert_lookup.participation.*` expressions | Alert attrs (`why_it_matters`, `severity`, `what_changed`, `acknowledged_at`, `suggested_action`, `id`) | Derived from `alerts` |
| 146 | `{{ url_for('analytics.acknowledge_alert', alert_id=alert_lookup.participation.id) }}` | Endpoint `analytics.acknowledge_alert` | [FLASK] `url_for()` |
| 148 | `{{ csrf_token() }}` | CSRF token | [FLASK] `csrf_token()` |
| 183 | `{{ "%.2f"|format(snapshot.money_velocity) }}` | Numeric metric | `snapshot` |
| 186-199 | `{% if snapshot.velocity_trend %}...{% endif %}` | Trend string | `snapshot` |
| 204-239 | `alert_lookup.velocity.*` expressions | Alert attrs | Derived from `alerts` |
| 217 | `{{ url_for('analytics.acknowledge_alert', alert_id=alert_lookup.velocity.id) }}` | Endpoint `analytics.acknowledge_alert` | [FLASK] `url_for()` |
| 220 | `{{ csrf_token() }}` | CSRF token | [FLASK] `csrf_token()` |
| 256 | `{% if snapshot.cwi_deviation_within_20pct >= 80 %}...{% endif %}` | Numeric metric | `snapshot` |
| 257 | `{{ "%.1f"|format(snapshot.cwi_deviation_within_20pct) }}%` | Numeric metric | `snapshot` |
| 261-274 | `{% if snapshot.balance_trend %}...{% endif %}` | Trend string | `snapshot` |
| 279-314 | `alert_lookup.cwi.*` expressions | Alert attrs | Derived from `alerts` |
| 293 | `{{ url_for('analytics.acknowledge_alert', alert_id=alert_lookup.cwi.id) }}` | Endpoint `analytics.acknowledge_alert` | [FLASK] `url_for()` |
| 295 | `{{ csrf_token() }}` | CSRF token | [FLASK] `csrf_token()` |
| 331 | `{% if snapshot.budget_survival_pass_rate >= 80 %}...{% endif %}` | Numeric metric | `snapshot` |
| 332 | `{{ "%.1f"|format(snapshot.budget_survival_pass_rate) }}%` | Numeric metric | `snapshot` |
| 340-375 | `alert_lookup.budget.*` expressions | Alert attrs | Derived from `alerts` |
| 354 | `{{ url_for('analytics.acknowledge_alert', alert_id=alert_lookup.budget.id) }}` | Endpoint `analytics.acknowledge_alert` | [FLASK] `url_for()` |
| 356 | `{{ csrf_token() }}` | CSRF token | [FLASK] `csrf_token()` |
| 390 | `{% if events %}` | Event list | Route kwarg `events` |
| 399-414 | `event.*` expressions (`description`, `event_date`, `old_value`, `new_value`, `event_type`) | Event attrs | Route kwarg `events` |
| 405 | `{{ event.event_date|format_datetime('%b %d, %Y at %I:%M %p') }}` | Datetime | `event.event_date` |
| 417 | `{{ url_for('analytics.events') }}` | Endpoint `analytics.events` | [FLASK] `url_for()` |
| 542 | `{{ url_for('docs.view_doc', doc_path='user-guides/features/analytics/interpreting-analytics') }}` | Endpoint `docs.view_doc` | [FLASK] `url_for()` |

---

### `admin_analytics_events.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** `analytics.events` — `GET /admin/analytics/events` — [`app/routes/analytics.py:377-379`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/analytics.py#L377-L379)

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `events` | `list` | Event rows for the table |
| `join_code` | `str` | Current class display code |
| `available_classes` | `list` | Class selector options |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 7 | `{% if available_classes %}` | `available_classes: list` | Route kwarg `available_classes` |
| 13 | `{{ url_for('analytics.events') }}` | Endpoint `analytics.events` | [FLASK] `url_for()` |
| 15-19 | `{% for class_option in available_classes %} ... {{ class_option.class_id }} ... {{ class_option.label }} ... {{ class_option.block }}` | Objects/dicts with `class_id`, `label`, `block` | Route kwarg `available_classes` |
| 16 | `{% if class_option.class_id and class_option.class_id == session.get('current_class_id') %}` | Session current class | [FLASK] `session` |
| 23 | `{{ url_for('analytics.dashboard') }}` | Endpoint `analytics.dashboard` | [FLASK] `url_for()` |
| 43 | `{% if events %}` | `events: list` | Route kwarg `events` |
| 59-89 | `event.*` expressions | Event attrs (`event_date`, `event_type`, `description`, `old_value`, `new_value`, `affected_students`) | Route kwarg `events` |
| 62-63 | `{{ event.event_date|format_datetime('%b %d, %Y') }}` / `{{ event.event_date|format_datetime('%I:%M %p') }}` | Datetime | `event.event_date` |
| 67-72 | `{% if event.event_type == ... %}` | Event type string | `event.event_type` |
| 73 | `{{ event.event_type|replace('_', ' ')|title }}` | Event type string | `event.event_type` |
| 87 | `{{ 's' if event.affected_students != 1 else '' }}` | Count | `event.affected_students` |
| 139 | `{{ url_for('analytics.events') }}` | Endpoint `analytics.events` | [FLASK] `url_for()` |
| 146 | `{{ url_for("admin.set_current_class") }}` | Endpoint `admin.set_current_class` | [FLASK] `url_for()` |

---

### `admin_analytics_student_detail.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** `analytics.student_drill_down` — `GET /admin/analytics/student/<int:student_id>` — [`app/routes/analytics.py:429-431`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/analytics.py#L429-L431)

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `student` | seat/student object | Selected student |
| `current_balance` | `number` | Current balance metric |
| `expected_balance` | `number` | Expected balance metric |
| `deviation` | `number` | Percent deviation |
| `cwi` | `number` | Composite Weekly Income |
| `recent_transactions` | `list` | Recent transactions |
| `join_code` | `str` | Current class display code |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 2 | `{{ student.name }}` | `student.name: str` | Route kwarg `student` |
| 6 | `{{ url_for('analytics.dashboard') }}` | Endpoint `analytics.dashboard` | [FLASK] `url_for()` |
| 18 | `{{ student.name | e }}` | Student name | `student` |
| 31-32 | `{% if current_balance >= 0 %}...{% endif %}` / `{{ "%.2f"|format(current_balance) }}` | Numeric balance | Route kwarg `current_balance` |
| 45 | `{{ "%.2f"|format(expected_balance) }}` | Numeric balance | Route kwarg `expected_balance` |
| 57-61 | `{% if deviation|abs <= ... %}` / `{{ "%.1f"|format(deviation) }}%` | Numeric deviation | Route kwarg `deviation` |
| 61 | `{% if deviation > 0 %}Above{% elif deviation < 0 %}Below{% else %}At{% endif %}` | Numeric deviation | Route kwarg `deviation` |
| 71-103 | `deviation`-based conditional blocks | Numeric deviation | Route kwarg `deviation` |
| 80, 85, 95 | `{{ student.name | e }}` | Student name | `student` |
| 119 | `{{ "%.2f"|format(cwi) }}/week` | Numeric CWI | Route kwarg `cwi` |
| 130 | `{% if recent_transactions %}` | Transaction list | Route kwarg `recent_transactions` |
| 150-161 | `txn.*` expressions (`timestamp`, `description`, `amount`, `balance_after_transaction`) | Transaction attrs | Route kwarg `recent_transactions` |
| 153-154 | `{{ txn.timestamp|format_datetime('%b %d, %Y') }}` / `{{ txn.timestamp|format_datetime('%I:%M %p') }}` | Datetime | `txn.timestamp` |

---

### `admin_announcement_form.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):**
- `admin.announcement_create` — `GET, POST /admin/announcements/create` — [`app/routes/admin.py:9977-9980`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py#L9977-L9980)
- `admin.announcement_edit` — `GET, POST /admin/announcements/edit/<int:announcement_id>` — [`app/routes/admin.py:10028-10030`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py#L10028-L10030)

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `form` | WTForms form | Announcement form fields |
| `action` | `str` | `Create` or `Edit` |
| `active_join_code` | `str` | Current class join code |
| `active_class_label` | `str` | Current class label |
| `active_block` | `str`/`int` | Current class period/block |
| `teacher_block` | object | Edit-mode block/context object |
| `announcement` | announcement object | Existing announcement in edit mode |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 3 | `{% set page_title = action + " Announcement" %}` | `action: str` | Route kwarg `action` |
| 4 | `{{ action }} Announcement` | `action: str` | Route kwarg `action` |
| 15 | `{{ action }} Announcement` | `action: str` | Route kwarg `action` |
| 20 | `{{ form.csrf_token }}` | WTForms CSRF field | Route kwarg `form` |
| 22 | `{% if action == 'Create' %}` | `action: str` | Route kwarg `action` |
| 26 | `{{ active_class_label }}` | Class label string | Route kwarg `active_class_label` |
| 26 | `{% if active_block %} (Period {{ active_block }}){% endif %}` | Block value | Route kwarg `active_block` |
| 26 | `{% if active_join_code %} — {{ active_join_code }}{% endif %}` | Join code string | Route kwarg `active_join_code` |
| 28 | `{{ form.class_id }}` | Class selector/hidden field | Route kwarg `form` |
| 29 | `{% elif action == 'Edit' and teacher_block %}` | `action`, `teacher_block` | Route kwargs |
| 32 | `{{ teacher_block.get_class_label() }}` | Method call | Route kwarg `teacher_block` |
| 32 | `{{ teacher_block.block }}` | `block` attr | Route kwarg `teacher_block` |
| 38-39 | `{{ form.title.label(...) }}` / `{{ form.title(...) }}` | WTForms field | Route kwarg `form` |
| 40-42 | `{% if form.title.errors %} ... {% for error in form.title.errors %}` | Error list | Route kwarg `form` |
| 48-54 | `form.message.*` | WTForms field/errors | Route kwarg `form` |
| 59-65 | `form.priority.*` | WTForms field/errors | Route kwarg `form` |
| 76-82 | `form.expires_at.*` | WTForms field/errors | Route kwarg `form` |
| 88-89 | `form.is_active(...)` / `form.is_active.label(...)` | WTForms field | Route kwarg `form` |
| 95 | `{{ url_for('admin.announcements') }}` | Endpoint `admin.announcements` | [FLASK] `url_for()` |
| 98 | `{{ form.submit(...) }}` | WTForms submit field | Route kwarg `form` |
| 104 | `{% if action == 'Edit' and announcement %}` | `action`, `announcement` | Route kwargs |
| 110-112 | `announcement.get_priority_class()`, `announcement.get_priority_icon()`, `announcement.title`, `announcement.message` | Announcement object attrs/methods | Route kwarg `announcement` |

---

### `admin_announcements.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** `admin.announcements` — `GET /admin/announcements` — [`app/routes/admin.py:9944-9946`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py#L9944-L9946)

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `announcements` | `list` | Class announcement rows |
| `active_class_label` | `str` | Current class label |
| `active_join_code` | `str` | Current class join code |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 2 | `{% set current_page = "announcements" %}` | Layout nav state | Template-local |
| 3 | `{% set page_title = "Class Announcements" %}` | Layout title state | Template-local |
| 4 | `{% block title %}Class Announcements{% endblock %}` | Layout title block | Template-local |
| 56 | `{{ url_for('admin.announcement_create') }}` | Endpoint `admin.announcement_create` | [FLASK] `url_for()` |
| 63 | `{{ active_class_label }}` | Class label string | Route kwarg `active_class_label` |
| 63 | `{% if active_join_code %} ... {{ active_join_code }} ... {% endif %}` | Join code string | Route kwarg `active_join_code` |
| 66 | `{% if announcements %}` | Announcement list | Route kwarg `announcements` |
| 68-107 | `announcement.*` expressions (`is_active`, `priority`, `get_priority_class()`, `get_priority_icon()`, `title`, `id`, `is_expired()`, `message`, `created_at`, `expires_at`) | Announcement attrs/methods | Route kwarg `announcements` |
| 84 | `toggleAnnouncement({{ announcement.id }})` | Announcement id | `announcement` |
| 89 | `{{ url_for('admin.announcement_edit', announcement_id=announcement.id) }}` | Endpoint `admin.announcement_edit` | [FLASK] `url_for()` |
| 94 | `deleteAnnouncement({{ announcement.id }}, '{{ announcement.title }}')` | Announcement id/title | `announcement` |
| 100 | `{{ announcement.message|nl2br|safe }}` | Announcement message string | `announcement` |
| 102 | `{{ announcement.created_at.strftime('%b %d, %Y at %I:%M %p') }}` | Datetime | `announcement.created_at` |
| 105 | `{{ announcement.expires_at.strftime('%b %d, %Y') }}` | Datetime | `announcement.expires_at` |
| 122 | `{{ csrf_token() }}` | CSRF token | [FLASK] `csrf_token()` |
| 134 | `{{ csrf_token() }}` | CSRF token for JS request | [FLASK] `csrf_token()` |

---

### `admin_attendance_log.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** `admin.attendance_log` — `GET /admin/attendance-log` — [`app/routes/admin.py:8236-8238`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py#L8236-L8238)
**PROD status:** REWIRED_READ — Resolved 2026-07-21. The page no longer calls legacy block tap-setting endpoints. `/api/attendance/history` reads canonical append-only `AttendanceSession` fields (`target_seat_id`, `timestamp`, `status`, `reason_code`) and uses `canonical_temporal_resolver` for class-local date filters.

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `blocks` | `list` | Block list |
| `class_labels_by_block` | `dict` | Block-to-label lookup |
| `current_page` | `str` | Layout/navigation state |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 104 | `{{ url_for('admin.students') }}` | Endpoint `admin.students` | [FLASK] `url_for()` |
| 129 | `{{ url_for('admin.students') }}` | Endpoint `admin.students` | [FLASK] `url_for()` |
| 381 | `fetch(\`/api/attendance/history?...`)` | JSON endpoint | [API] canonical attendance history |

---

### `admin_backfill_join_codes.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** No `render_template('admin_backfill_join_codes.html')` hit found in `app/routes/*.py`

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `students` | `list` | Student rows shown in the form |
| `available_blocks` | `list` | Period/block options |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 32 | `{{ csrf_token() }}` | CSRF token | [FLASK] `csrf_token()` |
| 43-66 | `{% for student in students %} ... {% for block in available_blocks %}` | Student/block collections | Missing route context |
| 46 | `{{ student.full_name }}` | Student name string | Loop variable `student` |
| 48 | `{{ student.username }}` | Username string | Loop variable `student` |
| 52 | `name="student_{{ student.id }}_block"` | Student id | Loop variable `student` |
| 55 | `aria-label="Assign {{ student.display_first_name }} to a period"` | Display name | Loop variable `student` |
| 59 | `{{ block }}` | Block value | Loop variable `block` |
| 59 | `{% if student.block == block %}selected{% endif %}` | Student/block compare | Loop variables `student`, `block` |
| 75 | `{{ students|length }}` | Sequence length | `students` |

---

### `admin_banking.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** `admin.banking` — `GET /admin/banking` — [`app/routes/admin.py:9200-9202`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py#L9200-L9202)

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `settings` | banking settings object | Banking config display/form state |
| `form` | WTForms form | Banking settings form |
| `transactions` | `list` | Transaction rows |
| `total_checking` | `number` | Sum of checking balances |
| `total_savings` | `number` | Sum of savings balances |
| `total_deposits` | `number` | Sum of deposits |
| `students_with_savings` | `number` | Count of students with savings |
| `total_students` | `number` | Total student count |
| `average_savings_balance` | `number` | Average savings balance |
| `blocks` | `list` | Blocks for filters/context |
| `class_labels_by_block` | `dict` | Block label lookup |
| `join_codes_by_block` | `dict` | Block join-code lookup |
| `transaction_types` | `list` | Transaction type filter options |
| `page` | `int` | Current pagination page |
| `total_pages` | `int` | Pagination total pages |
| `total_transactions` | `int` | Total matched transactions |
| `current_page` | `str` | Layout/navigation state |
| `format_utc_iso` | function | Timestamp helper |
| `teacher_blocks` | `list` | Teacher-owned block list |
| `selected_feature_scope` | `dict`/object | Active banking scope |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 2 | `{% set page_title = "Banking Management" %}` | Layout title state | Template-local |
| 3 | `{% set current_page = "banking" %}` | Layout nav state | Template-local |
| 173 | `{{ "%.2f"|format(total_checking|default(0)) }}` | Number | Route kwarg `total_checking` |
| 177 | `{{ "%.2f"|format(total_savings|default(0)) }}` | Number | Route kwarg `total_savings` |
| 181 | `{{ "%.2f"|format(total_deposits|default(0)) }}` | Number | Route kwarg `total_deposits` |
| 185 | `{{ students_with_savings|default(0) }}/{{ total_students|default(0) }}` | Counts | Route kwargs |
| 200 | `{% if settings %}` | Settings object | Route kwarg `settings` |
| 203 | `{{ "%.2f"|format(settings.savings_apy) }}%` | Settings field | `settings` |
| 206 | `{{ "%.2f"|format(settings.savings_monthly_rate) }}%` | Settings field | `settings` |
| 209-224 | `settings.interest_schedule_type`, `settings.interest_schedule_cycle_days`, `settings.overdraft_protection_enabled`, `settings.overdraft_fee_enabled`, `settings.overdraft_fee_type` | Settings attrs | `settings` |
| 242 | `{% if transactions %}` | Transaction list | Route kwarg `transactions` |
| 257 | `{% for tx in transactions[:10] %}` | Transaction slice | Route kwarg `transactions` |
| 260-286 | `tx.*` expressions (`timestamp`, `actor_public_id`, `student_name`, `student_block`, `type`, `account_type`, `amount`, `description`, `is_void`) | Transaction attrs | Route kwarg `transactions` |
| 261, 386 | `{{ format_utc_iso(tx.timestamp) }}` | Timestamp formatter | Route kwarg `format_utc_iso` / shared [GLOBAL] |
| 267, 392 | `{{ student_detail_url(tx.actor_public_id) }}` | Student detail URL helper | Shared [GLOBAL] `student_detail_url` |
| 271, 396 | `{{ class_labels_by_block.get(tx.student_block, tx.student_block) if tx.student_block else 'N/A' }}` | Dict lookup | Route kwarg `class_labels_by_block` |
| 312 | `{{ url_for('admin.banking') }}` | Endpoint `admin.banking` | [FLASK] `url_for()` |
| 318 | `request.args.get('account')` | Query params | [FLASK] `request` |
| 320 | `request.args.get('account')` | Query params | [FLASK] `request` |
| 328-329 | `{% for tx_type in transaction_types %}` / `{{ tx_type }}` | Transaction type strings | Route kwarg `transaction_types` |
| 337, 342, 347 | `request.args.get(...)` | Query params | [FLASK] `request` |
| 355 | `{{ url_for('admin.banking') }}` | Endpoint `admin.banking` | [FLASK] `url_for()` |
| 359 | `{{ transactions|length }}` | Sequence length | Route kwarg `transactions` |
| 381 | `{% if transactions %}` | Transaction list | Route kwarg `transactions` |
| 382 | `{% for tx in transactions %}` | Transaction loop | Route kwarg `transactions` |
| 383-421 | `tx.*` expressions | Transaction attrs | Route kwarg `transactions` |
| 385-386 | `{{ format_utc_iso(tx.timestamp) }}` | Timestamp formatter | Shared/route helper |
| 392 | `{{ student_detail_url(tx.actor_public_id) }}` | Student detail URL helper | Shared [GLOBAL] `student_detail_url` |
| 396 | `class_labels_by_block.get(...)` | Dict lookup | Route kwarg `class_labels_by_block` |
| 417 | `onclick="voidTransaction({{ tx.id }})"` | Transaction id | `tx` |
| 437 | `{% if total_pages > 1 %}` | Pagination state | Route kwarg `total_pages` |
| 441 | `{% if page <= 1 %}` | Current page | Route kwarg `page` |
| 443 | `{{ url_for('admin.banking', page=page-1, student=request.args.get('student', ''), account=request.args.get('account', ''), type=request.args.get('type', ''), start_date=request.args.get('start_date', ''), end_date=request.args.get('end_date', '')) }}` | Endpoint `admin.banking` | [FLASK] `url_for()` + `request` |
| 447 | `{% set start_page = [1, page - 2]|max %}` | `page: int` | Route kwarg `page`; shared [GLOBAL] `max` |
| 448 | `{% set end_page = [total_pages, page + 2]|min %}` | `page`, `total_pages` | Route kwargs; shared [GLOBAL] `min` |
| 460 | `{% for p in range(start_page, end_page + 1) %}` | Range values | Template-local `range` |
| 463 | `{{ url_for('admin.banking', page=p, student=request.args.get('student', ''), account=request.args.get('account', ''), type=request.args.get('type', ''), start_date=request.args.get('start_date', ''), end_date=request.args.get('end_date', '')) }}` | Endpoint `admin.banking` | [FLASK] `url_for()` + `request` |
| 473 | `{{ url_for('admin.banking', page=total_pages, student=request.args.get('student', ''), account=request.args.get('account', ''), type=request.args.get('type', ''), start_date=request.args.get('start_date', ''), end_date=request.args.get('end_date', '')) }}` | Endpoint `admin.banking` | [FLASK] `url_for()` + `request` |
| 480 | `{{ url_for('admin.banking', page=page+1, student=request.args.get('student', ''), account=request.args.get('account', ''), type=request.args.get('type', ''), start_date=request.args.get('start_date', ''), end_date=request.args.get('end_date', '')) }}` | Endpoint `admin.banking` | [FLASK] `url_for()` + `request` |
| 491 | `{{ url_for('admin.banking_settings_update') }}` | Endpoint `admin.banking_settings_update` | [FLASK] `url_for()` |
| 492 | `{{ form.hidden_tag() }}` | WTForms hidden fields | Route kwarg `form` |
| 506-515 | `settings.*` and `form.rate_input_mode.data` | Settings/form state | Route kwarg `settings`, `form` |
| 527 | `{{ form.savings_apy.data or 0 }}` | WTForms field data | Route kwarg `form` |
| 544 | `{{ form.savings_monthly_rate.data or 0 }}` | WTForms field data | Route kwarg `form` |
| 569-697 | `form.*` fields (`interest_calculation_type`, `compound_frequency`, `interest_schedule_type`, `interest_schedule_cycle_days`, `interest_payout_start_date`, `overdraft_protection_enabled`, `overdraft_fee_enabled`, `overdraft_fee_type`, `overdraft_fee_flat_amount`, `overdraft_fee_progressive_1`, `overdraft_fee_progressive_2`, `overdraft_fee_progressive_3`, `overdraft_fee_progressive_cap`, `submit`) | WTForms fields | Route kwarg `form` |
| 634, 642, 655 | `settings.overdraft_fee_enabled`, `settings.overdraft_fee_type` | Settings attrs | Route kwarg `settings` |
| 709 | `{{ average_savings_balance|default(0) }}` | Number | Route kwarg `average_savings_balance` |
| 711 | `{{ total_savings|default(0) }}` | Number | Route kwarg `total_savings` |

---

### `admin_claim_students.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** No `render_template('admin_claim_students.html')` hit found in `app/routes/*.py`

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `orphaned_students` | `list` | Unclaimed student rows |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 19 | `{{ orphaned_students|length }}` | Sequence length | Missing route context |
| 27 | `{% if orphaned_students|length == 0 %}` | Sequence length | Missing route context |
| 32 | `{{ url_for('admin.claim_students') }}` | Endpoint `admin.claim_students` | [FLASK] `url_for()` |
| 33 | `{{ csrf_token() }}` | CSRF token | [FLASK] `csrf_token()` |
| 40 | `{{ url_for('admin.claim_students') }}` | Endpoint `admin.claim_students` | [FLASK] `url_for()` |
| 41 | `{{ csrf_token() }}` | CSRF token | [FLASK] `csrf_token()` |
| 73 | `{% for student in orphaned_students %}` | Student list | Missing route context |
| 78 | `value="{{ student.id }}"` | Student id | Loop variable `student` |
| 83 | `{{ student.full_name }}` | Full name string | Loop variable `student` |
| 86 | `{{ student.block }}` | Block string | Loop variable `student` |
| 89 | `{% if student.has_completed_setup %}` | Boolean | Loop variable `student` |
| 99 | `{{ url_for('admin.dashboard') }}` | Endpoint `admin.dashboard` | [FLASK] `url_for()` |

---

### `admin_create_class.html`
**Extends:** none, standalone HTML document  
**Route(s):** `admin.onboarding` — `GET /admin/onboarding` — [`app/routes/admin.py:10302-10306`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py#L10302-L10306)

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| none | - | Route passes no `render_template()` kwargs |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 6 | `{{ csrf_token() }}` | CSRF token meta value | [FLASK] `csrf_token()` |
| 13 | `{{ static_url('css/tokens.css') }}` | Static CSS URL helper | [GLOBAL] `static_url` |
| 14 | `{{ static_url('css/style.css') }}` | Static CSS URL helper | [GLOBAL] `static_url` |
| 197-205 | `{% with messages = get_flashed_messages(with_categories=true) %} ... {% for category, message in messages %}` | Flash messages | [FLASK] `get_flashed_messages()` |
| 200 | `{{ 'danger' if category == 'error' else 'success' if category == 'success' else 'info' }}` | Flash category string | Loop variable `category` |
| 201 | `{{ message | safe }}` | Flash message text | Loop variable `message` |
| 223 | `{{ url_for('admin.download_csv_template') }}` | Endpoint `admin.download_csv_template` | [FLASK] `url_for()` |
| 230 | `{{ url_for('admin.upload_students') }}` | Endpoint `admin.upload_students` | [FLASK] `url_for()` |
| 231 | `{{ csrf_token() }}` | CSRF token | [FLASK] `csrf_token()` |

---

### `admin_dashboard.html`
**Extends:** `layout_admin.html` ([LAYOUT:admin])  
**Route(s):** `admin.dashboard` — `GET /admin/` — [`app/routes/admin.py:2573-2575`](/Users/timothychang/Documents/GitHub/classroom-economy/app/routes/admin.py#L2573-L2575)

**PROD status:** REWIRED_READ

- `recent_logs` is rewired to canonical `attendance_sessions` display rows.
- Payroll estimate/update fields are rewired to PROD `attendance_sessions` + `payroll_events` read projection.
- The former manual `admin.enforce_daily_limits` dashboard action has been intentionally removed from the template surface; daily-limit enforcement is scheduler-only, groups active PROD state by `class_id`, uses the class teacher seat as system actor, and writes the inactive row through `FEAT-PROD-001` at the exact timestamp where the daily limit is reached.
- Pending hall-pass dashboard rows are wired from ephemeral operational workflow state, not `hall_pass_logs`; dashboard rows link to the dedicated hall-pass page where reject discards without a PROD write and approve commits through `FEAT-PROD-002`.

**Variables from route:**

| Variable | Type | Purpose |
|---|---|---|
| `system_announcements` | `list` | Global/admin announcements |
| `show_recovery_setup` | `bool` | Recovery prompt flag |
| `total_students` | `number` | Student count |
| `total_balance` | `number` | Total balance |
| `avg_balance` | `number` | Average balance |
| `total_pending_actions` | `number` | Pending action count |
| `pending_redemptions_count` | `number` | Pending redemptions |
| `pending_hall_passes_count` | `number` | Pending hall passes |
| `pending_insurance_claims_count` | `number` | Pending insurance claims |
| `total_transactions_today` | `number` | Today’s transaction count |
| `total_payroll_estimate` | `number` | Payroll estimate |
| `payroll_updated_at` | `datetime` | Last payroll update |
| `next_payroll_date` | `datetime` | Next payroll date |
| `recent_redemptions` | `list` | Recent redemption requests |
| `recent_hall_passes` | `list` | Recent hall pass requests |
| `recent_insurance_claims` | `list` | Recent insurance claims |
| `recent_transactions` | `list` | Recent transactions |
| `recent_logs` | `list` | Recent attendance logs |
| `seat_profiles` | `dict` | Seat-id lookup to profile object |
| `show_insurance_tier_prompt` | `bool` | Insurance migration prompt |
| `current_page` | `str` | Layout/navigation state |

**Jinja expressions:**

| Line | Expression | Expects | Supplied By |
|---|---|---|---|
| 9 | `{{ current_admin_display_name or 'Teacher' }}` | Display name string | [CTX:current_admin] |
| 10 | `{{ url_for('admin.settings') }}` | Endpoint `admin.settings` | [FLASK] `url_for()` |
| 20 | `{% if show_recovery_setup %}` | Boolean | Route kwarg `show_recovery_setup` |
| 28 | `{{ url_for('admin.setup_recovery') }}` | Endpoint `admin.setup_recovery` | [FLASK] `url_for()` |
| 32 | `{% if show_insurance_tier_prompt %}` | Boolean | Route kwarg `show_insurance_tier_prompt` |
| 41 | `{{ url_for('admin.insurance_management') }}` | Endpoint `admin.insurance_management` | [FLASK] `url_for()` |
| 48 | `{% if system_announcements %}` | Announcement list | Route kwarg `system_announcements` |
| 49-57 | `{% for ann in system_announcements %}` / `ann.get_priority_class()`, `ann.get_priority_icon()`, `ann.title`, `ann.message` | Announcement attrs/methods | Route kwarg `system_announcements` |
| 71 | `{{ total_students }}` | Count | Route kwarg `total_students` |
| 90 | `{{ "{:,.0f}".format(total_balance) }}` | Number | Route kwarg `total_balance` |
| 104 | `{{ total_pending_actions }}` | Count | Route kwarg `total_pending_actions` |
| 105-117 | `pending_redemptions_count`, `pending_insurance_claims_count`, `pending_hall_passes_count` | Counts | Route kwargs; `pending_hall_passes_count` is REWIRED_READ from the ephemeral pending hall-pass request queue |
| 132 | `{{ format_utc_iso(next_payroll_date) }}` | Datetime helper | Shared [GLOBAL] `format_utc_iso` / route kwarg `next_payroll_date` — REWIRED_READ using canonical temporal resolver anchor |
| 133 | `{{ next_payroll_date.strftime('%b %d') }}` | Datetime | Route kwarg `next_payroll_date` — REWIRED_READ using canonical temporal resolver anchor |
| 136 | `{{ "{:,.0f}".format(total_payroll_estimate) }}` | Number | Route kwarg `total_payroll_estimate` — REWIRED_READ from PROD attendance/payroll projection |
| 137-141 | `payroll_updated_at` and `format_utc_iso(payroll_updated_at)` | Datetime | Route kwarg `payroll_updated_at` — REWIRED_READ from latest `payroll_events` anchor |
| 156 | `{{ url_for('admin.attendance_log') }}` | Endpoint `admin.attendance_log` | [FLASK] `url_for()` |
| 163 | `{{ url_for('admin.payroll') }}` | Endpoint `admin.payroll` | [FLASK] `url_for()` |
| 170 | `{{ url_for('admin.store_management') }}` | Endpoint `admin.store_management` | [FLASK] `url_for()` |
| 177 | `{{ url_for('admin.students') }}` | Endpoint `admin.students` | [FLASK] `url_for()` |
| 192 | `{{ url_for('admin.insurance_management') }}` | Endpoint `admin.insurance_management` | [FLASK] `url_for()` |
| 199 | `{{ url_for('admin.hall_pass') }}` | Endpoint `admin.hall_pass` | [FLASK] `url_for()` |
| 209-376 | `total_pending_actions`, `pending_*` counts, `recent_redemptions`, `recent_hall_passes`, `recent_insurance_claims` | Metrics/lists | Route kwargs |
| 260-285 | `req.*` expressions (`seat_id`, `store_item.name`, `redemption_details`, `id`) | Redemption object attrs | Route kwarg `recent_redemptions` |
| 264 | `seat_profiles.get(req.seat_id).first_name ~ ' ' ~ seat_profiles.get(req.seat_id).last_name if ...` | Profile dict values | Route kwarg `seat_profiles` |
| 270 | `{{ req.redemption_details | markdown }}` | Markdown text | Route kwarg `recent_redemptions` |
| 275 | `data-student-item-id="{{ req.id }}"` | Redemption id | Loop variable `req` |
| 301-321 | `pass.*` expressions (`seat_id`, `request_time`) | Hall-pass attrs | REWIRED_READ from ephemeral pending-request projection, not `hall_pass_logs` |
| 305 | `seat_profiles.get(pass.seat_id).first_name ~ ' ' ~ ...` | Profile dict values | REWIRED_READ via seat-id keyed `IdentityProfile` lookup |
| 313 | `{{ format_utc_iso(pass.request_time) }}` | Datetime helper | REWIRED_READ from pending-request timestamp projection |
| 338-357 | `claim.*` expressions (`seat_id`, `description`, `claim_amount`, `filed_date`) | Insurance claim attrs | Route kwarg `recent_insurance_claims` |
| 342 | `seat_profiles.get(claim.seat_id).first_name ~ ' ' ~ ...` | Profile dict values | Route kwarg `seat_profiles` |
| 345 | `{{ claim.description[:50] }}` | String slice | Loop variable `claim` |
| 348 | `{{ "%.2f"|format(claim.claim_amount) }}` | Number | Loop variable `claim` |
| 353 | `{{ format_utc_iso(claim.filed_date) }}` | Datetime helper | Shared [GLOBAL] `format_utc_iso` |
| 385 | `{{ url_for('admin.transactions') }}` | Endpoint `admin.transactions` | [FLASK] `url_for()` |
| 400-425 | `tx.*` expressions (`seat_id`, `description`, `amount`, `timestamp`) | Transaction attrs | Route kwarg `recent_transactions` |
| 404 | `{% set profile = seat_profiles.get(tx.seat_id) %}` | Seat profile dict | Route kwarg `seat_profiles` |
| 407 | `{{ profile.first_name ~ ' ' ~ profile.last_name if profile else 'Unknown' }}` | Profile object | `seat_profiles` |
| 410 | `{{ format_utc_iso(tx.timestamp) }}` | Datetime helper | Shared [GLOBAL] `format_utc_iso` |
| 446-478 | `recent_logs` loop and `log.*` expressions (`status`, `student_name`, `timestamp`, `period`) | Attendance log attrs | Route kwarg `recent_logs` — REWIRED_READ from `attendance_sessions` |
| 451 | `{% if log.status == 'active' %}` | Status string | Loop variable `log` |
| 461 | `{{ log.student_name }}` | Student name string | Loop variable `log` |
| 463 | `{{ format_utc_iso(log.timestamp) }}` | Datetime helper | Shared [GLOBAL] `format_utc_iso` |
| 464 | `{{ log.timestamp.strftime('%H:%M') }}` | Datetime | Loop variable `log` |
| 468 | `{{ log.status|title }} • Period {{ log.period }}` | Status/period | Loop variable `log` |
| 480 | `{{ url_for('admin.attendance_log') }}` | Endpoint `admin.attendance_log` | [FLASK] `url_for()` |
| removed | former `{{ url_for('admin.enforce_daily_limits') }}` dashboard action | Removed user trigger | Daily-limit enforcement collapsed to scheduled `FEAT-PROD-001` task with exact limit-boundary close timestamp |
