# 🎓 Classroom Token Hub

An interactive banking and classroom management platform for teaching students about money while tracking classroom participation.

⚠️ **Note:** This repository is currently private and under active development for controlled classroom testing.

## Table of Contents

- [🎓 Classroom Token Hub](#-classroom-token-hub)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
    - [Current](#current)
    - [Planned / Partial](#planned--partial)
  - [Getting Started](#getting-started)
  - [Configuration](#configuration)
  - [Deployment](#deployment)
  - [Monitoring](#monitoring)
  - [Roadmap](#roadmap)
  - [Maintaining Dependencies](#maintaining-dependencies)
  - [License](#license)

## Features

### Current

* Teacher CSV roster upload and automatic block creation
* Student account creation with block assignment
* Admin portal for roster management, CSV upload, attendance logs, and payroll
* Attendance tracking for Periods A and B with timed tap in/out
* Reward and fee issuance with transaction logs
* GitHub Actions auto-deploy pipeline for DigitalOcean

### Planned / Partial

* Invite-based admin setup flow
* Student first-time claim and login flow (PIN and passphrase)
* Rent and property tax tracking fields
* Classroom store purchases and reward management
* Optional TOTP or passkey second factor
* Student "Shop" interface and admin-managed store items

## Getting Started

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run
```

Seed data can be generated with `python seed_students.py`. After deployment, run `flask db upgrade` to apply migrations.

## Configuration

The application recognizes these optional variables:

* `LOG_LEVEL` – logging level (default `INFO`)
* `LOG_FORMAT` – log message format
* `LOG_FILE` – file used for rotating logs when `FLASK_ENV=production`

## Deployment

Deploy using Gunicorn:

```bash
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

For DigitalOcean deployments, run migrations, then launch Gunicorn:

```bash
FLASK_APP=app flask db upgrade
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

## Monitoring

Deploy behind a production web server such as NGINX. Call `/health` for a 200 response when the database is reachable.

## Roadmap

* Invite-based admin setup flow
* Student first-time claim/login system
* CSV export of student data and logs
* Classroom store & inventory system
* Rent and property tax payment workflows
* Optional TOTP or passkey authentication
* Mobile-friendly redesign
* Stock market mini-game using school data

## Maintaining Dependencies

Review upgrades monthly:

1. Activate your virtual environment.
2. Run `./scripts/update_packages.sh` to upgrade and run the tests.
3. Commit the updated `requirements.txt` if tests pass.

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).

> \[!IMPORTANT]
> **This license allows you to:**
>
> * Use this project in classrooms, clubs, and nonprofit educational settings
> * Modify or adapt it for school use, assignments, or personal learning
> * Share it with students or other educators
> * Use it for research or academic presentations (as long as they are not sold)
>
> **This license prohibits you from:**
>
> * Using it as part of a commercial product or SaaS platform
> * Hosting a paid service or subscription that includes this software
> * Incorporating it into any offering that generates revenue (e.g., paid courses, tutoring platforms)
> * Using it internally within a for-profit business, even if not publicly distributed
