# Demo Session Lifecycle and Cleanup

## Overview
Demo sessions let admins temporarily experience the student portal without impacting real data. They are intentionally short-lived and isolated:

- Sessions are hard-limited to **10 minutes** (`SESSION_TIMEOUT_MINUTES`), even when an admin is viewing as the demo student.
- Demo login links now require the **same admin** to be authenticated before use.
- Cleanup removes the demo student plus all related rent, insurance, hall pass, and commerce artifacts.

## Automatic Cleanup
- **Admin demo logout**: `student.logout` calls `cleanup_demo_student_data` to retire the session and delete the student artifacts in FK-safe order.
- **Background job**: `cleanup_expired_demo_sessions_job` (runs every 5 minutes) scans for expired demo sessions and invokes the same helper so the student record and related data are removed consistently.
- **Route guard**: `login_required` clears an invalid or expired demo session when an admin is viewing as a student.

## Manual Cleanup (when automation fails)
If a demo session gets stuck (e.g., scheduler paused), remove it manually:

1. SSH into the app host and activate the virtual environment if needed.
2. Run the cleanup in an app context (replace `<SESSION_ID>`):

```bash
python - <<'PY'
from app import app
from app.extensions import db
from app.models import DemoStudent
from app.utils.demo_sessions import cleanup_demo_student_data

with app.app_context():
    session_id = "<SESSION_ID>"
    demo_session = DemoStudent.query.filter_by(session_id=session_id).first()
    if not demo_session:
        print("No demo session found")
    else:
        cleanup_demo_student_data(demo_session)
        db.session.commit()
        print(f"Cleaned demo session {session_id}")
PY
```

3. Verify the `DemoStudent` row is gone and the student account no longer appears in the admin UI.

## Safety Notes
- The helper function already marks sessions inactive and timestamps `ended_at` before deleting dependents.
- The cleanup order prevents foreign key violations (claims → insurance → rent → hall passes → commerce → associations → demo session → student).
- Always commit the transaction; roll back if any exception is raised.
