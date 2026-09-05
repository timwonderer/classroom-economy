---
title: Transactions and Banking Troubleshooting
description: Why a transaction, adjustment, or interest posting looks wrong in the ledger.
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/attendance-payroll
  - user-guides/diagnostics/teacher/store
---

# Transactions and Banking Troubleshooting

Diagnostic guide for resolving errors with ledgers, student balances, and banking transfers.

## Balances look wrong

### Symptoms
- A student reports having less or more money than expected.
- The class total net worth looks incorrect.

### Causes & Solutions
**Cause 1: Wrong class context**
- **Check:** Confirm which class the student is actively viewing on their dashboard.
- **Fix:** Balances are strictly isolated per join code. A student might be looking at their Period 1 balance instead of Period 2.

**Cause 2: Voided transactions**
- **Check:** Check the student's transaction ledger for voided entries.
- **Fix:** Voided transactions are removed from the totals but remain visible in the ledger for transparency.

**Cause 3: Out of sync legacy data**
- **Check:** Are these transactions from before version 1.6?
- **Fix:** Use the "Backfill Join Codes" tool in Admin System Settings to repair legacy transactions that lack proper join_code scoping.

## Students cannot transfer funds

### Symptoms
- Students cannot move money between Checking and Savings.
- The transfer button is greyed out or errors upon submission.

### Causes & Solutions
**Cause 1: Banking disabled**
- **Check:** View the Feature Settings for that class period.
- **Fix:** Enable Banking for the period.

**Cause 2: Insufficient funds or wrong passphrase**
- **Check:** Ask the student if they see a specific error.
- **Fix:** Students must enter their exact passphrase and have enough funds in the source account to transfer. 

## When to Contact Support
Report this issue if:
- A voided transaction still actively affects the mathematical balance totals.
- Interest algorithms miscalculate payouts or post infinite loops.
