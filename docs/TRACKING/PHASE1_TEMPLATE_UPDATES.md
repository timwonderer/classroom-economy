# Phase 1 Template Updates Checklist

**Status:** In Progress  
**Date:** 2026-08-07  
**Reference:** TEMPLATE_JINJA_INVENTORY.md §554-683

---

## Template 1: student_shop.html

**Current Status:** Routes updated with builders ✅  
**Template Status:** AWAITING UPDATES ⏳

### Required Changes

**Remove Template Logic (Lines 30-39):**

```jinja
{# DELETE THESE LINES #}
{% set rent_item_types = rent_item_types_by_store_id.get(item.id, []) %}
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

**Replace with pre-computed properties from StoreItemCardView:**

```jinja
{# NOW USE PROPERTIES FROM VIEW MODEL #}
{% if item.is_rent_covered %}
{% if item.is_rent_perk_item %}
{% if item.has_any_rent_free_purchase %}
{# etc. #}
```

**Remove Price Formatting (Line 67, 69):**

```jinja
{# BEFORE: #}
<span class="badge bg-primary fs-6">${{ "%.2f"|format(item.price) }}</span>

{# AFTER: #}
<span class="badge bg-primary fs-6">{{ item.display_price }}</span>
```

**Remove Collective Progress Calculations (Lines 100-135):**

```jinja
{# DELETE: #}
{% set progress = collective_progress.get(item.id, {...}) %}

{# DELETE: #}
{{ item.collective_goal_expires_at.strftime('%b %d, %Y') }}

{# REPLACE with: #}
{% if item.collective_progress %}
  {{ item.collective_progress.display_expires_at }}
{% endif %}
```

**Flatten ORM Access in My Items Tab (Lines 198-234):**

```jinja
{# BEFORE: #}
{{ entitlement.store_item.name }}
{{ entitlement.store_item.item_type }}
{{ format_utc_iso(entitlement.purchase_date) }}
{{ entitlement.expiry_date.strftime('%m/%d/%y') }}

{# AFTER: #}
{{ entitlement.item_name }}
{{ entitlement.item_type }}
{{ entitlement.display_purchased_date }}
{{ entitlement.display_expiry_date }}
```

### Verification Steps

- [ ] All items access pre-formatted `display_price` not `price`
- [ ] All rent flags use item properties (item.is_rent_covered, item.is_rent_perk_item, etc.)
- [ ] All collective progress uses `item.collective_progress` view model or None
- [ ] All entitlements access flattened properties (item_name, item_type, display_dates)
- [ ] No `.strftime()` calls remain in template
- [ ] No `format_utc_iso()` filter calls remain
- [ ] No percentage formatting filters remain

---

## Template 2: admin_rent_settings.html

**Current Status:** Routes updated with builders ✅  
**Template Status:** AWAITING UPDATES ⏳

### Required Changes in Template 2

**Use Pre-Computed Student Counts (Lines 178, 191):**

```jinja
{# TEMPLATE ALREADY CORRECT: #}
{{ obligation_summary.current_student_count if obligation_summary else 0 }}
{{ obligation_summary.behind_student_count if obligation_summary else 0 }}
```

**Verify Usage Pattern:**
The route now calls `add_display_formatting_to_class_obligation_summary()` which adds:

- `obligation_summary.current_student_count` (students with status up_to_date or outstanding)
- `obligation_summary.behind_student_count` (students with status past_due_grace or past_due_overdue)
- `obligation_summary.display_total_paid` (pre-formatted as "$X.XX")
- `obligation_summary.display_total_unpaid` (pre-formatted as "$X.XX")

### Verification Steps in Template 2

- [ ] Lines 178, 191 use `current_student_count` and `behind_student_count` (already done ✅)
- [ ] Currency formatting moved to view model (display_total_paid, display_total_unpaid)
- [ ] No direct access to `status_breakdown` dict properties
- [ ] All amounts are pre-formatted strings starting with "$"

---

## Template 3: admin_payroll.html

**Current Status:** Routes updated with builders ✅  
**Template Status:** AWAITING UPDATES ⏳

### Required Changes in Template 3

**Update Student Stats Loop:**
student_stats is now a list of `StudentPayrollStatusView` objects with pre-formatted display fields:

```jinja
{# REPLACE raw stats with view models #}
{% for stat in student_stats %}
  {# BEFORE: #}
  {{ "%.2f"|format(stat.estimated_payout) }}
  {{ stat.total_earned }}

  {# AFTER: #}
  {{ stat.display_earnings_this_period }}
  {{ stat.display_total_earnings_all_time }}
{% endfor %}
```

**Use PayrollConfigurationView (if display exists):**

```jinja
{# If payroll_config is passed: #}
{{ payroll_config.display_pay_rate }}
{{ payroll_config.display_next_payroll_date }}
{{ payroll_config.display_total_payroll_amount }}
{{ payroll_config.display_overtime_multiplier }}
```

### Verification Steps in Template 3

- [ ] All earnings amounts use pre-formatted display fields
- [ ] No `"%.2f"|format()` filters remain
- [ ] No date `.strftime()` calls remain
- [ ] All numbers displayed via view model properties

---

## Build Verification

After template updates, verify:

```bash
# 1. Run tests
pytest tests/test_student_routes.py::test_student_shop -v
pytest tests/test_admin_routes.py::test_rent_settings -v
pytest tests/test_admin_routes.py::test_payroll -v

# 2. Manual testing
# - student_shop.html: Rent items, collective progress, entitlements
# - admin_rent_settings.html: Obligation summary totals
# - admin_payroll.html: Student earnings display

# 3. Audit compliance
# Verify no new Jinja filter usage
grep -n "strftime\|format(" templates/student_shop.html
grep -n "strftime\|format(" templates/admin_rent_settings.html
grep -n "strftime\|format(" templates/admin_payroll.html
```

---

## Audit Compliance Summary

### Violations Fixed

| Template | Violation | Status |
| ---------- | ----------- | -------- |
| student_shop.html | Lines 30-39 complex rent logic | ✅ View model computed |
| student_shop.html | Lines 100-135 collective progress | ✅ View model computed |
| student_shop.html | Lines 198-234 ORM traversal | ✅ Flattened in view |
| admin_rent_settings.html | Lines 178, 191 ORM aggregation | ✅ Display fields added |
| admin_payroll.html | 74 vars, 151 tags | ✅ View models provided |

### Pattern Fixes

- ✅ Pattern 1: Raw numeric variables → Pre-formatted display strings
- ✅ Pattern 2: ORM `.strftime()` → Pre-formatted display strings
- ✅ Pattern 3: Template-computed business logic → View models
- ✅ Pattern 4: ORM traversals → Flattened view properties
- ✅ Pattern 5: Custom Jinja filters → Pre-computed values
- ✅ Pattern 6: ORM model access → View model properties

---

## Timeline

- Phase 1 Builders: ✅ Complete (2026-08-07)
- Phase 1 Routes: ✅ Complete (2026-08-07)
- Phase 1 Templates: ⏳ In Progress (estimated 2026-08-07/08)
- Phase 1 Testing: ⏳ Pending
- Phase 1 Audit Update: ⏳ Pending

---

**Next Steps:**

1. Update student_shop.html template
2. Update admin_rent_settings.html template
3. Update admin_payroll.html template
4. Run test suite and manual testing
5. Update TEMPLATE_JINJA_INVENTORY.md to mark violations as FIXED
6. Create Phase 1 completion commit
