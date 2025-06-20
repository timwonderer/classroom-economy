# Classroom Economy System

An interactive banking and classroom management platform for students. The application simulates real-world finances while letting teachers track attendance and run payroll based on student participation.

## Features

### Implemented & manually tested
- Student login with QR ID and PIN
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

## Deployment & Monitoring
Deploy behind a production web server such as Gunicorn and NGINX.
For uptime checks, call the `/health` endpoint which returns HTTP 200 if the
database is reachable.

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
> - Use this project in classrooms, clubs, and nonprofit educational settings
> - Modify or adapt it for school use, assignments, or personal learning
> - Share it with students or other educators
> - Use it for research or academic presentations (as long as they are not sold)
> 
> **This license prohibits you from:**
> - Use it as part of a commercial product or SaaS platform
> - Host a paid service or subscription that includes this software
> - Incorporate it into any offering that generates revenue (e.g., paid courses, tutoring platforms)
> - Use it internally within a for-profit business, even if not publicly distributed

