-- Migration to add admin invite codes and admins table with MFA

-- Ensure uuid generation function is available
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE admin_invite_codes (
    code TEXT PRIMARY KEY,
    expires_at TIMESTAMP,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    used_at TIMESTAMP
);

CREATE TABLE admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    totp_secret TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

