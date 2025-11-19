# Cleanup Duplicate Students (PostgreSQL)

## Problem
Due to an algorithm bug in the previous commit, duplicate students were created when the roster was uploaded twice. The duplicate detection failed because it was using a different hashing algorithm.

## Solution
The bug has been FIXED. Now you need to clean up the existing duplicates.

---

## Step 1: Identify Duplicates

Run this command to see which students are duplicated:

```bash
psql $DATABASE_URL -c "
SELECT
    first_name,
    last_initial,
    block,
    COUNT(*) as count,
    STRING_AGG(id::text, ', ') as student_ids
FROM students
WHERE block IS NOT NULL
GROUP BY first_name, last_initial, block
HAVING COUNT(*) > 1
ORDER BY block, last_initial, first_name;
"
```

This will show you each duplicated student with their IDs.

---

## Step 2: Review Before Deleting

For each set of duplicates, you want to KEEP the student with:
- The LOWEST ID (created first)
- OR the one that has completed setup
- OR the one with transactions/balance

Run this to see details of duplicates:

```bash
psql $DATABASE_URL -c "
SELECT
    id,
    first_name || ' ' || last_initial || '.' as name,
    block,
    has_completed_setup,
    hall_passes
FROM students
WHERE (first_name, last_initial, block) IN (
    SELECT first_name, last_initial, block
    FROM students
    WHERE block IS NOT NULL
    GROUP BY first_name, last_initial, block
    HAVING COUNT(*) > 1
)
ORDER BY block, last_initial, first_name, id;
"
```

---

## Step 3: Delete Duplicates (AUTOMATED - RECOMMENDED)

### Option A: Using psql directly

This will automatically delete all duplicates, keeping the OLDEST record (lowest ID) for each student:

```bash
psql $DATABASE_URL -c "
DELETE FROM students
WHERE id NOT IN (
    SELECT MIN(id)
    FROM students
    WHERE block IS NOT NULL
    GROUP BY first_name, last_initial, block
)
AND (first_name, last_initial, block) IN (
    SELECT first_name, last_initial, block
    FROM students
    WHERE block IS NOT NULL
    GROUP BY first_name, last_initial, block
    HAVING COUNT(*) > 1
);
"
```

### Option B: Using Flask shell (safer, with transaction support)

```bash
flask shell
```

Then run this Python code:

```python
from app.extensions import db
from app.models import Student
from sqlalchemy import func
from collections import defaultdict

# Get all students
students = Student.query.order_by(Student.id).all()

# Group by (first_name, last_initial, block)
groups = defaultdict(list)
for student in students:
    if student.block:
        key = (student.first_name, student.last_initial, student.block)
        groups[key].append(student)

# Find duplicates
duplicates = {k: v for k, v in groups.items() if len(v) > 1}

print(f"Found {len(duplicates)} sets of duplicates")

# Delete duplicates (keep oldest)
deleted_count = 0
for (first_name, last_initial, block), students_list in duplicates.items():
    students_list.sort(key=lambda s: s.id)
    keep = students_list[0]
    to_delete = students_list[1:]

    print(f"{first_name} {last_initial}. in {block}: Keeping ID={keep.id}, Deleting {len(to_delete)} copies")

    for dup in to_delete:
        db.session.delete(dup)
        deleted_count += 1

# Commit changes
db.session.commit()
print(f"✓ Deleted {deleted_count} duplicate records!")
```

---

## Step 4: Verify Cleanup

Check that duplicates are gone:

```bash
psql $DATABASE_URL -c "
SELECT
    block,
    COUNT(*) as student_count
FROM students
WHERE block IS NOT NULL
GROUP BY block
ORDER BY block;
"
```

You should now see roughly half the number of students per block (if you uploaded twice).

---

## Alternative: Manual Deletion (If you want more control)

If you want to manually choose which duplicates to delete:

```bash
# Find a specific duplicate set
psql $DATABASE_URL -c "
SELECT id, first_name, last_initial, block, has_completed_setup
FROM students
WHERE first_name = 'Destiny' AND last_initial = 'M' AND block = 'A';
"

# Delete a specific ID
psql $DATABASE_URL -c "DELETE FROM students WHERE id = 123;"
```

---

## Safety Notes

1. **BACKUP FIRST**: PostgreSQL backup:
   ```bash
   pg_dump $DATABASE_URL > backup_before_cleanup.sql
   ```

2. **If something goes wrong**, restore from backup:
   ```bash
   psql $DATABASE_URL < backup_before_cleanup.sql
   ```

3. **The fix is now in place**: After cleanup, uploading the same roster again will NOT create duplicates.

---

## Quick Copy-Paste Commands

### 1. Backup
```bash
pg_dump $DATABASE_URL > backup_before_cleanup.sql
```

### 2. Delete duplicates
```bash
psql $DATABASE_URL -c "
DELETE FROM students
WHERE id NOT IN (
    SELECT MIN(id)
    FROM students
    WHERE block IS NOT NULL
    GROUP BY first_name, last_initial, block
)
AND (first_name, last_initial, block) IN (
    SELECT first_name, last_initial, block
    FROM students
    WHERE block IS NOT NULL
    GROUP BY first_name, last_initial, block
    HAVING COUNT(*) > 1
);
"
```

### 3. Verify
```bash
psql $DATABASE_URL -c "
SELECT block, COUNT(*) as students
FROM students
GROUP BY block
ORDER BY block;
"
```

---

## What Was Fixed

1. ✅ Reverted to original name code algorithm (vowels from first name + consonants from last name)
2. ✅ Fixed duplicate detection in all three student creation functions
3. ✅ Future uploads will correctly detect and skip duplicates
4. ✅ Students with similar names (like "Destiny Morales" and "Destiny Mora Escobedo") will NOT be incorrectly flagged as duplicates
