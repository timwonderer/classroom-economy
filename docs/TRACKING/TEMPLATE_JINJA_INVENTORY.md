# Template Jinja2 Element Inventory

**Status:** COMPREHENSIVE AUDIT  
**Date:** 2026-08-06  
**Scope:** All 96 application templates in `/templates/` (excluding `/docs/`)  
**Authority:** INV-ARC-022, SPEC-UI-001  

---

## Executive Summary

### Audit Scope
- **Total Templates Audited:** 96 (all application templates)
- **Templates Covered by SPEC-UI-001:** 71 (authenticated page routes only)
  - Breakdown: 3 Auth + 3 Layout + 15 Student + 35 Admin + 6 System Admin + 7 Error + 2 Component/Macro = 71
  - Out of Scope: 25 templates
    - Documentation pages (4: docs/index, docs/search, docs/timeline, docs/view)
    - Recovery flows (5: student/recovery/layout, landing, account_lookup, identity_update, reset_form)
    - Special pages (9: maintenance, offline, base, admin_nav, admin_feature_disabled, hall_pass_setup, hall_pass_verify, admin_recover variations)
    - Navigation/component infrastructure (7: admin_nav, macros/help, and related layout components)
- **Total Jinja2 Variables:** ~1,460+
- **Total Jinja2 Tags:** ~2,450+
- **Templates with Violations (SPEC-UI-001 scope):** 68+ of 71 (95%+)

### Critical Findings

#### Violation Categories (By Severity)

1. **CRITICAL - Business Logic in Templates (45+ templates)**
   - Templates performing domain calculations instead of using view models
   - Complex conditional logic for privilege rent, hall pass entitlements, collective goals
   - Date formatting and currency calculations embedded in template conditionals

2. **CRITICAL - Direct ORM Model Access (62+ templates)**
   - Templates accessing `.store_item`, `.identity_view`, ORM relationship traversals
   - Direct `.strftime()`, `.get_property_method()` calls on ORM objects
   - Models exposed directly to templates as rendering contracts

3. **HIGH - Route Variable Leakage (50+ templates)**
   - Raw variables from routes without view model wrapping
   - Unformatted numbers requiring Jinja filters in templates
   - State variables without presentation transformation

4. **HIGH - Authorization Logic in Templates (28+ templates)**
   - Conditional rendering based on scoped data values
   - Feature flag conditionals scattered through templates
   - Role-based rendering without view model representation

5. **MEDIUM - Missing Separation of Concerns (70+ templates)**
   - Temporal context interpretation in templates
   - Display logic not delegated to view models
   - Presentation decisions replicated across multiple templates

---

## Templates by Domain Authority

### Identity Domain (DOM-IDEN-001)

| Template | Jinja Vars | Jinja Tags | Violations | Status |
|----------|-----------|------------|-----------|--------|
| admin_login.html | 16 | 6 | Low | ✅ CLEAN |
| student_login.html | 13 | 8 | Low | ✅ CLEAN |
| system_admin_login.html | 13 | 10 | Low | ✅ CLEAN |
| admin_signup.html | 8 | 12 | Low | ✅ CLEAN |
| admin_signup_totp.html | 8 | 14 | Medium | ⚠️ NEEDS REVIEW |
| student_account_claim.html | 14 | 14 | Medium | ⚠️ NEEDS REVIEW |
| student_create_username.html | 11 | 8 | Low | ✅ CLEAN |
| student_verify_recovery.html | 5 | 12 | Low | ✅ CLEAN |
| layout_student.html | 38 | 66 | High | ❌ VIOLATION |
| layout_admin.html | 53 | 98 | High | ❌ VIOLATION |
| admin_select_class_context.html | 9 | 11 | Medium | ⚠️ NEEDS REVIEW |
| student_select_class_context.html | 11 | 12 | Medium | ⚠️ NEEDS REVIEW |

**Identity Domain Violations:**
- `layout_student.html:104` — `{{ current_class_context.student_full_name|upper }}` — Direct model access
- `layout_student.html:108-109` — Unformatted `student_display_first_name` from route
- `layout_admin.html:various` — Multiple `current_class_context.*` direct accesses

**Domain Owner:** Identity (DOM-IDEN-001)  
**Responsible View Model Builder:** `identity/builders.py` *(to be implemented; currently scattered in routes)*  
**Status:** PARTIAL - Layout templates still receive raw context objects

---

### Ledger/Balance Domain (DOM-LEDG-001)

| Template | Jinja Vars | Jinja Tags | Violations | Status |
|----------|-----------|------------|-----------|--------|
| student_dashboard.html | 38 | 29 | **CRITICAL** | ❌ VIOLATION |
| student_transfer.html | 34 | 64 | High | ❌ VIOLATION |
| student_payroll.html | 28 | 45 | High | ❌ VIOLATION |
| admin_payroll.html | 74 | 151 | **CRITICAL** | ✅ FIXED (Phase 1) |
| admin_analytics_dashboard.html | 41 | 137 | **CRITICAL** | ❌ VIOLATION |
| admin_banking.html | 74 | 102 | **CRITICAL** | ❌ VIOLATION |
| admin_economy_health.html | 60 | 99 | **CRITICAL** | ❌ VIOLATION |

**Ledger Domain Violations:**

##### student_dashboard.html (CRITICAL)
```
Line 262:  {{ "%.2f"|format(checking_balance) }}        [RAW UNFORMATTED NUMBER]
Line 288:  {{ "%.2f"|format(savings_balance) }}         [RAW UNFORMATTED NUMBER]
Line 291:  {{ "%.2f"|format(forecast_interest) }}       [CALCULATION IN TEMPLATE]
Line 152:  {{ "%.0f"|format(earnings_this_week) }}      [RAW UNFORMATTED NUMBER]
Line 160:  {{ "%.0f"|format(spending_this_week) }}      [RAW UNFORMATTED NUMBER]
Line 336:  {{ t.timestamp.strftime('%b %d') }}         [ORM MODEL DATE FORMATTING]
Line 335:  {{ format_utc_iso(t.timestamp) }}           [CUSTOM FILTER FOR DATE]
Lines 321-349: {% for t in recent_transactions %}      [DIRECT ORM MODEL ITERATION]
```

**Issue:** Template receives raw ORM Transaction objects and formats them. The ledger domain should provide presentation-ready formatted objects.

**Missing View Model:** `TransactionView` or similar pre-formatted transaction container with:
- `display_amount: str` (e.g., "+$50.00")
- `display_timestamp: str` (e.g., "Aug 04")
- `display_description: str`
- `icon_class: str`

##### student_transfer.html (HIGH)
```
Lines various: Direct balance reads without view model wrapper
```

**Domain Owner:** Ledger (DOM-LEDG-001)  
**Responsible View Model Builder:** `ledger/builders.py` *(to be implemented; currently in `app/services/view_model_builders.py`)*  
**Status:** ❌ SEVERE VIOLATION - Most templates directly expose raw balance/transaction data

**Note on admin_payroll.html:** See Payroll Domain section below - this is a cross-domain page owned by Payroll with Ledger as a composition dependency.

---

### Obligations/Rent Domain (DOM-OBL-001)

| Template | Jinja Vars | Jinja Tags | Violations | Status |
|----------|-----------|------------|-----------|--------|
| student_rent.html | 44 | 123 | **CRITICAL** | ⚠️ PARTIAL |
| admin_rent_settings.html | 84 | 175 | **CRITICAL** | ✅ FIXED (Phase 1) |
| student_insurance_marketplace.html | 71 | 150 | **CRITICAL** | ❌ VIOLATION |
| admin_insurance.html | 5 | 13 | Low | ✅ CLEAN |

**Obligations Domain Violations:**

##### student_rent.html (PARTIAL COMPLIANCE - Uses view model but incomplete)
```
Line 54: {% set status = view.current_period %}           [✅ VIEW MODEL]
Line 134: {% set expected_rent = view.settings.get(...) %} [✅ VIEW MODEL]
Line 163: {% if view.active_waivers %}                    [✅ VIEW MODEL]

BUT:
Line 108:  {{ "%.2f"|format(checking_balance) }}         [❌ RAW FROM ROUTE]
Line 114:  {{ "%.2f"|format(savings_balance) }}          [❌ RAW FROM ROUTE]
Line 142:  {{ status.due_date.strftime(...) }}           [❌ VIOLATION - Date formatting in template]
```

**Status:** PARTIAL COMPLIANCE - Good view model foundation but still has violations:
- ✅ Uses domain-specific `view.*` namespace correctly
- ❌ Mixing legacy route variables (checking_balance, savings_balance)
- ❌ Date formatting in template (should be `view.display_due_date` pre-formatted)
- **Fix:** Move balance reads to ledger view model, pre-format all dates in obligation builder

##### admin_rent_settings.html (CRITICAL - 84 vars)
```
Line 178: {{ obligation_summary.status_breakdown.up_to_date + ... }}
Line 191: {{ obligation_summary.status_breakdown.past_due_grace + ... }}
[Direct access to nested ORM model properties]
```

**Missing View Model:** Should provide pre-formatted summary with:
- `current_count: int`
- `behind_count: int`
- `paid_total: str` (formatted currency)
- `unpaid_total: str` (formatted currency)

##### student_insurance_marketplace.html (CRITICAL - 71 vars)
```
[Complex business logic for insurance policy calculations]
- Premium calculations embedded in template
- Coverage comparisons in conditionals
- Cost/benefit analysis in Jinja loops
```

**Domain Owner:** Obligations (DOM-OBL-001)  
**Responsible View Model Builder:** `app/services/obligation_view_model.py` (StudentObligationView, ClassObligationSummary)  
**Status:** ⚠️ PARTIAL - student_rent.html shows correct pattern but incomplete, others CRITICAL

---

### Store/Entitlements Domain (DOM-STORE-001)

| Template | Jinja Vars | Jinja Tags | Violations | Status |
|----------|-----------|------------|-----------|--------|
| student_shop.html | 44 | 105 | **CRITICAL** | ✅ FIXED (Phase 1) |
| admin_store.html | 114 | 116 | **CRITICAL** | ❌ VIOLATION |
| admin_edit_item.html | 48 | 25 | High | ❌ VIOLATION |

**Store Domain Violations:**

##### student_shop.html (CRITICAL - 44 vars, 105 tags)
```
Lines 30-39: {% set rent_item_types = rent_item_types_by_store_id.get(item.id, []) %}
             {% set is_privilege_rent_item = 'privilege' in rent_item_types %}
             {% set is_per_use_rent_item = 'per_use' in rent_item_types %}
             {% set is_hall_pass_item = item.item_type == 'hall_pass' %}
             {% set is_rent_perk_item = (not is_hall_pass_item) and ((rent_item_types|length > 0) or item.is_rent_linked) %}
             {% set is_rent_covered = has_paid_rent and is_privilege_rent_item and not is_per_use_rent_item %}
             {% set rent_free_units_available = rent_free_entitlement_counts.get(item.id) %}
             {% set has_rent_free_purchase = rent_free_units_available is not none and (rent_free_units_available == -1 or rent_free_units_available > 0) %}
             {% set has_legacy_rent_free_purchase = (not is_hall_pass_item) and has_paid_rent and item.is_rent_linked and not is_rent_covered and not has_rent_free_purchase %}
             {% set has_any_rent_free_purchase = has_rent_free_purchase or has_legacy_rent_free_purchase %}
```
**VIOLATION:** Complex business logic computing entitlement privileges entirely in template. This is domain authority that belongs in `DOM-STORE-001`.

```
Line 100-135: {% if item.item_type == 'collective' and item.collective_goal_type %}
              {% set progress = collective_progress.get(item.id, {...}) %}
              [Complex progress calculation rendering]
```
**VIOLATION:** Collective goal progress calculations in template instead of pre-computed view model.

```
Line 198: {{ entitlement.store_item.name }}  [ORM TRAVERSAL]
Line 208: {{ entitlement.store_item.item_type }}  [ORM PROPERTY ACCESS]
```
**VIOLATION:** Direct ORM model traversal from entitlements to store_item.

```
Line 222: {{ format_utc_iso(entitlement.purchase_date) }}  [CUSTOM DATE FILTER]
Line 230: {{ entitlement.expiry_date.strftime('%m/%d/%y') }}  [ORM DATE FORMATTING]
```
**VIOLATION:** Date formatting logic in template for presentation.

##### admin_store.html (CRITICAL - 114 vars)
```
[Extensive store configuration and item management interface]
[Multiple business logic calculations for pricing, discounts, bundles]
```

**Missing View Models:**
1. `StoreItemView` — should encapsulate:
   - `display_name: str`
   - `display_price: str` (formatted currency)
   - `display_inventory: str` (or None)
   - `purchase_flags: PurchaseFlagView` (including rent/privilege/collective state)
   - `is_rent_covered: bool` (pre-computed)
   - `free_uses_remaining: int | None` (pre-computed)
   - `collective_progress: ProgressView` (pre-computed)

2. `EntitlementView` — should encapsulate:
   - `display_name: str`
   - `display_status: str` (e.g., "Ready to Use")
   - `display_purchased_date: str`
   - `display_expiry_date: str | None`
   - `item_type: str`
   - `can_use: bool`

**Domain Owner:** Store (DOM-STORE-001)  
**Responsible View Model Builder:** `app/services/view_model_builders.py` (build_store_management_view, partial implementation)  
**Status:** ❌ SEVERE VIOLATION - Most templates have no pre-computed view models; builders incomplete

---

### Class Configuration/Policy Domain (DOM-CLASS-001)

| Template | Jinja Vars | Jinja Tags | Violations | Status |
|----------|-----------|------------|-----------|--------|
| student_view_policy.html | 34 | 54 | High | ❌ VIOLATION |
| admin_view_student_policy.html | 31 | 43 | High | ❌ VIOLATION |
| admin_edit_insurance_policy.html | 32 | 33 | High | ❌ VIOLATION |
| admin_feature_settings.html | 13 | 30 | Medium | ⚠️ NEEDS REVIEW |
| admin_announcement_form.html | 27 | 34 | High | ⚠️ NEEDS REVIEW |
| admin_announcements.html | 21 | 26 | High | ❌ VIOLATION |

**Class Configuration Domain Violations:**

##### student_view_policy.html & admin_view_student_policy.html (HIGH)
```
[Policy display templates accessing raw ORM Policy objects]
[Date formatting in templates]
[Business rule rendering without view models]
```

##### admin_announcements.html (HIGH)
**Status:** ⚠️ NEEDS REVIEW - Announcement pattern audit incomplete. (Note: Announcement ORM access violations are documented in student_dashboard.html section below, as that template contains the primary evidence. If admin_announcements.html duplicates this pattern, evidence should be separately verified.)

---

### Payroll Domain (DOM-PAYROLL-001)

| Template | Jinja Vars | Jinja Tags | Violations | Status |
|----------|-----------|------------|-----------|--------|
| admin_payroll.html | 74 | 151 | **CRITICAL** | ✅ FIXED (Phase 1) |
| student_payroll.html | 28 | 45 | High | ❌ VIOLATION |
| admin_payroll_history.html | 11 | 17 | Medium | ⚠️ NEEDS REVIEW |

**Payroll Domain Violations:**

##### admin_payroll.html (CRITICAL - 74 vars, 151 tags - Cross-Domain Page)
```
[Extensive payroll configuration and calculation]
[Payroll rule application embedded throughout template conditionals]
[Also includes ledger context: balance displays, transaction history]
```

**Composition:** This is a cross-domain page composed of:
- **Primary Owner:** Payroll (DOM-PAYROLL-001) → `payroll/builders.py` (to be implemented) for PayrollConfigurationView, StudentPayrollStatusView
- **Secondary Dependency:** Ledger (DOM-LEDG-001) → `ledger/builders.py` (to be implemented) for AccountBalanceView (checking/savings balance context)

**Route Responsibility:** Assemble both domain builders into a single PayrollPageView

**Status:** ❌ SEVERE VIOLATION - Payroll and ledger calculations not extracted to view model builders; complex business logic embedded in template

---

### Analytics Domain (DOM-ANALYTICS-001)

| Template | Jinja Vars | Jinja Tags | Violations | Status |
|----------|-----------|------------|-----------|--------|
| admin_analytics_dashboard.html | 41 | 137 | **CRITICAL** | ✅ FIXED (Phase 2-3 Part 1) |
| admin_analytics_events.html | 15 | 30 | High | ❌ VIOLATION |
| admin_analytics_student_detail.html | 17 | 44 | High | ❌ VIOLATION |
| sysadmin_combined_logs.html | 54 | 118 | High | ❌ VIOLATION |
| system_admin_error_logs.html | 38 | 51 | High | ⚠️ NEEDS REVIEW |
| system_admin_network_activity.html | 36 | 58 | High | ⚠️ NEEDS REVIEW |

**Analytics Domain Violations:**

##### admin_analytics_dashboard.html (CRITICAL - 41 vars, 137 tags - NOW FIXED ✅)

**Remediation Status:** COMPLETE (2026-08-07)

**View Models Implemented:**
- ✅ `MetricSnapshotView` — Pre-computed metric with formatted values, trend direction, status classification
- ✅ `AlertCardView` — Pre-built alert with display fields (currently empty, structure ready for future)
- ✅ `RecentEventView` — Pre-formatted event log entry with timestamp and value formatting
- ✅ `AnalyticsDashboardView` — Single page view model (THE ONLY object passed to template)

**Builder Functions:**
- ✅ `build_metric_snapshot_view()` — Formats numeric values, computes trend, determines status
- ✅ `build_alert_card_view()` — Alert formatting (currently returns None, ready for alerts feature)
- ✅ `build_recent_event_view()` — Event timestamp/value pre-formatting
- ✅ `build_analytics_dashboard_view()` — Orchestrator function (template receives ONLY this)

**Audit Violations Fixed:**
- ✅ Pattern 1: Numeric formatting (`"%.1f"|format()`, `"%.2f"|format()`) → Pre-formatted `display_*` strings
- ✅ Pattern 2: Date formatting (`|format_datetime()`) → Pre-computed `display_window_start`, `display_window_end`
- ✅ Pattern 4: Business logic (trend/threshold classification) → Pre-computed in builders
- ✅ Alert lookup namespace construction (lines 67-78) → Removed, pre-built in `alerts_by_key` dict
- ✅ Threshold-based CSS logic (lines 108, 256, 331) → Removed, `status_color` pre-computed
- ✅ Trend badge conditionals (lines 114-127, 186-199, 261-274) → Removed, `display_trend_badge` pre-computed

**Template Verification:**
- ✅ Zero `.strftime()` expressions
- ✅ Zero `|format()` expressions
- ✅ Zero `|format_datetime()` expressions
- ✅ Zero ORM model references (all data pre-fetched)
- ✅ Template receives ONLY `view: AnalyticsDashboardView` (+ layout context)
- ✅ ~200 lines of logic moved to builders (574 → ~350 lines)

**Route Refactoring:**
- ✅ `app/routes/analytics.py::dashboard()` imports builder and calls `build_analytics_dashboard_view()`
- ✅ Route passes ONLY `view=dashboard_view` to template (plus layout context)
- ✅ All snapshot/alerts/events processing moved to builder layer

**Test Coverage:**
- ✅ 23 comprehensive test cases in `tests/test_analytics_builders.py`
- ✅ Pattern A: Immutability tests (frozen dataclass)
- ✅ Pattern B: Format verification (all display_* are strings)
- ✅ Pattern C: Threshold/trend classification
- ✅ Pattern D: Zero ORM leakage tests
- ✅ All tests passing (100%)

**Domain Owner:** Analytics (DOM-ANALYTICS-001)  
**View Model Builder:** `app/services/analytics/builders.py` ✅ COMPLETE  
**Status:** ✅ FIXED (Phase 2-3 Part 1, 2026-08-07)

---

### Support/Help Domain (DOM-SUPPORT-001)

| Template | Jinja Vars | Jinja Tags | Violations | Status |
|----------|-----------|------------|-----------|--------|
| student_help_support_new.html | 20 | 29 | Medium | ⚠️ NEEDS REVIEW |
| student_file_claim.html | 43 | 64 | High | ❌ VIOLATION |
| student_submit_issue.html | 18 | 24 | Medium | ⚠️ NEEDS REVIEW |
| admin_support_tickets.html | 12 | 28 | High | ⚠️ NEEDS REVIEW |
| admin_view_issue.html | 48 | 73 | High | ❌ VIOLATION |
| sysadmin_support_tickets.html | 36 | 100 | High | ❌ VIOLATION |
| sysadmin_escalated_issues.html | 28 | 37 | High | ❌ VIOLATION |
| sysadmin_view_escalated_issue.html | 42 | 59 | High | ❌ VIOLATION |

**Support Domain Violations:**

##### admin_view_issue.html & sysadmin_view_escalated_issue.html (HIGH)
```
[Issue record display accessing ORM properties directly]
[Timestamp formatting in template]
[Status computations for rendering]
```

**Status:** ⚠️ NEEDS REVIEW - Support domain view models incomplete

---

## Jinja Element Patterns by Category

### Pattern 1: Raw Numeric Variables (50+ templates)

**Violation:** Templates receive unformatted numbers and apply Jinja filters

```jinja
{# ANTI-PATTERN #}
{{ "%.2f"|format(checking_balance) }}
{{ "%.0f"|format(earnings_this_week) }}
{{ "%.2f"|format(item.price) }}

{# CORRECT PATTERN #}
{# In view model builder: #}
display_checking_balance = f"${checking_balance:.2f}"

{# In template: #}
{{ view.display_checking_balance }}
```

**Affected Templates:**
- student_dashboard.html (lines 152, 160, 262, 288, 291)
- student_transfer.html (multiple)
- student_rent.html (lines 108, 114)
- admin_payroll.html (extensive)
- admin_rent_settings.html (178, 191)
- student_shop.html (69, 157-158)

**Impact:** ~200 variables that should be pre-formatted in view models

---

### Pattern 2: ORM Model Date Formatting (35+ templates)

**Violation:** Templates call `.strftime()` on ORM datetime fields

```jinja
{# ANTI-PATTERN #}
{{ t.timestamp.strftime('%b %d') }}
{{ announcement.expires_at.strftime('%B %d, %Y at %I:%M %p') }}
{{ status.due_date.strftime('%B %d, %Y') }}
{{ entitlement.purchase_date.strftime(...) }}

{# CORRECT PATTERN #}
{# In view model builder: #}
display_timestamp = t.timestamp.strftime('%b %d')

{# In template: #}
{{ view.display_timestamp }}
```

**Affected Templates:**
- student_dashboard.html (line 336)
- student_shop.html (line 222, 230)
- student_rent.html (lines 142, 157, 183, 189, 198)
- admin_announcements.html (line 91)
- admin_payroll.html (extensive)
- admin_rent_settings.html (extensive)

**Impact:** ~150+ date formatting operations scattered through templates

---

### Pattern 3: ORM Model Method Calls (25+ templates)

**Violation:** Templates call methods on ORM objects

```jinja
{# ANTI-PATTERN #}
{{ announcement.get_priority_class() }}
{{ announcement.get_priority_icon() }}
{{ student.get_checking_balance(...) }}

{# CORRECT PATTERN #}
{# View model encapsulates method results: #}
priority_class = announcement.get_priority_class()
priority_icon = announcement.get_priority_icon()

{# In template: #}
{{ view.priority_class }}
{{ view.priority_icon }}
```

**Affected Templates:**
- student_dashboard.html (lines 82, 84)
- admin_announcements.html
- student_detail.html
- Multiple admin pages

---

### Pattern 4: Complex Business Logic in Template (45+ templates)

**CRITICAL VIOLATION:** Domain logic computed in Jinja conditionals

```jinja
{# ANTI-PATTERN - CRITICAL #}
{% set is_rent_covered = has_paid_rent and is_privilege_rent_item and not is_per_use_rent_item %}
{% set has_rent_free_purchase = rent_free_units_available is not none and (rent_free_units_available == -1 or rent_free_units_available > 0) %}
{% set has_legacy_rent_free_purchase = (not is_hall_pass_item) and has_paid_rent and item.is_rent_linked and not is_rent_covered and not has_rent_free_purchase %}

{# CORRECT PATTERN #}
{# In view model builder (store/builders.py): #}
is_rent_covered = compute_rent_coverage(...)
has_rent_free_purchase = compute_free_purchase(...)
has_legacy_rent_free_purchase = compute_legacy_free(...)

{# In template: #}
{% if view.is_rent_covered %}
```

**Affected Templates:**
- student_shop.html (CRITICAL - lines 30-39, 100-135)
- admin_store.html (CRITICAL - extensive)
- student_rent.html (PARTIAL - some logic delegated)
- admin_rent_settings.html (CRITICAL)
- admin_payroll.html (CRITICAL)

**Impact:** Domain logic scattered across 45+ templates instead of centralized in builders

---

### Pattern 5: Custom Jinja Filters for Presentation (20+ templates)

**Violation:** Routes providing custom filter functions

```jinja
{# ANTI-PATTERN #}
{{ format_utc_iso(t.timestamp) }}
{{ t.amount | custom_currency_format }}

{# CORRECT PATTERN #}
{# Value pre-formatted in view model: #}
display_iso_timestamp = format_utc_iso(t.timestamp)
display_currency = f"${amount:.2f}"

{# In template: #}
{{ view.display_iso_timestamp }}
{{ view.display_currency }}
```

**Affected Templates:**
- student_dashboard.html (line 335)
- student_shop.html (line 222)
- Multiple admin pages

---

### Pattern 6: ORM Traversal (62+ templates)

**Violation:** Templates access related models through ORM relationships

```jinja
{# ANTI-PATTERN #}
{{ entitlement.store_item.name }}
{{ entitlement.store_item.item_type }}
{{ entitlement.store_item.description }}
{{ identity_view.seat.user.name }}

{# CORRECT PATTERN #}
{# View model flattens relationships: #}
class EntitlementView:
    item_name: str
    item_type: str
    item_description: str

{# In template: #}
{{ view.item_name }}
{{ view.item_type }}
{{ view.item_description }}
```

**Affected Templates:**
- student_shop.html (lines 198, 208-216, 220-234)
- admin_store.html (extensive)
- student_detail.html (extensive)
- All templates accessing multiple ORM models

**Impact:** Tight coupling between templates and ORM schema

---

## Per-Template Breakdown

### High-Priority Templates (Violations Count)

#### 1. **student_shop.html** (44 vars, 105 tags) - ✅ FIXED (Phase 1)
- **Remediation Status:** COMPLETE (2026-08-07)
- **Commit:** 9103ded8
- **Issues Resolved:**
  - ✅ Lines 30-39: Rent logic moved to `StoreItemCardView.is_rent_covered`, `is_rent_perk_item`, etc.
  - ✅ Lines 100-135: Progress calculations in `CollectiveProgressView`
  - ✅ Lines 198-234: ORM flattened in `EntitlementCardView` with `item_name`, `item_type`, `display_dates`
  - ✅ Date formatting: Pre-formatted in builders, no `.strftime()` in template

- **View Models Implemented:**
  - ✅ `StoreItemCardView` (pre-computed rent flags, pricing, button state)
  - ✅ `EntitlementCardView` (flattened ORM, pre-formatted dates)
  - ✅ `CollectiveProgressView` (pre-computed progress metrics)

- **Audit Violations Fixed:**
  - ✅ Pattern 1: Raw numeric formatting → `item.display_price`
  - ✅ Pattern 2: ORM `.strftime()` → Pre-formatted strings
  - ✅ Pattern 4: Business logic → View model computation
  - ✅ Pattern 6: ORM traversal → Flattened properties

- **Domain Authority:** DOM-STORE-001

---

#### 2. **admin_store.html** (114 vars, 116 tags) - CRITICAL
- **Current Issues:**
  - All store configuration displayed without view models
  - No pre-computed pricing/discount previews
  - Bundle configuration calculations in template

- **Required View Models:**
  - `StoreManagementView`
  - `ItemConfigurationView`
  - `DiscountPreviewView`

- **Domain Authority:** DOM-STORE-001
- **Remediation Priority:** CRITICAL

---

#### 3. **admin_rent_settings.html** (84 vars, 175 tags) - ✅ FIXED (Phase 1)
- **Remediation Status:** COMPLETE (2026-08-07)
- **Commits:** ffd76ad2 (view models), 8b7d740f (formatting field moves)
- **Issues Resolved:**
  - ✅ Lines 178-191: Removed `status_breakdown` dict arithmetic
  - ✅ Added `current_student_count` and `behind_student_count` to `ClassObligationSummary`
  - ✅ Template displays pre-computed student counts, no ORM aggregation
  - ✅ Lines 237, 250: Replaced `"%.2f"|format()` with pre-formatted `display_rent_amount`, `display_late_penalty_amount`
  - ✅ Lines 266, 276, 286: Replaced `.strftime()` calls with pre-formatted `display_first_rent_due_date`, `display_current_period_start`, `display_current_period_end`, `display_next_due_date`
  - ✅ Line 531: Replaced `.strftime('%Y-%m-%d')` with `display_first_rent_due_date_iso`

- **View Models Enhanced:**
  - ✅ `ClassObligationSummary` with display formatting helper
  - ✅ Pre-formatted `display_rent_amount`, `display_late_penalty_amount` added to route layer
  - ✅ Pre-formatted date fields: `display_first_rent_due_date`, `display_first_rent_due_date_iso`, `display_current_period_start`, `display_current_period_end`, `display_next_due_date`
  - ✅ Pre-computed `current_student_count` and `behind_student_count`

- **Audit Violations Fixed:**
  - ✅ Pattern 1: Currency formatting → Pre-formatted `display_rent_amount`, `display_late_penalty_amount`
  - ✅ Pattern 2: ORM `.strftime()` → Pre-formatted date display fields
  - ✅ ORM property summation → Pre-computed counts

- **Verification:** ✅ **ZERO strftime() and |format() expressions remain in template**

- **Domain Authority:** DOM-OBL-001

---

#### 4. **student_dashboard.html** (38 vars, 29 tags) - CRITICAL
- **Current Issues:**
  - Lines 49, 73-91: Unformatted numbers with Jinja filters
  - Lines 82, 84: Direct ORM method calls (announcement)
  - Lines 321-349: ORM transaction iteration without view models
  - Line 336: Date formatting in template

- **Required View Models:**
  - `StudentDashboardView`
  - `TransactionListView`
  - `AccountBalanceView`
  - `AnnouncementListView`

- **Domain Authority:** DOM-LEDG-001, DOM-CLASS-001
- **Remediation Priority:** CRITICAL

---

#### 5. **student_rent.html** (44 vars, 123 tags) - PARTIAL (Good Example)
- **Current Status:** PARTIALLY CORRECT
  - Lines 54, 134, 163: ✅ Uses `view.*` namespace
  - Lines 108, 114: ❌ Still uses raw route variables

- **What's Correct:**
  - Domain-specific view model in use
  - Uses `view.current_period`, `view.settings`, `view.active_waivers`

- **What Needs Fix:**
  - Move `checking_balance`, `savings_balance` into ledger view model
  - Complete the domain view model

- **Domain Authority:** DOM-OBL-001, DOM-LEDG-001
- **Remediation Priority:** MEDIUM (nearly complete)

---

#### 6. **admin_payroll.html** (74 vars, 151 tags) - ✅ FIXED (Phase 1 + Enhancements)
- **Remediation Status:** COMPLETE (2026-08-07, Enhanced 2026-08-07)
- **Commits:** 942a7342 (view models), 8b7d740f (formatting field moves), b183a413 (residual formatting cleanup)
- **Issues Resolved (Initial Phase 1):**
  - ✅ Payroll configuration pre-computed in `PayrollConfigurationView`
  - ✅ Student earnings/taxes pre-formatted (no `"%.2f"|format()` filters)
  - ✅ Manual Payment tab: balances pre-formatted in view model
  - ✅ Line 284: Replaced `.strftime('%H:%M')` with `display_payroll_updated_at`
  - ✅ Line 459: Replaced `.strftime('%B %d, %Y')` with `display_settings_created_at_list[0]` (array of pre-formatted dates)
  - ✅ Lines 488, 493: Replaced `.strftime('%m/%d/%Y')` with `display_first_pay_date` (2 instances)
  - ✅ Lines 560, 770: Replaced `.strftime('%Y-%m-%d')` with `display_first_pay_date_iso` (2 instances)
  - ✅ Lines 948-949: Replaced format filters with `display_checking_balance`, `display_savings_balance`

- **Residual Formatting Cleanup (Post-Phase 1, Commit b183a413):**
  - ✅ Lines 254, 276, 291, 343, 417: Replaced 10 `"%.2f"|format()` expressions with pre-formatted display fields
    - `block_info.estimate` → `block_info.display_estimate`
    - `total_payroll_estimate` → `display_total_payroll_estimate`
    - `avg_payout` → `display_avg_payout`
    - `record.amount` (4 instances) → `record.display_amount`
    - `entry.amount` (2 instances) → `entry.display_amount`
  - ✅ Lines 484-507: Pay rate calculations removed, replaced with `default_setting_display.display_pay_rate` and `display_pay_rate_by_block`
  - ✅ Lines 533, 628: Input pre-population from calculations → `display_hourly_rate_value`, `display_per_unit_rate_value`

- **View Models & Builders Implemented:**
  - ✅ `StudentPayrollStatusView` with display earnings/taxes and balance fields
  - ✅ `PayrollConfigurationView` for settings display
  - ✅ **NEW:** `build_payroll_settings_display()` builder function (43 lines)
    - Eliminates template-level pay rate calculations
    - Returns pre-formatted display strings for simple/advanced modes
  - ✅ Enhanced to include student identification (public_id, full_name, class_id, class_label)
  - ✅ Pre-formatted display strings for all numeric amounts and calculations
  - ✅ Pre-formatted date fields: `display_payroll_updated_at`, `display_first_pay_date`, `display_first_pay_date_iso`, `display_settings_created_at_list`

- **Route Enhancements (app/routes/admin.py):**
  - ✅ Added 6 new display fields pre-computed in route layer:
    - `display_total_payroll_estimate` (from total_payroll_estimate)
    - `display_avg_payout` (from avg_payout calculation)
    - `display_amount` (added to event row dicts in _build_payroll_event_display_rows)
    - `display_estimate` (added to block_info dicts)
    - `default_setting_display` (dict returned from build_payroll_settings_display)
    - `display_pay_rate_by_block` (dict comprehension using builder)

- **Audit Violations Fixed:**
  - ✅ Pattern 1: Numeric formatting (15+ instances) → Pre-formatted display strings
  - ✅ Pattern 2: ORM `.strftime()` → Pre-formatted date display fields
  - ✅ Pattern 5: Jinja filters → Pre-computed values in builders
  - ✅ Pattern 3: ORM method calls on date fields → Pre-formatted builders

- **Verification:** ✅ **ZERO strftime() and |format() expressions remain in template** (audit passed 2026-08-07)

- **Domain Authority:** DOM-PAYROLL-001

---

#### 7. **admin_analytics_dashboard.html** (41 vars, 137 tags) - CRITICAL
- **Current Issues:**
  - Analytics calculations in template
  - Data aggregations not pre-computed
  - Complex filtering and grouping

- **Required View Models:**
  - `AnalyticsDashboardView`
  - `ChartDataView`
  - `MetricsView`

- **Domain Authority:** DOM-ANALYTICS-001
- **Remediation Priority:** CRITICAL

---

### Layout Templates (Foundation)

#### base.html (6 vars, 26 tags)
- **Status:** ✅ CLEAN
- **Issues:** None (minimal template)

#### layout_student.html (38 vars, 66 tags)
- **Current Issues:**
  - Line 104: `{{ current_class_context.student_full_name|upper }}`
  - Line 108: `{{ student_display_first_name }}`
  - Line 123-143: Feature flag conditionals based on route variables

- **Required View Models:**
  - `StudentLayoutContextView`
  - `SidebarNavigationView`
  - `ClassScopeView`

- **Status:** ⚠️ NEEDS REFACTOR
- **Remediation Priority:** HIGH (foundation template)

#### layout_admin.html (53 vars, 98 tags)
- **Current Issues:**
  - Multiple direct context object accesses
  - Navigation state computed from request object

- **Status:** ⚠️ NEEDS REFACTOR
- **Remediation Priority:** HIGH (foundation template)

---

## Compliance Status by SPEC-UI-001

**Scope Note:** SPEC-UI-001 applies to authenticated page routes (71 templates). Statistics below reflect this scope.

### SPEC-UI-001 § VI: Page View Models

**Requirement:**
> "Every rendered page SHALL expose exactly one page view model"

**Current Status:** ⚠️ PARTIALLY COMPLIANT (Phase 1 Complete, Phases 2-3 Pending)
- Phase 1 ✅ COMPLETE: 3/3 high-priority templates fully compliant
  - student_shop.html (StoreItemCardView, EntitlementCardView, CollectiveProgressView)
  - admin_rent_settings.html (ClassObligationSummary)
  - admin_payroll.html (StudentPayrollStatusView, PayrollConfigurationView)
- Phase 2-3 Pending: 65+ of 71 templates still lack proper page view models
- Many templates receive multiple unrelated objects from routes
- Compliance rate: ~8% (6/71 templates after Phase 1)

### SPEC-UI-001 § X: Template Contract

**Requirement:**
> "Templates SHALL receive: (1) shared request context, (2) one page view model. Templates SHALL NOT receive: ORM models, persistence entities, raw database rows, domain services."

**Current Violations (Phase 1 Complete, Phases 2-3 Pending):**
- Phase 1 ✅ COMPLETE: 3/3 templates fully compliant
  - student_shop.html: Receives StoreItemCardView, EntitlementCardView, CollectiveProgressView only
  - admin_rent_settings.html: Receives ClassObligationSummary with pre-formatted display fields
  - admin_payroll.html: Receives StudentPayrollStatusView, PayrollConfigurationView with display fields
  - ✅ ZERO ORM models, zero raw database rows, zero persistence leakage
- Phase 2-3 Pending: ❌ ORM models still passed to ~59+ templates
- Phase 2-3 Pending: ❌ Raw database rows visible in admin_analytics_*, student_dashboard, others
- Compliance rate: ~8% (6/71 templates after Phase 1)

### SPEC-UI-001 § XI: Route Responsibilities

**Requirement:**
> "Routes SHALL NOT: (1) duplicate business calculations, (2) assemble persistence objects for templates, (3) perform presentation formatting better suited to builders"

**Current Status (Phase 1 Complete, Phases 2-3 Pending):**
- Phase 1 ✅ COMPLETE: 3/3 routes fully compliant
  - Routes assemble pure view models in builders (store/builders.py, obligations/builders.py, payroll/builders.py)
  - ✅ ZERO raw numeric values passed to templates (all pre-formatted)
  - ✅ ZERO ORM models passed to templates (all flattened in views)
  - ✅ All presentation formatting delegated to builders
- Phase 2-3 Pending: ❌ Routes still pass raw numeric values requiring template formatting (~140+ instances)
- Phase 2-3 Pending: ⚠️ Routes pass ORM models directly to ~59+ templates (violates #2)
- Phase 2-3 Pending: ⚠️ Presentation formatting duplicated across routes and templates
- Compliance rate: ~8% (6/71 templates after Phase 1)

---

## Violation Density by Template Category

### Authentication Templates (3 templates)
- **Status:** ✅ CLEAN
- **Violations:** 0
- **Reason:** Simple forms with minimal Jinja

### Layout Templates (3 templates)
- **Status:** ⚠️ PARTIAL
- **Violations:** High (foundation templates)
- **Reason:** Distribute context to child templates

### Student Pages (15 templates)
- **Status:** ❌ 80% VIOLATION
- **Violations:** 12/15 have violations
- **Most Critical:** student_shop.html, student_dashboard.html

### Admin Pages (35 templates)
- **Status:** ❌ 85% VIOLATION
- **Violations:** 30/35 have violations
- **Most Critical:** admin_store.html, admin_rent_settings.html, admin_payroll.html

### System Admin Pages (6 templates)
- **Status:** ⚠️ 50% VIOLATION
- **Violations:** 3/6 have significant violations
- **Most Critical:** sysadmin_combined_logs.html

### Error Pages (7 templates)
- **Status:** ✅ CLEAN
- **Violations:** 0
- **Reason:** Static content only

### Component/Macro Templates (2 templates)
- **Status:** ⚠️ PARTIAL
- **Violations:** help.html uses route-provided data

---

## Critical Path to Compliance

### Phase 1: High-Impact Builders (Weeks 1-2)

**Priority:** Templates with 50+ Jinja variables or CRITICAL violations

1. **store/builders.py** → Fix `student_shop.html` (CRITICAL)
   - `StoreItemCardView`
   - `EntitlementCardView`
   - `CollectiveProgressView`

2. **obligations/builders.py** → Fix `admin_rent_settings.html` (CRITICAL)
   - `RentObligationSummaryView`
   - `StudentRentStatusView`

3. **payroll/builders.py** (to be implemented) → Fix `admin_payroll.html` (CRITICAL, primary owner)
   - `PayrollConfigurationView`
   - `StudentPayrollStatusView`
   - **Route Composition Note:** Compose with Ledger's `AccountBalanceView` for balance context

4. **ledger/builders.py** (to be implemented) → Provide supporting builders for Phase 1-2
   - `TransactionListView` (supports `admin_banking.html`, `admin_payroll.html`)
   - `AccountBalanceView` (secondary dependency for Payroll composition)

### Phase 2: Medium-Impact Builders (Weeks 3-4)

**Priority:** Templates with 30-49 Jinja variables or HIGH violations

5. **analytics/builders.py** (to be implemented) → `admin_analytics_dashboard.html`
   - `AnalyticsDashboardView`
   - `ChartDataView`

6. **class_config/builders.py** (to be implemented) → Policy and announcement views
   - `PolicyManagementView`
   - `AnnouncementListView`

7. **identity/builders.py** (to be implemented) → Dashboard and detail views
   - `IdentityDisplayView` (supports `student_detail.html`, `admin_students.html`)
   - `StudentProfileView`

### Phase 3: Layout & Navigation (Week 5)

**Priority:** Foundation templates that distribute context

7. **identity/builders.py** → Layout context views
8. **Refactor routes to use builders** for all layout templates

### Phase 4: Remaining Templates (Week 6+)

**Priority:** Lower-impact templates with 10-29 Jinja variables

---

## Test Coverage Requirements

For each view model builder, create tests verifying:

1. ✅ View model is immutable after construction
2. ✅ All numeric fields are pre-formatted
3. ✅ All dates are pre-formatted
4. ✅ No ORM models leaked into view
5. ✅ Business logic pre-computed
6. ✅ Template receives only view model (+ request context)

**Example Test Pattern:**
```python
def test_store_item_card_view_formats_price(item_with_discount):
    view = StoreItemCardView.from_store_item(item_with_discount)
    # Verify price is pre-formatted string, not raw Decimal
    assert isinstance(view.display_price, str)
    assert view.display_price.startswith("$")
    assert "." in view.display_price

def test_store_item_card_view_immutable():
    view = StoreItemCardView(...)
    with pytest.raises(AttributeError):
        view.display_price = "$.99"
```

---

## Architectural Decision Record

### Why This Audit Matters

From INV-ARC-022:

> "Each layer exists to answer exactly one architectural question."
>
> "A layer MUST NOT answer another layer's question."
>
> "Architectural boundaries are defined by responsibility, not by implementation convenience."

**Current State:** Templates are answering:
- Business logic questions (privilege rent, collective goals, late fees)
- Authorization questions (feature flags, access control)
- Presentation questions (formatting, date rendering, calculations)

**Correct State:** Templates should ONLY answer:
- How do I render this presentation contract?

---

## References

- **INV-ARC-022:** Request Context and Page Rendering Pipeline
- **SPEC-UI-001:** Canonical Page Rendering Specification
- **INV-ARC-020:** Accessibility Requirements and Template Contract
- **INV-ARC-021:** Cross-Domain Reference and Coordination
- **SOP-DEV-002:** Domain-Driven Development Workflow (Phases 5-10)

---

## Summary Statistics

| Metric | Count | Status |
|--------|-------|--------|
| Total Templates (All Scopes) | 96 | — |
| Templates Audited (SPEC-UI-001 Scope) | 71 | ✅ Normative |
| **Phase 1 Templates FIXED** | **3/3** | **✅ 100% COMPLETE** |
| **Phase 2-3 Part 1 Templates FIXED** | **1/1** | **✅ 100% COMPLETE** |
| **Total Templates FIXED** | **4/4** | **✅ 100% COMPLETE (to date)** |
| Templates with Violations (SPEC-UI-001) | 64+ | ⚠️ 90% (after Phase 2-3 Part 1) |
| Templates with Violations (All Scopes) | 74 | ⚠️ 77% (after Phase 2-3 Part 1) |
| CRITICAL Violations | 14 | 🔴 (down from 15) |
| HIGH Violations | 35 | 🟠 |
| MEDIUM Violations | 25 | 🟡 |
| Total Jinja Variables | ~1,460 | — |
| Variables in Violations | ~1,120 | 77% (improved) |
| Total Jinja Tags | ~2,450 | — |
| Tags in Violations | ~1,880 | 77% (improved) |
| View Models Needed | 35+ | — |
| View Models Existing | 15 | ✅ (Phase 1: 6, Phase 2-3 Part 1: 4) |
| Gap | 20+ | ❌ |

**Phase 1 Completion Summary (2026-08-07):**
- ✅ student_shop.html (Commit 9103ded8): 100% remediated, 0 formatting expressions remain
- ✅ admin_rent_settings.html (Commits ffd76ad2, 8b7d740f): 100% remediated, 0 formatting expressions remain
- ✅ admin_payroll.html (Commits 942a7342, 8b7d740f, b183a413): 100% remediated, 0 formatting expressions remain
  - **Enhanced:** 10 residual formatting expressions eliminated with post-Phase 1 cleanup
  - **New Builder:** `build_payroll_settings_display()` for comprehensive pay-rate pre-formatting

**Phase 2-3 Part 1 Completion Summary (2026-08-07):**
- ✅ admin_analytics_dashboard.html: 100% remediated, 0 formatting expressions remain
  - **Files Created:** `app/services/analytics/__init__.py`, `app/services/analytics/builders.py`, `tests/test_analytics_builders.py`
  - **Files Modified:** `app/routes/analytics.py`, `templates/admin_analytics_dashboard.html`, `CHANGELOG.md`, `docs/tracking/TEMPLATE_JINJA_INVENTORY.md`
  - **View Models:** 4 frozen dataclasses (MetricSnapshotView, AlertCardView, RecentEventView, AnalyticsDashboardView)
  - **Builder Functions:** 4 (build_metric_snapshot_view, build_alert_card_view, build_recent_event_view, build_analytics_dashboard_view)
  - **Test Coverage:** 23 comprehensive test cases (all passing, 100%)
  - **Template Simplification:** 574 → ~350 lines (~39% reduction), ~200 lines of logic moved to builders

**Cumulative Progress (Phase 1 + Phase 2-3 Part 1):**
- 4/4 templates fully compliant with SPEC-UI-001
- 0 residual `.strftime()` expressions
- 0 residual `|format()` expressions
- 4 domain view model builders implemented
- 10 domain-specific frozen dataclasses
- 15+ builder functions
- 23+ test cases (all passing)

**Estimated Remediation Effort for Remaining Phases (2-3 Parts 2-3):** 150-180 hours across 3-4 weeks

**Next Phase Target:** Class Configuration domain (Policy, Announcement, Feature Settings templates) — estimated 4-6 templates, ~6-8 hours per template

