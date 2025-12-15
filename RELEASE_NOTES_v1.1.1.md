# Release Notes - Version 1.1.1

**Release Date**: December 15, 2025

Version 1.1.1 is a stability-focused patch that addresses regressions discovered after the 1.1.0 launch. This release tightens authentication recovery, fixes redirect and time-zone edge cases in the student dashboard, and restores consistent styling across admin entry points.

---

## 🐛 Bug Fixes

### Authentication & Recovery
- Secured teacher recovery by hashing stored date-of-birth sums with salted HMAC, migrating existing records, and validating both legacy and new hashes during recovery checks (#637).
- Hardened student login redirects by rejecting missing/unsafe `next` parameters and normalizing weekly/monthly earnings calculations to UTC timestamps to avoid negative spending totals (#638).

### UI & Theming
- Applied the new green brand theme to standalone admin/auth templates so signup, reset, and system-admin pages no longer fall back to the deprecated orange palette (#635).
- Restored admin dashboard/help headings to the correct hierarchy and spacing based on design feedback (#639).

### Static Assets & Templates
- Added cache-busting `static_url` helper defaults and test coverage to prevent stale assets and undefined `static_url` errors across templates, including student login and admin layouts (#628-633).

---

## 📦 Upgrade Notes

No manual steps are required beyond the standard deployment process. Deployments will run the included migration to populate the new recovery hash fields automatically.

---

## 🧪 Validation

- Existing automated tests continue to cover the static asset helper changes and recovery flows introduced in this patch.

---

## 📝 Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete list of changes.
