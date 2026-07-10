import unittest
import pyotp

from app import create_app, db
from app.models import User, UserRole, AdminInviteCode
from app.hash_utils import hash_username_lookup
from sqlalchemy import text


class TestAdminTos(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.session.remove()
        db.engine.dispose()
        with db.engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            conn.execute(text("SET search_path TO public"))
            conn.commit()
            db.Model.metadata.create_all(bind=conn)
            conn.commit()
        db.engine.dispose()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.app_context.pop()

    def test_admin_signup_with_tos(self):
        invite_code = "TESTCODE123"
        db.session.add(AdminInviteCode(code=invite_code))
        db.session.commit()

        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'tos_agreed': 'false'
        }, follow_redirects=True)

        self.assertIn(b'You must agree to the Terms of Service', response.data)

        user = User.query.filter_by(username_lookup_hash=hash_username_lookup('newadmin')).first()
        self.assertIsNone(user)

        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'tos_agreed': 'true'
        })

        self.assertIn(b'Scan the QR code', response.data)
        self.assertIn(b'name="tos_agreed" value="true"', response.data)

        with self.client.session_transaction() as sess:
            totp_secret = sess.get('admin_totp_secret')

        totp = pyotp.TOTP(totp_secret)
        code = totp.now()

        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'totp_code': code,
            'tos_agreed': 'true'
        }, follow_redirects=True)

        self.assertIn(b'Admin account created successfully', response.data)

        user = User.query.filter_by(username_lookup_hash=hash_username_lookup('newadmin')).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.user_role, UserRole.TEACHER)
        invite = AdminInviteCode.query.filter_by(code=invite_code).first()
        self.assertIsNotNone(invite)
        self.assertFalse(invite.used)

    def test_invite_code_with_db_whitespace_is_preserved(self):
        stored_code = "  PADDED123  "
        submitted_code = "PADDED123"
        db.session.add(AdminInviteCode(code=stored_code))
        db.session.commit()

        response = self.client.post('/admin/signup', data={
            'username': 'whitespaceadmin',
            'invite_code': submitted_code,
            'dob_sum': '1991-02-03',
            'tos_agreed': 'true'
        })

        self.assertIn(b'Scan the QR code', response.data)

        with self.client.session_transaction() as sess:
            totp_secret = sess.get('admin_totp_secret')

        totp = pyotp.TOTP(totp_secret)
        code = totp.now()

        response = self.client.post('/admin/signup', data={
            'username': 'whitespaceadmin',
            'invite_code': submitted_code,
            'dob_sum': '1991-02-03',
            'totp_code': code,
            'tos_agreed': 'true'
        }, follow_redirects=True)

        self.assertIn(b'Admin account created successfully', response.data)
        invite = AdminInviteCode.query.filter_by(code=stored_code).first()
        self.assertIsNotNone(invite)
        self.assertFalse(invite.used)

    def test_totp_submission_without_tos_agreement(self):
        invite_code = "TESTCODE123"
        db.session.add(AdminInviteCode(code=invite_code))
        db.session.commit()

        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'tos_agreed': 'true'
        })

        with self.client.session_transaction() as sess:
            totp_secret = sess.get('admin_totp_secret')

        totp = pyotp.TOTP(totp_secret)
        code = totp.now()

        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'totp_code': code,
            'tos_agreed': 'false'
        }, follow_redirects=True)

        self.assertIn(b'You must agree to the Terms of Service', response.data)

        user = User.query.filter_by(username_lookup_hash=hash_username_lookup('newadmin')).first()
        self.assertIsNone(user)

    def test_totp_submission_without_tos_parameter(self):
        invite_code = "TESTCODE123"
        db.session.add(AdminInviteCode(code=invite_code))
        db.session.commit()

        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'tos_agreed': 'true'
        })

        with self.client.session_transaction() as sess:
            totp_secret = sess.get('admin_totp_secret')

        totp = pyotp.TOTP(totp_secret)
        code = totp.now()

        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'totp_code': code
        }, follow_redirects=True)

        self.assertIn(b'You must agree to the Terms of Service', response.data)

        user = User.query.filter_by(username_lookup_hash=hash_username_lookup('newadmin')).first()
        self.assertIsNone(user)

    def test_schema_columns_exist(self):
        # User has tos_accepted attributes in V2
        self.assertTrue(hasattr(User, 'tos_accepted'))
        self.assertTrue(hasattr(User, 'tos_accepted_at'))

if __name__ == '__main__':
    unittest.main()
