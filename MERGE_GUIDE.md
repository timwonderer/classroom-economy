# Merge Conflict Resolution Guide

## Status
✅ **Conflict Resolution Tested & Documented**

The feature branch `claude/revamp-class-store-page-01HYq4SktP2xFB4bLTZXdCA7` has **one file conflict** with main that needs manual resolution when merging.

---

## Conflict Summary

### File: `app/routes/api.py`

**Main branch**: Has the original store revamp WITHOUT validation guards
**Feature branch**: Has P1 bug fixes WITH None guards

**Conflicts occur in 4 locations:**
1. Line ~64: Bulk discount price calculation
2. Line ~135: Bundle item creation
3. Line ~147: Bundle safety fallback
4. Line ~200-210: Success message generation

---

## How to Merge

### Option 1: Automated Resolution (Recommended)

```bash
# 1. Checkout main
git checkout main
git pull origin main

# 2. Merge the feature branch
git merge claude/revamp-class-store-page-01HYq4SktP2xFB4bLTZXdCA7

# 3. Resolve conflicts by accepting the FEATURE BRANCH version (ours)
# For each conflict, take the version WITH None guards
git checkout --ours app/routes/api.py   # WRONG - takes main version
git checkout --theirs app/routes/api.py # CORRECT - takes feature branch

# 4. Verify and commit
git add app/routes/api.py
git commit
git push origin main
```

### Option 2: Manual Resolution (If you want to review)

When you see conflicts like this:

```python
<<<<<<< HEAD
if item.bulk_discount_enabled and quantity >= item.bulk_discount_quantity:
=======
if (item.bulk_discount_enabled and
    item.bulk_discount_quantity is not None and
    item.bulk_discount_percentage is not None and
    quantity >= item.bulk_discount_quantity):
>>>>>>> claude/revamp-class-store-page-01HYq4SktP2xFB4bLTZXdCA7
```

**ALWAYS choose the version BELOW the `=======` line** (the feature branch version with None guards).

#### Resolution Rules:

| Conflict | Choose This Version | Why |
|----------|-------------------|-----|
| Line 64 (discount calc) | Feature branch (with None checks) | Prevents TypeError when discount fields are None |
| Line 135 (bundle creation) | Feature branch (with None checks) | Prevents TypeError when bundle_quantity is None |
| Line 147 (bundle fallback) | Feature branch (add elif block) | Adds safety fallback for corrupted data |
| Line 200-210 (success message) | Feature branch (with None checks) | Prevents crashes in message generation |

---

## What Each Version Does

### ❌ Main Branch Version (WITHOUT guards)
```python
if item.bulk_discount_enabled and quantity >= item.bulk_discount_quantity:
```
**Problem**: Crashes with `TypeError` if `bulk_discount_quantity` is `None`

### ✅ Feature Branch Version (WITH guards)
```python
if (item.bulk_discount_enabled and
    item.bulk_discount_quantity is not None and
    item.bulk_discount_percentage is not None and
    quantity >= item.bulk_discount_quantity):
```
**Solution**: Safely checks for None before comparison

---

## After Merging

1. **Clear Python cache**:
   ```bash
   find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
   find . -type f -name "*.pyc" -delete
   ```

2. **Reload application**:
   ```bash
   touch wsgi.py
   ```

3. **Test the store**:
   - Create a bundle item (ensure bundle quantity is required)
   - Create a bulk discount item (ensure discount fields are required)
   - Try purchasing both types

---

## Files Changed in Merge

| File | Status | Notes |
|------|--------|-------|
| `app/routes/api.py` | ⚠️ CONFLICT | Resolve with feature branch version |
| `forms.py` | ✅ Auto-merged | Validation methods added cleanly |
| `deploy_updates.sh` | ✅ Auto-merged | Deployment script added cleanly |

---

## Critical P1 Fixes Included

### 1. Bundle/Discount Validation (forms.py)

The merged code includes form-level validation:

```python
def validate_bundle_quantity(self, field):
    if self.is_bundle.data and (not field.data or field.data <= 0):
        raise ValidationError('Bundle quantity is required when creating a bundled item.')

def validate_bulk_discount_quantity(self, field):
    if self.bulk_discount_enabled.data and (not field.data or field.data <= 0):
        raise ValidationError('Minimum quantity is required when bulk discount is enabled.')

def validate_bulk_discount_percentage(self, field):
    if self.bulk_discount_enabled.data:
        if not field.data or field.data <= 0:
            raise ValidationError('Discount percentage is required.')
        if field.data > 100:
            raise ValidationError('Discount percentage cannot exceed 100%.')
```

### 2. Hall Pass Limit Bypass Fix (app/routes/api.py)

Fixed critical bug where multi-quantity hall pass purchases bypassed per-student limits:

**Problem:**
- Old code used exact string match: `description="Purchase: Hall Pass"`
- New quantity format: `"Purchase: Hall Pass (x3)"`
- Exact match failed → limit checks counted 0 prior purchases
- Students could buy unlimited passes in bulk

**Solution:**
```python
# Use LIKE query to match description prefix
transactions = Transaction.query.filter(
    Transaction.student_id == student.id,
    Transaction.type == 'purchase',
    Transaction.description.like(f"Purchase: {item.name}%")
).all()

# Parse and sum quantities from all matching transactions
total_purchased = 0
for txn in transactions:
    match = re.search(r'\(x(\d+)\)', txn.description)
    if match:
        total_purchased += int(match.group(1))
    else:
        total_purchased += 1  # No suffix = quantity 1
```

**Result:** Limits now correctly enforce based on total quantity purchased, not transaction count.

---

## Quick Reference

**Accept ALL feature branch changes for app/routes/api.py**

The feature branch has the critical P1 bug fixes that prevent application crashes.
