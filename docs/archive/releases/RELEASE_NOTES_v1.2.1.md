# Release Notes - Version 1.2.1

**Release Date**: December 21, 2025  
**Focus**: Multi-tenancy hardening, legacy migration completion, operational clarity

---

## 🎯 Highlights

- Finalized the comprehensive legacy account migration toolkit and documentation
- Added safety checks for the `student_blocks` join code migration to handle partially applied schemas
- Ensured all transaction creation paths propagate `join_code` for strict class isolation
- Introduced a schema inspection script to verify `join_code` coverage across all student-data tables
- Refreshed maintenance page messaging for clearer outage communication

---

## 🚀 New & Notable

### Legacy Migration Readiness
- **Comprehensive migration script** (`scripts/comprehensive_legacy_migration.py`) now paired with a detailed operations guide to move all legacy records to the join-code model.
- **Idempotent StudentBlock migration** (`a1b2c3d4e5f8_add_join_code_to_student_blocks.py`) adds `join_code` and index with existence checks to avoid duplicate-column failures on environments with hotfixes already applied.
- **Test coverage** (`tests/test_comprehensive_legacy_migration.py`) verifies all five migration phases, multi-period students, rollback safety, and CTE performance optimization.

### Multi-Tenancy Enforcement
- Added missing `join_code` propagation to overdraft fees, bonus/bulk payroll transactions, insurance reimbursements, manual payments, and bug-report rewards to close remaining isolation gaps.
- Optimized bonus join code lookup to avoid N+1 queries during mass payouts.

### Diagnostics & Operations
- **Join code schema audit tool** (`scripts/inspect_join_code_columns.py`) lists tables with/without `join_code`, highlights unknown tables, and recommends next steps.
- **Maintenance page refresh** improves copy and layout for clearer outage messaging and admin bypass guidance.

---

## 🧪 Testing

- Migration script and safeguards covered by the comprehensive migration test suite (`tests/test_comprehensive_legacy_migration.py`).

---

## 📌 Upgrade Notes

1. Apply migrations (`flask db upgrade`) to ensure `student_blocks.join_code` exists and is indexed.
2. Run `scripts/comprehensive_legacy_migration.py --dry-run` first, then run without `--dry-run` to backfill legacy data.
3. Use `scripts/inspect_join_code_columns.py` to verify all student-data tables include `join_code`.
4. Confirm operational docs are up to date: `docs/operations/LEGACY_ACCOUNT_MIGRATION.md`.

