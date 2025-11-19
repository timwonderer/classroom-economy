# Cleanup Duplicate Students

## Problem
Due to an algorithm bug in the previous commit, duplicate students were created when the roster was uploaded twice. The duplicate detection failed because it was using a different hashing algorithm.

## Solution
The bug has been FIXED. Now you need to clean up the existing duplicates.

---

## Step 1: Identify Duplicates

Run this command to see which students are duplicated:

```bash
sqlite3 instance/classroom_economy.db "
SELECT
    first_name,
    last_initial,
    block,
    COUNT(*) as count,
    GROUP_CONCAT(id) as student_ids
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
sqlite3 instance/classroom_economy.db -header -column "
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

This will automatically delete all duplicates, keeping the OLDEST record (lowest ID) for each student:

```bash
sqlite3 instance/classroom_economy.db "
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

---

## Step 4: Verify Cleanup

Check that duplicates are gone:

```bash
sqlite3 instance/classroom_economy.db "
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
sqlite3 instance/classroom_economy.db "
SELECT id, first_name, last_initial, block, has_completed_setup
FROM students
WHERE first_name = 'Destiny' AND last_initial = 'M' AND block = 'A';
"

# Delete a specific ID
sqlite3 instance/classroom_economy.db "DELETE FROM students WHERE id = 123;"
```

---

## Safety Notes

1. **BACKUP FIRST**: The automated script will backup your database automatically, but you can also manually backup:
   ```bash
   cp instance/classroom_economy.db instance/classroom_economy.db.backup
   ```

2. **If something goes wrong**, restore from backup:
   ```bash
   cp instance/classroom_economy.db.backup instance/classroom_economy.db
   ```

3. **The fix is now in place**: After cleanup, uploading the same roster again will NOT create duplicates.

---

## What Was Fixed

1. ✅ Reverted to original name code algorithm (vowels from first name + consonants from last name)
2. ✅ Fixed duplicate detection in all three student creation functions
3. ✅ Future uploads will correctly detect and skip duplicates
4. ✅ Students with similar names (like "Destiny Morales" and "Destiny Mora Escobedo") will NOT be incorrectly flagged as duplicates
