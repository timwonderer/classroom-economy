# TOTP Encryption Migration Guide

## Overview

This migration adds encryption-at-rest for TOTP secrets in the `admins` and `system_admins` tables.

**Status:** ⚠️ DATABASE MIGRATION REQUIRED

## Changes Made

1. Added `encrypt_totp()` and `decrypt_totp()` helper functions in `app/utils/encryption.py`
2. Updated all TOTP secret creation points to encrypt before storing
3. Updated all TOTP secret verification points to decrypt before use
4. Changed column length from VARCHAR(32) to VARCHAR(200) to accommodate encrypted data

## Database Migration Required

The TOTP secret columns need to be expanded to accommodate base64-encoded encrypted data:

```sql
-- Run these SQL commands OR use Flask-Migrate

ALTER TABLE admins ALTER COLUMN totp_secret TYPE VARCHAR(200);
ALTER TABLE system_admins ALTER COLUMN totp_secret TYPE VARCHAR(200);
```

### Using Flask-Migrate (Recommended)

```bash
# Generate migration
flask db migrate -m "Expand totp_secret column for encryption"

# Review the generated migration file in migrations/versions/

# Apply migration
flask db upgrade
```

## Backward Compatibility

The `decrypt_totp()` function handles both:
- **Legacy plaintext** TOTP secrets (32 chars, base32 alphabet)
- **New encrypted** TOTP secrets (base64-encoded)

This means:
✅ Existing admins can continue to log in with old plaintext secrets
✅ New admins will have encrypted secrets
✅ Password resets will migrate admins to encrypted secrets
✅ No data migration script needed - migration happens on-the-fly

## Testing Checklist

- [ ] Run database migration
- [ ] Test admin login with existing account (legacy plaintext)
- [ ] Test creating new admin account (encrypted)
- [ ] Test admin password reset (migrates to encrypted)
- [ ] Test system admin login
- [ ] Test system admin TOTP reset for teacher

## Security Notes

- Encryption uses the same `ENCRYPTION_KEY` as student PII encryption
- Uses Fernet (AES-128-CBC + HMAC-SHA256)
- Secrets are encrypted before database storage
- Decrypted only transiently in memory during TOTP verification
- **Still vulnerable if `ENCRYPTION_KEY` is compromised** - see `docs/security/ACCESS_AND_SECRETS_REPORT.md`

## Next Steps (Long-Term)

1. Migrate `ENCRYPTION_KEY` out of `.env` file
2. Consider AWS Secrets Manager or HashiCorp Vault
3. Implement key rotation procedures
4. Add monitoring for failed decryption attempts

## Rollback

If issues arise:

1. Revert code changes
2. Rollback database migration: `flask db downgrade`
3. Old plaintext TOTP secrets will work again

**⚠️ WARNING:** After this migration, you cannot rollback without data loss for newly created admins!
