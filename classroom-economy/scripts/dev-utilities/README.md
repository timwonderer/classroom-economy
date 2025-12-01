# Development Utilities

## ⚠️ WARNING: DANGEROUS SCRIPTS ⚠️

These scripts are **DEVELOPMENT ONLY** and can cause **PERMANENT DATA LOSS** if used incorrectly.

### Scripts in this directory:

- **reset_database.py** - Completely wipes and recreates the entire database
- **reset_database_no_schema.py** - Alternative database reset method
- **diagnose_migrations.py** - Diagnostic tool for migration issues

### Important Safety Guidelines:

1. **NEVER** run these scripts in production
2. **ALWAYS** backup your database before running any reset script
3. These scripts will **DELETE ALL DATA** without confirmation
4. Only use in local development environments
5. Ensure you have the correct DATABASE_URL set before running

### Usage:

```bash
# From project root
python scripts/dev-utilities/reset_database.py
```

### Production Safety:

If you accidentally run these in production:
1. Restore from your most recent backup immediately
2. Check your environment variables
3. Consider adding additional safeguards to prevent this
