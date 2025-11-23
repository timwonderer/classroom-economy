# Fix insurance policy scoping and add marketing badges

## Summary

This PR fixes a critical scoping issue with insurance policies and adds fun marketing badge features for teachers to use when promoting insurance plans to students.

## Problem: Schrödinger's Insurance 🐱📦

Students could see insurance policies from **all teachers** in the system, not just their own. This created a quantum state where:
- ✅ Admin sees "Paycheck Protection Classic" (their policy)
- ❌ Admin doesn't see "Basic Paycheck Protection" (created by another teacher or has NULL teacher_id)
- ✅ Student sees BOTH policies (bug!)

Additionally, the student portal had hardcoded styling that made the 3rd policy in the database always show as "Best Value!" regardless of its actual attributes.

## Changes

### 1. Insurance Policy Scoping Fix

**Security & Data Isolation:**
- Students now only see insurance policies from their associated teachers
- Added teacher_id verification in purchase route to prevent cross-teacher purchases
- Properly scopes `InsurancePolicy.query` to filter by student's teacher IDs

**Files Changed:**
- `app/routes/student.py`: Filter policies by `teacher_id.in_(teacher_ids)`
- `app/routes/student.py`: Add authorization check in purchase route

### 2. Orphaned Policy Detection Tool

Created diagnostic script to find insurance policies with `NULL` teacher_id:
- `check_orphaned_insurance.py`: Lists policies without teacher ownership
- Shows enrollment counts and available teachers for reassignment
- Helps identify policies invisible in admin panel but visible to students

### 3. Marketing Badges System

**Teacher Control:**
Teachers can now add marketing badges to insurance policies through the admin panel.

**17 Badge Options:**

**Serious badges:**
- Best Value! (⭐ grade)
- Most Popular (📈 trending_up)
- Recommended (✓ verified)
- Premium Coverage (🏅 workspace_premium)
- Limited Time Offer (⏰ schedule)
- New! (🆕 new_releases)
- Fan Favorite (❤️ favorite)

**Fun/Silly badges:**
- YOLO Protection (🎲 casino)
- Trust Me Bro (🤝 handshake)
- Definitely Not a Scam (✓ verified_user)
- Your Parents Would Approve (👨‍👩‍👧 family_restroom)
- As Seen on TV (📺 live_tv)
- Industry Leading* (🏆 emoji_events)
- Chaos Insurance (🌀 tornado)
- The Responsible Choice™ (✓ check_circle)
- The One Your Friend Has (👥 groups)

**Visual Styling:**
- Each badge has unique color scheme (primary, danger, warning, success, info, dark)
- Optional thick colored borders for emphasis
- Material Symbol icons display inline with badge text
- Replaces hardcoded loop.index styling with actual policy attributes

**Files Changed:**
- `app/models.py`: Add `marketing_badge` column
- `forms.py`: Add SelectField with 17 badge choices
- `app/routes/admin.py`: Handle marketing_badge in create/edit
- `templates/student_insurance_marketplace.html`: Display badges with colors and icons
- `migrations/versions/a2b3c4d5e6f7_add_marketing_badge_to_insurance.py`: Migration file

### 4. Dashboard Improvements

**Replace Item Status Card:**
The "Item Status" card (showing Pending/Redeemed/Expired counts) was removed because it showed all zeros and wasted valuable dashboard space.

**New: Recent Transactions Card:**
- Shows 5 most recent transactions
- Material Symbol icons:
  - `add_circle` (green) for deposits/credits
  - `remove_circle` (red) for withdrawals/charges
- Displays: description, timestamp, account type badge, amount
- "View All Transactions" button → finances page
- Empty state with large `receipt_long` icon

**Files Changed:**
- `app/routes/student.py`: Add `recent_transactions[:5]` to context
- `templates/student_dashboard.html`: Replace Item Status with Recent Transactions

## Database Migration

Run this migration on production:
```bash
flask db upgrade
```

This adds the `marketing_badge` column to `insurance_policies` table.

## Testing Checklist

- [x] Students only see policies from their teachers
- [x] Students cannot purchase policies from other teachers (even with direct URL)
- [x] Marketing badges display correctly with colors and icons
- [x] Recent transactions show on dashboard with proper formatting
- [x] Material Symbols render correctly (no emoji fallbacks)
- [ ] Run `check_orphaned_insurance.py` on production to find orphaned policies

## Screenshots

### Before:
- Students saw ALL policies from any teacher
- 3rd policy always showed "Best Value!" (hardcoded)
- Item Status card showed useless 0/0/0 counts

### After:
- Students see only their teacher's policies
- Teachers control which badge appears on each policy
- Dashboard shows useful recent transactions

## Notes

- The orphaned policy script is diagnostic only - it doesn't auto-fix issues
- Teachers need to manually select badges when creating/editing policies
- No badge selected = no marketing badge displayed (clean default)
- Material Symbols are already loaded in the app, so no new dependencies

## Breaking Changes

None - this is purely additive with one security fix.

## Related Issues

Fixes: "Schrödinger's insurance - policies both exist and don't exist"
