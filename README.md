# Classroom Economy System

An interactive banking and classroom management platform for teaching students about money while tracking classroom participation.

## Table of Contents
- [Classroom Economy System](#classroom-economy-system)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
    - [Current](#current)
    - [Planned / Partial](#planned--partial)
  - [Getting Started](#getting-started)
  - [Configuration](#configuration)
  - [Deployment](#deployment)
    - [Azure](#azure)
    - [DigitalOcean](#digitalocean)
  - [Monitoring](#monitoring)
  - [Roadmap](#roadmap)
  - [Maintaining Dependencies](#maintaining-dependencies)
  - [License](#license)

## Features
### Current
- Student login with username and PIN
- New user setup with PIN and passphrase creation
- Two‑factor transfers between checking and savings
- Attendance tracking for Periods A and B with timed tap in/out
- Insurance market with multiple plans and cooldown logic
- Admin portal for roster management, CSV upload, attendance logs and payroll

### Planned / Partial
- Rent and property tax tracking fields
- Classroom store purchases
- Optional TOTP or passkey second factor
- Student "Shop" link and admin items for hall passes and audits

## Getting Started
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run
```

Seed data can be generated with `python seed_students.py`.
Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` to seed an admin user automatically, or run `flask ensure-admin`.
After deployment run `flask db upgrade` to apply migrations.

## Configuration
The application recognises these optional variables:
- `LOG_LEVEL` – logging level (default `INFO`)
- `LOG_FORMAT` – log message format
- `LOG_FILE` – file used for rotating logs when `FLASK_ENV=production`

## Deployment
The `Procfile` starts the server with:
```bash
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```
`startup.txt` contains the same command for platforms that read from it.

### Azure
Add a database migration before starting:
```bash
web: bash -c 'flask db upgrade && gunicorn --bind=0.0.0.0 --timeout 600 app:app'
```

### DigitalOcean
Run migrations then launch Gunicorn:
```bash
FLASK_APP=app flask db upgrade
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

## Monitoring
Deploy behind a production web server such as NGINX. Call `/health` for a 200 response when the database is reachable.

## Roadmap

- Mobile‑friendly redesign
- Classroom store & inventory system
- Rent and property tax payment workflows
- Optional TOTP or passkey authentication
- Stock market mini‑game using school data

## Maintaining Dependencies
Review upgrades monthly:
1. Activate your virtual environment.
2. Run `./scripts/update_packages.sh` to upgrade and run the tests.
3. Commit the updated `requirements.txt` if tests pass.

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).

>[!IMPORTANT]
> **This license allows you to:**
>
> - Use this project in classrooms, clubs, and nonprofit educational settings
> - Modify or adapt it for school use, assignments, or personal learning
> - Share it with students or other educators
> - Use it for research or academic presentations (as long as they are not sold)
>
> **This license prohibits you from:**
>
> - Use it as part of a commercial product or SaaS platform
> - Host a paid service or subscription that includes this software
> - Incorporate it into any offering that generates revenue (e.g., paid courses, tutoring platforms)
> - Use it internally within a for-profit business, even if not publicly distributed
