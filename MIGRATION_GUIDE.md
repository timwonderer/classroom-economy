# 🔧 Database Migration Guide - Branch Consolidation

## ⚠️ CRITICAL: Branched Migration History Issue (RESOLVED)

### What Was The Problem?

When the `feat-hall-pass-management` branch was created, it branched off from migration `d0ecd9d002b4`.
Meanwhile, staging continued with its own migrations, creating TWO independent migration chains:

```
d0ecd9d002b4 (common ancestor)
    ├──→ f5a1e3e4d7c8 (hall pass) ← Feature branch
    └──→ 2118b1d00805 → ... → 8a4ca17f506f ← Staging branch
```

This is called "multiple heads" in Alembic and will cause `flask db upgrade` to fail.

### ✅ Solution Applied

I created a **merge migration** (`merge_001`) that:
- Has BOTH branch heads as parents: `('8a4ca17f506f', 'f5a1e3e4d7c8')`
- Intelligently applies hall pass changes (rename `passes_left` → `hall_passes`, create `hall_pass_logs` table)
- Checks if changes already exist before applying (idempotent)

## 📋 Migration Steps for Different Environments

### For Production/Staging Database (Currently at 8a4ca17f506f):

1. **Pull the consolidated code**:
   ```bash
   git checkout staging
   git pull origin staging  # After PR is merged
   ```

2. **Run migrations**:
   ```bash
   flask db upgrade
   ```

   This will:
   - Apply the hall pass migration (f5a1e3e4d7c8)
   - Apply the merge migration (merge_001)
   - Result: `passes_left` → `hall_passes`, `hall_pass_logs` table created

### For Development Database (If you've been testing feature branch):

If your local DB already has the hall pass migration applied:

1. **Check current migration**:
   ```bash
   flask db current
   ```

2. **Upgrade**:
   ```bash
   flask db upgrade
   ```

   The merge migration will detect existing changes and skip gracefully.

### Fresh Database Setup:

```bash
flask db upgrade head
```

All migrations will apply in order, no issues.

## 🔍 Verifying Migrations

After upgrading, verify:

```sql
-- Check that students table has hall_passes column
SELECT hall_passes FROM students LIMIT 1;

-- Check that hall_pass_logs table exists
SELECT * FROM hall_pass_logs LIMIT 1;

-- Verify migration history
SELECT * FROM alembic_version;
-- Should show: merge_001
```

## 📊 What Changed in the Database?

### Students Table:
- **Renamed column**: `passes_left` → `hall_passes` (data preserved)
- Type: INTEGER, default 3

### New Table: hall_pass_logs
```sql
CREATE TABLE hall_pass_logs (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL,
    reason VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending, approved, rejected, left_class, returned
    request_time DATETIME NOT NULL,
    decision_time DATETIME,
    left_time DATETIME,
    return_time DATETIME,
    FOREIGN KEY (student_id) REFERENCES students(id)
);
```

## 🚨 Common Issues & Solutions

### Issue: "Multiple heads detected"
**Solution**: You're using old code. Pull the latest with the merge migration.

### Issue: "Column 'passes_left' doesn't exist"
**Solution**: The migration already ran. This is expected. Check for `hall_passes` instead.

### Issue: "Table 'hall_pass_logs' already exists"
**Solution**: The migration is idempotent and will skip. This is safe.

### Issue: Migration fails with "can't drop column passes_left"
**Solution**: Your DB state is unexpected. Check with:
```bash
flask db current
sqlite3 your_database.db ".schema students"
```

## 📝 Migration Chain (Final State)

```
02f217d8b08e (initial)
    ↓
7ed94f24520a (systemadmin)
    ↓
283d887e9b15 (remove second_factor)
    ↓
d0ecd9d002b4
    ├──→ f5a1e3e4d7c8 (hall pass models)
    │       ↓
    │   [MERGE] ← merge_001
    │       ↑
    └──→ 2118b1d00805 → 2b5e304b912b → 5343a19b72e6
            → 8f4a660d5082 → 9e7a8d4f5c6b → d1b3c4d5e6f7 → 8a4ca17f506f
```

## ✅ Pre-Deployment Checklist

Before merging to staging:
- [ ] Review the merge migration code
- [ ] Test migration on a copy of production DB
- [ ] Backup production database
- [ ] Plan rollback strategy (downgrade to 8a4ca17f506f if needed)

Before merging staging to main:
- [ ] Verify all features work on staging
- [ ] Confirm migration completed successfully
- [ ] Check that hall pass features work correctly
- [ ] Verify no data loss in students.hall_passes (should equal old passes_left values)

## 🔄 Rollback Plan

If something goes wrong:

```bash
# Rollback to before hall pass merge
flask db downgrade 8a4ca17f506f

# This will:
# - Drop hall_pass_logs table
# - Rename hall_passes back to passes_left
# - Restore to staging state before merge
```

## 📞 Need Help?

Common commands:
```bash
flask db current          # Show current migration
flask db history          # Show migration history
flask db upgrade          # Apply pending migrations
flask db downgrade <rev>  # Rollback to specific revision
```
