# Cleanup Duplicate Students

## Problem
Due to an algorithm bug in a previous commit, duplicate students were created when the roster was uploaded twice. The duplicate detection failed because it was using a different hashing algorithm.

## Solution
The bug has been FIXED. Now you need to clean up the existing duplicates.

---

## ⚠️ IMPORTANT: Why Raw SQL Won't Work

**You MUST use the Flask script** - raw PostgreSQL/psql commands will NOT work because:

- `Student.first_name` is encrypted (PIIEncryptedType with Fernet)
- Same name encrypts differently each time (random IV)
- SQL `GROUP BY first_name` sees each encryption as unique → no duplicates detected
- Only SQLAlchemy can decrypt and properly compare names

**Bottom line:** Use the Python script below. Raw SQL queries will fail silently.

---

## Cleanup Method: Use Flask Script

### Step 1: List duplicates
```bash
python scripts/cleanup_duplicates_flask.py --list
```

This will show you all duplicate students and which ones will be kept/deleted.

### Step 2: Delete duplicates
```bash
python scripts/cleanup_duplicates_flask.py --delete
```

This automatically:
- **Migrates ALL related data** (transactions, attendance, hall passes, etc.) from duplicate → student being kept
- **Deletes the duplicate** safely (no foreign key violations)
- **Preserves all financial and attendance history**

**That's it!** The script uses SQLAlchemy which properly handles encrypted fields.

---

## For DigitalOcean Deployment

SSH into your server and run:

```bash
# Navigate to app directory
cd /path/to/classroom-economy

# Activate virtual environment (if using one)
source venv/bin/activate

# List duplicates first
python scripts/cleanup_duplicates_flask.py --list

# Review the output, then delete
python scripts/cleanup_duplicates_flask.py --delete
```

---

## For Render.com Deployment

1. Go to your web service dashboard
2. Click the "Shell" tab
3. Run:
   ```bash
   python scripts/cleanup_duplicates_flask.py --list
   python scripts/cleanup_duplicates_flask.py --delete
   ```

---

## What the Script Does

### Detection Phase (`--list`)
- Loads all students via SQLAlchemy (auto-decrypts names)
- Groups by `(first_name, last_initial, block)` in Python
- Shows which duplicates will be kept vs. deleted
- Shows how many related records will be migrated

### Cleanup Phase (`--delete`)
For each set of duplicates:
1. **Keeps** the student with the lowest ID (created first)
2. **Migrates** all related records from duplicates to the kept student:
   - Transactions (preserves financial history)
   - Tap Events (preserves attendance)
   - Hall Pass Logs
   - Student Items (purchases)
   - Rent Payments
   - Rent Waivers
   - Insurance Enrollments
   - Insurance Claims
3. **Deletes** the duplicate student record
4. **Commits** everything in one database transaction

---

## Safety Features

- **Preview mode**: `--list` shows exactly what will happen
- **3-second countdown**: Gives you time to cancel with Ctrl+C
- **Data preservation**: All transactions and history are migrated, not lost
- **Single transaction**: All changes commit together (all or nothing)
- **Keeps oldest**: Always preserves the original student record

---

## Example Output

```
⚠️  Found 2 sets of duplicate students:
====================================================================================================

Destiny M. in Block A:
  Found 2 copies (will keep oldest, delete 1)
  ✓ KEEP: ID=45, Setup=True, Checking=$150.00, Savings=$50.00
  ✗ DELETE: ID=78, Setup=False, Checking=$0.00, Savings=$0.00
    → Will migrate 15 related records (txns:12, taps:3, halls:0, items:0, rent:0, ins:0, claims:0)

John S. in Block B:
  Found 2 copies (will keep oldest, delete 1)
  ✓ KEEP: ID=12, Setup=True, Checking=$200.00, Savings=$100.00
  ✗ DELETE: ID=46, Setup=False, Checking=$0.00, Savings=$0.00
    → Will migrate 8 related records (txns:5, taps:3, halls:0, items:0, rent:0, ins:0, claims:0)

====================================================================================================

Total: 2 duplicate records will be deleted
Total: 23 related records will be migrated to kept students
```

---

## Verification After Cleanup

After running the cleanup, verify the results:

```bash
# Run list again - should show "No duplicates found!"
python scripts/cleanup_duplicates_flask.py --list

# Check student counts look correct
# (should be roughly half if you uploaded twice)
```

You can also check in the admin panel that student counts per block are correct.

---

## What Was Fixed

1. ✅ Reverted to original name code algorithm (vowels from first name + consonants from last name)
2. ✅ Fixed duplicate detection in all three student creation functions
3. ✅ Future uploads will correctly detect and skip duplicates
4. ✅ Students with similar names (like "Destiny Morales" and "Destiny Mora Escobedo") will NOT be incorrectly flagged as duplicates
5. ✅ Cleanup script migrates all related data before deletion (no data loss)
