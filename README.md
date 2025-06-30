# Classroom Economy System

An interactive banking and classroom management platform for students. The application simulates real-world finances while letting teachers track attendance and run payroll based on student participation.

(Here are some edits I am adding to practice the GitHub flow)

## Features

### Implemented & manually tested

- Student login with username and PIN
- New user setup to create PIN and passphrase
- Two-factor transfer between checking and savings accounts
- Attendance tracking for Period A and B with tap in/out and automatic timers
- Insurance market with multiple plans and cooldown logic
- Admin portal with roster management, CSV upload, attendance logs, and payroll processing

### Implemented but not covered by automated tests

- All features above currently rely on manual testing only

### Backend implemented but no frontend

- Rent and property tax tracking fields
- Purchase model for future classroom store
- Support for TOTP/passkey second factor

### Frontend only / not connected

- Student "Shop" link and admin menu items for Hall Pass, Transactions, Store, and Audit
- TOTP setup page template

## Tech Stack

- **Backend:** Flask, SQLAlchemy (PostgreSQL or SQLite)
- **Frontend:** Bootstrap & Jinja2 templates
- **Deployment:** Gunicorn + NGINX on Ubuntu (sample configuration)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run
```

Seed data can be generated with `python seed_students.py`.
If `ADMIN_USERNAME` and `ADMIN_PASSWORD` are provided the application will
automatically create that admin account on first request. You can also run
`flask ensure-admin` manually to seed it ahead of time.

After deploying to a new environment, run `flask db upgrade` to apply the
latest migrations, including the admin table.

## Deployment

The included `Procfile` launches the app with:

```bash
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

`startup.txt` mirrors this command for platforms that read from it. Use this
entrypoint when deploying to ensure the Flask application starts correctly.

## Deployment & Monitoring

Deploy behind a production web server such as Gunicorn and NGINX.
For uptime checks, call the `/health` endpoint which returns HTTP 200 if the
database is reachable.

### Environment variables

The application respects several optional variables:

- `LOG_LEVEL` – logging level (defaults to `INFO`).
- `LOG_FORMAT` – format for log messages.
- `LOG_FILE` – file used for rotating logs when `FLASK_ENV=production`.

## Roadmap

- Mobile‑friendly redesign
- Classroom store & inventory system
- Rent and property tax payment workflows
- Optional TOTP or passkey authentication
- Stock market mini-game using school data

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

## Deployment on Azure

Add `flask db upgrade` before launching Gunicorn so the database schema is up to date:

```powershell
web: bash -c 'flask db upgrade && gunicorn --bind=0.0.0.0 --timeout 600 app:app'
```

Configure your Azure App Service startup command or Procfile with this line.

## Deployment on DigitalOcean

When deploying on DigitalOcean, run migrations before starting Gunicorn:

```bash
FLASK_APP=app flask db upgrade
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

## Maintaining Dependencies

To keep dependencies current, review upgrades once a month:

1. Activate your virtual environment.
2. Run `./scripts/update_packages.sh`.
   This script upgrades outdated packages, updates `requirements.txt`, and runs the tests.
3. Commit the updated `requirements.txt` if everything passes.
