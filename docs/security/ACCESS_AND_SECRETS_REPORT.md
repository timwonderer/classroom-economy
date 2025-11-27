# Access Control, Secrets, & Codebase Vulnerability & Mitigation Strategy

**Scope:** Server-level access, database security, and secrets management.

### 1. Plaintext Secrets in Database
*   **Vulnerability:** `totp_secret` (for Admins) is stored in plain text in the database.
*   **Risk:** If the database is compromised (SQL injection or backup leak), attackers can generate valid 2FA codes for every admin, leading to total account takeover.
*   **Mitigation Strategy:**
    *   **Encryption at Rest:** Encrypt the `totp_secret` column using a separate key (not stored in the DB). Decrypt it only transiently in memory when verifying a login attempt.

### 2. Environment Variable Exposure
*   **Vulnerability:** `ENCRYPTION_KEY` (for PII) and `SECRET_KEY` (for sessions) are stored in the `.env` file or process environment variables.
*   **Risk:** Any process with read access to `/proc` or the app directory (e.g., via Local File Inclusion or server compromise) can steal these keys, allowing them to decrypt all student names and forge sessions.
*   **Mitigation Strategy:**
    *   **File Permissions:** Ensure `.env` is readable *only* by the user running the application (`chmod 600`).
    *   **Secret Rotation:** Implement a procedure to rotate these keys periodically.

### 3. Weak User Hashing (Global Pepper)
*   **Vulnerability:** `username_lookup_hash` uses a global `PEPPER_KEY` without a per-user salt.
*   **Risk:** If the `PEPPER_KEY` is leaked (via server compromise), attackers can perform a dictionary attack to reverse all student usernames.
*   **Mitigation Strategy:**
    *   **Defense in Depth:** While determinism is needed for lookups, ensure `PEPPER_KEY` is high-entropy and strictly protected. Consider migrating to a slow hash (e.g., Argon2) if lookup speed permits.

### 4. Codebase Exposure (.git)
*   **Vulnerability:** The `.git` directory exists on the server (`ls -a` confirmed this).
*   **Risk:** If the web server is misconfigured to serve static files from the root, attackers can download the entire `.git` folder, reconstructing the source code and commit history (which may contain old secrets).
*   **Mitigation Strategy:**
    *   **Server Config:** Ensure the web server (Nginx/Gunicorn) explicitly denies access to `/.git` and `*.py` files.
