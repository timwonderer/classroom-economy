# Public Demo Environment (Teacher + Student)

This guide describes how to stand up the read-only style demo endpoints that power the landing page iframes and buttons in `docs/index.html`. It uses the built-in demo student lifecycle (10-minute TTL, auto-cleanup) and a dedicated demo teacher with seeded data.

## What already exists in the codebase
- Demo student lifecycle: `app/routes/api.py:create_demo_student`, `app/routes/student.py:demo_login`, and `app/utils/demo_sessions.py:cleanup_demo_student_data`
- Timeouts: `SESSION_TIMEOUT_MINUTES` (10 minutes) enforced in `app/auth.py` (`login_required`)
- Automatic cleanup: scheduler job `cleanup_expired_demo_sessions_job` in `app/scheduled_tasks.py` and logout hook in `student.logout` (documented in `docs/operations/DEMO_SESSIONS.md`)
- Schema: `demo_students` table (see `docs/technical-reference/database_schema.md`)

## Prerequisites
- A separate deployment for the demo (do **not** point at production data). Follow `docs/DEPLOYMENT.md` for the base setup.
- Environment configured with production-like settings plus Turnstile keys (or leave unset to bypass during testing).
- APScheduler running so `cleanup_expired_demo_sessions_job` executes every 5 minutes (see `app/scheduled_tasks.py`).

## Steps: Stand up the demo deployment
1) **Deploy a fresh instance**  
   - Use a separate Postgres database. Run `flask db upgrade` to ensure the `demo_students` table exists.  
   - Create a system admin with `flask create-sysadmin` and log in to create a dedicated teacher (e.g., `demo_teacher`).

2) **Seed safe sample data**  
   - Option A: Upload a CSV using `student_upload_template.csv`.  
   - Option B: Run `python seed_dummy_students.py` for quick placeholder students (no real PII).  
   - Add a few store items and attendance/payroll settings via the admin UI to make the teacher dashboard feel real.

3) **Create a live demo student session (for the iframe)**  
   - Log in as the demo teacher in the demo deployment (session cookie required).  
   - Call the built-in endpoint (returns `redirect_url` like `/student/demo-login/<session_id>`):
     ```bash
     curl -X POST https://demo.classroomtokenhub.com/api/admin/create-demo-student \
       -H "Content-Type: application/json" \
       -b "session=<YOUR_ADMIN_SESSION_COOKIE>" \
       -d '{"period":1,"starting_balance":150,"pay_rate":10}'
     ```
   - Use the returned `redirect_url` for the **Student Demo** iframe/button. The session will auto-expire in 10 minutes and clean itself up (via `cleanup_demo_student_data`).

4) **Point the landing page to the demo URLs**  
   - Update `docs/index.html` demo links/iframes to the live demo host (e.g., `https://demo.classroomtokenhub.com/student/demo-login/<session_id>` for student, `https://demo.classroomtokenhub.com/admin` for teacher).  
   - The iframe sandbox is already set in `docs/index.html` (`sandbox="allow-same-origin allow-scripts allow-forms"`).

5) **Optional hardening so users cannot alter data**  
   - Run the demo against a database snapshot that refreshes nightly.  
   - Restrict the demo teacher to a dedicated tenant with dummy students only.  
   - Monitor demo cleanup in logs; if a session sticks, follow `docs/operations/DEMO_SESSIONS.md` to clean it manually.

## Verification checklist
- Student demo iframe loads and navigates; sessions expire after ~10 minutes and disappear from admin UI.  
- Teacher demo login works and surfaces only dummy data.  
- `cleanup_expired_demo_sessions_job` is running (check logs for “Cleaned up expired demo session”).  
- No PII from production is present in the demo database.
