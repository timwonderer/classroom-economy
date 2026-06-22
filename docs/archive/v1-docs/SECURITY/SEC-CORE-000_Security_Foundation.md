# Security Architecture Foundation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SEC-CORE-000| 1.1 | 2026-03-08 | 1.0 |Constitutional|

## I. Purpose
To establish the foundational rules and methodologies for security audits, threat models, incident responses, and vulnerability disclosures across the Classroom Token Hub.

## II. Scope
All endpoints, storage mediums, network routes, and third-party integrations utilized within the application schema.

## III. Authority Level
Authoritative (ARC tier equivalent). Must remain subordinate to the identity and data-isolation invariants defined in INV-CORE-000.

## IV. Security Precepts

### 1. Route-Level Role Authentication
Zero-trust handling is enforced via strict decorator gating (`@admin_required`, `@sysadmin_required`, `@student_required`) mapped to discrete sessions. No route may infer permission context from parameters alone.

### 2. PII Obfuscation
Personally Identifiable Information is restricted. Critical identifiers (Student First Name, Email) MUST be symmetrically encrypted at rest using the application's implementation of `Fernet` (AES-128 via `ENCRYPTION_KEY`). Passwords must be hashed using bcrypt combined with constant-time verification, incorporating both salt and a `.env` configured pepper.

### 3. Resource Exhaustion and Bot Defense
Public-facing forms (login, claim verification) must implement Cloudflare Turnstile token validation. Repeated hit endpoints must be protected using `Flask-Limiter` with an active Redis instance.

### 4. Code Immutability
Security mandates parameterized queries (SQLAlchemy ORM) universally. Dynamic SQL string interpolation is unconditionally prohibited to eliminate SQL injection vulnerabilities. All state-mutating requests enforce CSRF.

## V. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
