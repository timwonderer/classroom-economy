
import unittest
import pyotp

from app import create_app, db
from app.models import User, UserRole, Admin, AdminInviteCode
from app.hash_utils import hash_username_lookup


class TestAdminTos(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for easier testing
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_admin_signup_with_tos(self):
        # Create an invite code
        invite_code = "TESTCODE123"
        db.session.add(AdminInviteCode(code=invite_code))
        db.session.commit()

        # Try signup without ToS agreement (simulate checkbox not checked, hidden field false)
        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'tos_agreed': 'false'
        }, follow_redirects=True)

        # Should fail (flash message error)
        self.assertIn(b'You must agree to the Terms of Service', response.data)

        # Verify admin was not created
        admin = Admin.query.filter_by(username_lookup_hash=hash_username_lookup('newadmin')).first()
        self.assertIsNone(admin)

        # Try signup WITH ToS agreement
        # Note: First step usually redirects to TOTP page if successful
        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'tos_agreed': 'true'
        })

        # Check if we got the TOTP page (QR code present)
        self.assertIn(b'Scan the QR code', response.data)

        # Verify the hidden tos_agreed field is present in the TOTP form
        self.assertIn(b'name="tos_agreed" value="true"', response.data)

        # Now simulate the TOTP confirmation step
        # Retrieve the secret from the session
        with self.client.session_transaction() as sess:
            totp_secret = sess.get('admin_totp_secret')

        totp = pyotp.TOTP(totp_secret)
        code = totp.now()

        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'totp_code': code,
            'tos_agreed': 'true'  # Include it again as hidden field persists or session logic
        }, follow_redirects=True)

        self.assertIn(b'Admin account created successfully', response.data)

        # Verify admin was created with ToS accepted
        admin = Admin.query.filter_by(username_lookup_hash=hash_username_lookup('newadmin')).first()
        self.assertIsNotNone(admin)
        self.assertTrue(admin.tos_accepted)
        self.assertIsNotNone(admin.tos_accepted_at)
        invite = AdminInviteCode.query.filter_by(code=invite_code).first()
        self.assertIsNotNone(invite)
        self.assertTrue(invite.used)

    def test_invite_code_with_db_whitespace_is_marked_used(self):
        # Stored code has surrounding whitespace (legacy data shape)
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
        self.assertTrue(invite.used)

    def test_totp_submission_without_tos_agreement(self):
        # Create an invite code
        invite_code = "TESTCODE123"
        db.session.add(AdminInviteCode(code=invite_code))
        db.session.commit()

        # Simulate signup with ToS agreement
        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'tos_agreed': 'true'
        })

        # Retrieve the secret from the session
        with self.client.session_transaction() as sess:
            totp_secret = sess.get('admin_totp_secret')

        totp = pyotp.TOTP(totp_secret)
        code = totp.now()

        # Now simulate TOTP confirmation without ToS agreement
        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'totp_code': code,
            'tos_agreed': 'false'  # Bypassing frontend by submitting false
        }, follow_redirects=True)

        # Should fail (flash message error)
        self.assertIn(b'You must agree to the Terms of Service', response.data)

        # Verify admin was not created
        admin = Admin.query.filter_by(username_lookup_hash=hash_username_lookup('newadmin')).first()
        self.assertIsNone(admin)

    def test_totp_submission_without_tos_parameter(self):
        # Create an invite code
        invite_code = "TESTCODE123"
        db.session.add(AdminInviteCode(code=invite_code))
        db.session.commit()

        # Simulate signup with ToS agreement
        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'tos_agreed': 'true'
        })

        # Retrieve the secret from the session
        with self.client.session_transaction() as sess:
            totp_secret = sess.get('admin_totp_secret')

        totp = pyotp.TOTP(totp_secret)
        code = totp.now()

        # Now simulate TOTP confirmation without tos_agreed parameter
        response = self.client.post('/admin/signup', data={
            'username': 'newadmin',
            'invite_code': invite_code,
            'dob_sum': '1990-01-01',
            'totp_code': code
            # tos_agreed is missing
        }, follow_redirects=True)

        # Should fail (flash message error)
        self.assertIn(b'You must agree to the Terms of Service', response.data)

        # Verify admin was not created
        admin = Admin.query.filter_by(username_lookup_hash=hash_username_lookup('newadmin')).first()
        self.assertIsNone(admin)

    def test_schema_columns_exist(self):
        # Verify columns exist on the model
        self.assertTrue(hasattr(Admin, 'tos_accepted'))
        self.assertTrue(hasattr(Admin, 'tos_accepted_at'))

if __name__ == '__main__':
    unittest.main()
