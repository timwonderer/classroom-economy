---
title: Third-Party Notices
roles: [teacher, student]
description: Attributions and licenses for third-party software and services
category: legal
keywords: [third-party, attributions, dependencies, licenses, open source]
searchable: true
related:
  - user-guides/legal/license
  - user-guides/legal/attribution
---

# Third-Party Notices

This project relies on third-party open-source software and services. The following attributions are provided in accordance with their respective licenses.

---

## Major Third-Party Services and Assets

### Bitwarden Passwordless.dev

Used for passwordless authentication functionality.

**License:** MIT License

**Project:** [https://github.com/bitwarden/passwordless-server](https://github.com/bitwarden/passwordless-server)

---

### Google Material Symbols

Used for UI icons and symbols.

**License:** Apache License 2.0

**Project:** [https://fonts.google.com/icons](https://fonts.google.com/icons)

**License Details:** Full text available at [LICENSES/Apache-2.0.txt](https://github.com/timwonderer/classroom-economy/blob/main/LICENSES/Apache-2.0.txt)

---

### Bootstrap Icons

Used for UI iconography.

**License:** MIT License

**Project:** [https://icons.getbootstrap.com/](https://icons.getbootstrap.com/)

**License Details:** Full text available at [LICENSES/MIT.txt](https://github.com/timwonderer/classroom-economy/blob/main/LICENSES/MIT.txt)

---

## Python Dependencies

This project uses additional open-source Python packages installed via pip and listed in `requirements.txt`.

These dependencies are not redistributed directly and retain their original licenses.

### Key Python Dependencies

The following are some of the major Python dependencies used by this project:

- **Flask** - Web framework (BSD-3-Clause)
- **SQLAlchemy** - ORM and database toolkit (MIT)
- **Alembic** - Database migrations (MIT)
- **psycopg2** - PostgreSQL adapter (LGPL with exceptions)
- **Flask-WTF** - CSRF protection and forms (BSD)
- **pyotp** - TOTP authentication (BSD)
- **cryptography** - PII encryption (Apache 2.0 / BSD)
- **Gunicorn** - WSGI server (MIT)

For a complete list of dependencies and their versions, see [requirements.txt](https://github.com/timwonderer/classroom-economy/blob/main/requirements.txt).

---

## License Compliance

All third-party dependencies used in this project are either:

1. **Not redistributed** - Installed by users via pip/package managers
2. **Properly attributed** - Where required by their licenses
3. **Compatible** - With the PolyForm Noncommercial License 1.0.0

---

## Full License Texts

Full text of common open-source licenses referenced above:

- **Apache License 2.0:** [LICENSES/Apache-2.0.txt](https://github.com/timwonderer/classroom-economy/blob/main/LICENSES/Apache-2.0.txt)
- **MIT License:** [LICENSES/MIT.txt](https://github.com/timwonderer/classroom-economy/blob/main/LICENSES/MIT.txt)

---

**Last Updated:** 2026-01-05
