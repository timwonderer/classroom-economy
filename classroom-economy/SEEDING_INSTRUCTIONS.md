# Multi-Tenancy Test Data Seeding Instructions

This document explains how to use the `seed_multi_tenancy_test_data.py` script to populate your database with comprehensive test data for validating the join_code-based multi-tenancy fixes.

## 🎯 Purpose

The seeding script creates realistic test data specifically designed to validate:

1. **Cross-teacher data isolation** - Students enrolled with different teachers see separate data
2. **Same-teacher multi-period isolation** - Students with the same teacher in different periods see isolated data per period
3. **Join code as source of truth** - All data (transactions, balances, items, insurance) properly scoped by join_code

## 📋 Prerequisites

Before running the script:

1. **Database migration must be applied**:
   ```bash
   flask db upgrade
   ```
   This adds the `join_code` column to the `transaction` table.

2. **Environment variables set**:
   - `PEPPER_KEY` (auto-set by script if missing for testing)
   - `ENCRYPTION_KEY` (auto-set by script if missing for testing)
   - `DATABASE_URL` or configured in your Flask app

3. **Python dependencies installed**:
   ```bash
   pip install -r requirements.txt
   ```

## 🚀 Running the Script

### Basic Usage

```bash
python seed_multi_tenancy_test_data.py
```

The script will:
- Create 4 teachers with 2-3 class periods each (10 total class periods)
- Create 15 students with various enrollment patterns
- Generate 8-15 transactions per enrollment (all with join_code)
- Create store items (some unique to classes, some shared)
- Create insurance policies (tiered and independent)
- Create payroll and rent settings for each period
- Purchase insurance for ~40% of students
- Output all credentials to `TEST_CREDENTIALS.txt`

### Expected Output

```
🌱 Starting database seeding...
============================================================

📚 Creating teachers and class periods...
  ✓ Created teacher: ms_johnson
    • Period A: English 1st Period (Join: A7K2M9)
    • Period B: English 3rd Period (Join: P3XW8R)
    ...

👥 Creating students...
  Student: Emma Evans
    ✓ Enrolled in ms_johnson - English 1st Period (A7K2M9)
    ✓ Enrolled in ms_johnson - English 3rd Period (P3XW8R)
  ...

📝 Writing credentials to file...
✅ Credentials written to: TEST_CREDENTIALS.txt

📊 SEEDING SUMMARY
============================================================
Teachers created: 4
Students created: 15
Class periods (seats): 25
Transactions created: 250
  - With join_code: 250
  - Without join_code: 0
Store items: 45
Insurance policies: 18
Student insurance purchases: 10
Insurance claims: 3
Payroll settings: 10
Rent settings: 10
============================================================

✨ Seeding complete!
```

## 📖 Test Data Structure

### Teachers Created

1. **ms_johnson** (English teacher)
   - Period A: English 1st Period
   - Period B: English 3rd Period
   - Period C: English 5th Period

2. **mr_smith** (Math teacher)
   - Period A: Math Period 1
   - Period D: Math Period 4

3. **mrs_davis** (Science teacher)
   - Period B: Science 2nd Period
   - Period E: Science 6th Period

4. **dr_wilson** (History teacher)
   - Period F: History Period 7

### Student Enrollment Patterns

#### Single Teacher, Single Period (Control Group)
- **Alice Anderson** - ms_johnson Period A only
- **Bob Baker** - mr_smith Period A only

#### Multiple Different Teachers
- **Carol Chen** - ms_johnson Period A + mr_smith Period A
- **David Davis** - mr_smith Period D + mrs_davis Period B
- **Henry Harris** - ms_johnson Period A + mr_smith Period A + mrs_davis Period B

#### Same Teacher, Multiple Periods (CRITICAL TEST CASES) 🔥
- **Emma Evans** - ms_johnson Period A + Period B
- **Frank Fisher** - ms_johnson Period B + Period C
- **Grace Garcia** - mr_smith Period A + Period D

These are the **most critical** test cases for validating period-level isolation!

### Generated Data Per Enrollment

For each student enrollment (student + teacher + period):

- **8-15 transactions** with correct join_code, including:
  - Daily attendance rewards
  - Quiz bonuses
  - Homework completion
  - Participation points
  - Penalties/fines
  - Transfers between checking/savings
  - Interest payments
  - Purchases
  - Rent payments

- **40% chance** of insurance purchase
  - 60% of purchases are past waiting period
  - Some have claims filed

- **Period-specific settings**:
  - Payroll rate and schedule
  - Rent amount and frequency

## 🧪 Credentials Output

All login credentials are written to `TEST_CREDENTIALS.txt`:

### Teacher Login
Teachers use TOTP (Time-based One-Time Passwords). The credentials file includes:
- Username
- TOTP secret (for generating codes)
- TOTP provisioning URL (for QR code generation)

**Example**:
```
Username: ms_johnson
TOTP Secret: JBSWY3DPEHPK3PXP
TOTP Setup URL: otpauth://totp/ClassroomEconomy:ms_johnson?secret=JBSWY3DPEHPK3PXP&issuer=ClassroomEconomy
```

To generate TOTP codes for testing:
```python
import pyotp
totp = pyotp.TOTP('JBSWY3DPEHPK3PXP')
print(totp.now())  # Current 6-digit code
```

Or use an authenticator app:
- Scan the QR code from the provisioning URL
- Or manually enter the secret

### Student Login
Students use username + password (credential):
```
Username: emmae2009
Password: E2009
```

Format: `{firstname}{lastinitial}{dob_sum}`

### Class Join Codes
Each period has a unique 6-character join code:
```
ms_johnson - Period A: English 1st Period
  Join Code: A7K2M9
```

## ✅ Validation Checklist

After seeding, test the following scenarios:

### 1. Same Teacher, Different Periods (CRITICAL!)

**Test Case**: Emma Evans enrolled in ms_johnson Periods A & B

Steps:
1. Login as Emma (username: `emmae2009`, password: `E2009`)
2. Select Period A context
3. Note the checking balance (e.g., $150)
4. View transaction history - should only show Period A transactions
5. Switch to Period B context
6. Check balance again - should be DIFFERENT (e.g., $200)
7. Transaction history should show ONLY Period B transactions

**Expected Result**: ✅ Complete isolation between periods
- Balances are different for each period
- Transactions filtered by join_code
- No mixing of data

**Failure Case**: ❌ If balances are combined or transactions mixed, join_code isolation is broken!

### 2. Different Teachers

**Test Case**: Carol Chen enrolled with ms_johnson and mr_smith

Steps:
1. Login as Carol
2. Select ms_johnson's class
3. Note balance and transactions
4. Switch to mr_smith's class
5. Verify different balance and transaction set

**Expected Result**: ✅ No cross-teacher data leakage

### 3. Store Items Visibility

**Test Case**: Period-specific vs. shared items

Steps:
1. Login as teacher ms_johnson
2. Check store items for Period A
3. Some items should be visible to all periods (Homework Pass, Extra Credit)
4. Some items should be Period A only (check block visibility settings)

**Expected Result**: ✅ Block visibility respected

### 4. Insurance Policies

**Test Case**: Tiered policies and block visibility

Steps:
1. View insurance marketplace as student in different periods
2. Check which policies are available
3. Verify tiered policies (Paycheck Protection Basic/Standard/Premium) are grouped
4. Confirm block visibility filtering works

**Expected Result**: ✅ Policies filtered by period

### 5. Transaction join_code Population

**Database Check**:
```sql
-- All transactions should have join_code populated
SELECT COUNT(*) FROM transaction WHERE join_code IS NULL;
-- Should return 0

-- Verify transactions are distributed across join codes
SELECT join_code, COUNT(*) as count
FROM transaction
GROUP BY join_code
ORDER BY count DESC;
```

**Expected Result**: ✅ Zero NULL join_codes

### 6. Balance Calculations

**Test Case**: Manual balance verification

Steps:
1. For a multi-period student, query database directly:
```sql
SELECT
    join_code,
    SUM(amount) as balance
FROM transaction
WHERE student_id = (SELECT id FROM students WHERE username_lookup_hash = ...)
  AND account_type = 'checking'
  AND is_void = false
GROUP BY join_code;
```

2. Compare with balances shown in UI for each period

**Expected Result**: ✅ UI balances match per-join_code database calculations

## 🔧 Troubleshooting

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'pyotp'`

**Solution**:
```bash
pip install pyotp
```

### Database Migration Not Applied

**Error**: `column transaction.join_code does not exist`

**Solution**:
```bash
flask db upgrade
```

### Existing Data Conflicts

**Error**: `duplicate key value violates unique constraint`

**Solution**: Either:
1. Clear existing test data first (CAREFUL - only in development!)
2. Or modify the script to use different usernames/codes

### Pepper Key Error

**Error**: `KeyError: 'PEPPER_KEY'`

**Solution**: Set environment variable or let script auto-set for testing:
```bash
export PEPPER_KEY="your_pepper_key_here"
```

## 📊 Data Analysis Queries

After seeding, use these queries to analyze the data:

### Transaction Distribution by Join Code
```sql
SELECT
    tb.join_code,
    a.username as teacher,
    tb.block as period,
    COUNT(t.id) as transaction_count,
    COUNT(DISTINCT t.student_id) as student_count
FROM transaction t
JOIN teacher_blocks tb ON t.join_code = tb.join_code
JOIN admins a ON tb.teacher_id = a.id
GROUP BY tb.join_code, a.username, tb.block
ORDER BY a.username, tb.block;
```

### Students with Multiple Periods (Same Teacher)
```sql
SELECT
    s.id,
    CONCAT(s.first_name, ' ', s.last_initial, '.') as student_name,
    a.username as teacher,
    COUNT(DISTINCT tb.block) as period_count,
    STRING_AGG(DISTINCT tb.block || ' (' || tb.join_code || ')', ', ') as periods
FROM students s
JOIN teacher_blocks tb ON s.id = tb.student_id
JOIN admins a ON tb.teacher_id = a.id
WHERE tb.is_claimed = true
GROUP BY s.id, s.first_name, s.last_initial, a.username
HAVING COUNT(DISTINCT tb.block) > 1
ORDER BY teacher, period_count DESC;
```

### Insurance Coverage Status
```sql
SELECT
    s.first_name,
    s.last_initial,
    ip.title as policy,
    si.status,
    si.purchase_date,
    si.coverage_start_date,
    CASE
        WHEN si.coverage_start_date <= NOW() THEN 'ACTIVE'
        ELSE 'WAITING'
    END as coverage_status,
    COUNT(ic.id) as claims_filed
FROM students s
JOIN student_insurance si ON s.id = si.student_id
JOIN insurance_policies ip ON si.policy_id = ip.id
LEFT JOIN insurance_claims ic ON si.id = ic.student_insurance_id
GROUP BY s.id, s.first_name, s.last_initial, ip.title, si.status,
         si.purchase_date, si.coverage_start_date
ORDER BY s.first_name;
```

## 🎓 Testing Workflow

Recommended testing workflow after seeding:

1. **Phase 1: Database Verification**
   - Run SQL queries to verify data structure
   - Confirm all transactions have join_code
   - Check enrollment patterns

2. **Phase 2: UI Testing - Single Period Students**
   - Login as Alice or Bob (single enrollment)
   - Verify basic functionality works
   - Confirm balances and transactions display correctly

3. **Phase 3: UI Testing - Same Teacher Multi-Period** ⭐ **CRITICAL**
   - Login as Emma, Frank, or Grace
   - Switch between periods
   - Verify complete data isolation
   - Check balance calculations
   - Verify transaction filtering

4. **Phase 4: UI Testing - Multiple Teachers**
   - Login as Carol, David, or Henry
   - Switch between different teachers' classes
   - Verify cross-teacher isolation

5. **Phase 5: Feature Testing**
   - Test store purchases in different periods
   - Test insurance claims
   - Test transfers between accounts
   - Test rent payments

6. **Phase 6: Edge Cases**
   - Rapidly switch between classes
   - Test session management
   - Verify no session bleed between contexts

## 📝 Notes

- **All transactions include join_code** - This is the key fix!
- **Session tracks current_join_code** - Not just teacher_id
- **Queries filter by join_code** - For proper isolation
- **Balance calculations scoped by join_code** - No aggregation across periods

## 🚨 Red Flags to Watch For

If you see any of these, the multi-tenancy fix is broken:

❌ Student sees combined balance from multiple periods with same teacher
❌ Transactions from different periods appear together
❌ Store items visible across periods when they shouldn't be
❌ Insurance policies showing from wrong period
❌ Any transaction with `join_code = NULL`
❌ Session shows wrong period after switching
❌ Balance changes when switching periods (should be recalculated per period)

## ✅ Success Indicators

✅ Each period shows isolated balance
✅ Switching periods changes visible transactions
✅ All transactions have join_code populated
✅ Store/insurance filtered by period
✅ Same student can have different balances in different periods (same or different teacher)
✅ Manual SQL queries match UI calculations per join_code

---

**For detailed test credentials, see `TEST_CREDENTIALS.txt` after running the script.**
