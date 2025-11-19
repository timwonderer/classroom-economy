# Cleanup Duplicate Students (PostgreSQL)

## Problem
Due to an algorithm bug in the previous commit, duplicate students were created when the roster was uploaded twice. The duplicate detection failed because it was using a different hashing algorithm.

## Solution
The bug has been FIXED. Now you need to clean up the existing duplicates.

---

## EASIEST METHOD: Use the Flask Cleanup Script

### Step 1: List duplicates
```bash
python cleanup_duplicates_flask.py --list
```

This will show you all duplicate students and which ones will be kept/deleted.

### Step 2: Delete duplicates
```bash
python cleanup_duplicates_flask.py --delete
```

This automatically deletes duplicates, keeping the oldest (lowest ID) for each student.

**That's it!** The script uses your existing Flask database connection, so no need to figure out DATABASE_URL.

---

## Alternative: Direct PostgreSQL Commands

If you prefer SQL commands or the Flask script doesn't work:

### Step 1: Get your DATABASE_URL

First, you need to find your database connection string. Check one of these:
- Environment variable: `echo $DATABASE_URL`
- Your hosting platform (Render, Heroku, Railway, etc.)
- Your `.env` file (if you have one locally)

The URL format is usually:
```
postgresql://username:password@host:port/database
```

### Step 2: Backup
```bash
pg_dump "YOUR_DATABASE_URL_HERE" > backup_before_cleanup.sql
```

### Step 3: List duplicates
```bash
psql "YOUR_DATABASE_URL_HERE" -c "
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

### Step 4: Delete duplicates
```bash
psql "YOUR_DATABASE_URL_HERE" -c "
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

### Step 5: Verify
```bash
psql "YOUR_DATABASE_URL_HERE" -c "
SELECT block, COUNT(*) as students
FROM students
GROUP BY block
ORDER BY block;
"
```

---

## For Render.com Users

If you're hosting on Render:

1. Go to your Render dashboard
2. Click on your PostgreSQL database
3. Copy the "External Database URL"
4. Use that URL in the commands above

Or use Render's shell:
1. Go to your web service
2. Click "Shell" tab
3. Run: `python cleanup_duplicates_flask.py --list`
4. Then: `python cleanup_duplicates_flask.py --delete`

---

## Manual Deletion (If you want control)

If you want to manually choose which duplicates to delete:

```bash
# Find a specific duplicate set
psql "YOUR_DATABASE_URL" -c "
SELECT id, first_name, last_initial, block, has_completed_setup
FROM students
WHERE first_name = 'Destiny' AND last_initial = 'M' AND block = 'A';
"

# Delete a specific ID
psql "YOUR_DATABASE_URL" -c "DELETE FROM students WHERE id = 123;"
```

---

## What Was Fixed

1. ✅ Reverted to original name code algorithm (vowels from first name + consonants from last name)
2. ✅ Fixed duplicate detection in all three student creation functions
3. ✅ Future uploads will correctly detect and skip duplicates
4. ✅ Students with similar names (like "Destiny Morales" and "Destiny Mora Escobedo") will NOT be incorrectly flagged as duplicates
