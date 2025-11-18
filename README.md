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

*   **Modern UI Design**: Clean, professional interface with Material Symbols iconography, gradient title banners, and collapsible navigation groups for improved user experience across admin and student portals.
*   **System Admin Portal**: Comprehensive super-user interface for managing teachers, generating admin invites, viewing system logs, monitoring errors, and testing error pages.
*   **Teacher Management**: System admins can view all teacher accounts with signup dates, last login timestamps, and student counts. Delete teachers with automatic cascade deletion of all their students and related data.
*   **Comprehensive Error Handling**: Custom error pages for all major HTTP errors (400, 401, 403, 404, 500, 503) with user-friendly troubleshooting guides and automatic database logging.
*   **Database Error Logging**: All errors are automatically logged to database with full context including timestamp, error type, request details, user agent, IP address, stack trace, and last 50 lines of application logs.
*   **Error Testing & Monitoring**: Built-in error testing interface allowing system admins to trigger test errors safely and view paginated, filterable error logs from the database.
*   **Invite-Based Admin Signup**: New administrators can only sign up using a secure, single-use invite code.
*   **TOTP-Only Admin Authentication**: All administrator accounts are secured with Time-Based One-Time Passwords (TOTP) for enhanced security.
*   **Admin Activity Tracking**: Track when each admin account was created and their last login timestamp.
*   **Student Roster Management**: Upload student rosters via CSV or add students manually.
*   **Student First-Time Setup**: Students complete a secure setup process to create a PIN and passphrase for account access.
*   **Attendance Tracking**: Students can tap in and out for designated class periods, with session durations logged automatically.
*   **Automated Payroll**: The system calculates and distributes payroll to students based on their attendance.
*   **Transaction Logging**: All financial activities, including bonuses, fees, and transfers, are logged.
*   **GitHub Actions CI/CD**: Automated deployment pipeline to DigitalOcean.

### Planned / Partial

*   Rent and property tax tracking fields
*   Classroom store purchases and reward management
*   Optional TOTP or passkey second factor for students
*   Student "Shop" interface and admin-managed store items

## Getting Started

1.  **Set up the environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Configure your environment variables:**
    Create a `.env` file and populate it with the required variables listed in the [Configuration](#configuration) section.

3.  **Apply database migrations:**
    ```bash
    flask db upgrade
    ```

4.  **Create the first System Admin:**
    Run the following command and follow the prompts to create your initial administrator account. You will be given a TOTP secret to add to your authenticator app.
    ```bash
    flask create-sysadmin
    ```

5.  **Run the application:**
    ```bash
    flask run
    ```

For testing purposes, you can:
- Use `student_upload_template.csv` as a reference for CSV roster uploads
- Run `python seed_dummy_students.py` to seed the database with sample students

## Configuration

The application requires the following environment variables to be set:

*   `SECRET_KEY`: A long, random string used to secure sessions and sign cookies.
*   `DATABASE_URL`: The full connection string for your PostgreSQL database (e.g., `postgresql://user:password@host:port/dbname`).
*   `FLASK_ENV`: The environment for Flask (e.g., `development` or `production`).
*   `ENCRYPTION_KEY`: A 32-byte key for encrypting personally identifiable information (PII). You can generate one with `openssl rand -base64 32`.
*   `PEPPER_KEY`: A secret key used to add an additional layer of security to student credentials.

The application also recognizes these optional variables for logging:

*   `LOG_LEVEL`: The logging level (default: `INFO`).
*   `LOG_FORMAT`: The log message format.
*   `LOG_FILE`: The file used for rotating logs when `FLASK_ENV=production`.

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

*   CSV export of student data and logs
*   Classroom store & inventory system
*   Rent and property tax payment workflows
*   Optional TOTP or passkey authentication for students
*   Mobile-friendly redesign
*   Stock market mini-game using school data

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
