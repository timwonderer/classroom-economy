import os
from pathlib import Path
from dotenv import dotenv_values
from app import create_app, db
from app.models import Admin
import pytest

pytestmark = pytest.mark.skip(reason="TeacherBlock removed in Wave 11 decommissioning")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"
TEST_DATABASE_URL = dotenv_values(DOTENV_PATH).get("TEST_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL must be set in .env for verification tests.")

# Set required environment variables for testing
os.environ['FLASK_ENV'] = 'testing'
os.environ.setdefault('SECRET_KEY', 'test_secret')
os.environ['DATABASE_URL'] = TEST_DATABASE_URL
os.environ.setdefault('TURNSTILE_SITE_KEY', 'test')
os.environ.setdefault('TURNSTILE_SECRET_KEY', 'test')
os.environ.setdefault('ENCRYPTION_KEY', 'jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=')
os.environ.setdefault('PEPPER_KEY', 'tKiXIAgaPqsOOhR1PqvdEQo4BelrN5SP3cpWxVYrsHk=')

def test_onboarding_status_no_class_period_fix():
    """
    Verify that onboarding_status no longer returns no_class_period: True
    even when the teacher has no classes.
    """
    app = create_app()
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create a new admin (teacher)
        from tests.helpers.v2_fixtures import make_admin
        admin = make_admin('new_teacher', 'secret')
        
        db.session.add(admin)
        db.session.commit()
        
        # Ensure no TeacherBlocks exist for this admin
        assert TeacherBlock.query.filter_by(teacher_id=admin.id).count() == 0
        
        # Log in (simulate session)
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['admin_id'] = admin.id
                sess['is_admin'] = True
                sess['_fresh'] = True
            
            # Call onboarding status
            response = client.get('/admin/onboarding/status')
            assert response.status_code == 200
            data = response.get_json()
            
            print(f"Response data: {data}")
            
            # VERIFICATION: 
            # 1. no_class_period should NOT be True (it should be absent or False)
            assert not data.get('no_class_period'), "no_class_period should be False or missing"
            
            # 2. dismissal status
            assert data.get('dismissed') is False
            
            # 3. Completion data should exist
            assert 'completion' in data
            
            # 4. 'roster' should be False (since no students)
            assert data['completion']['roster'] is False

if __name__ == "__main__":
    try:
        test_onboarding_status_no_class_period_fix()
        print("✅ Verification Passed: onboarding_status returning correct structure for new teacher.")
    except Exception as e:
        print(f"❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
