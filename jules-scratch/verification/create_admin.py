import os
import sys
# Add the current directory to the path to find the 'app' module
sys.path.append(os.getcwd())

from app import app, db, Admin, StoreItem
import pyotp

# This script needs the same environment variables as the main app
os.environ['SECRET_KEY'] = 'dummy-secret-key'
os.environ['DATABASE_URL'] = 'sqlite:///verification.db'
os.environ['FLASK_ENV'] = 'development'
os.environ['ENCRYPTION_KEY'] = os.environ.get('ENCRYPTION_KEY', 'a' * 44) # Re-use if set, else dummy
os.environ['PEPPER_KEY'] = 'dummy-pepper-key'


def create_admin_and_item():
    with app.app_context():
        # Create admin user
        # Ensure user does not already exist to prevent errors on re-run
        existing_admin = Admin.query.filter_by(username='testadmin').first()
        if existing_admin:
            print("Admin 'testadmin' already exists.")
        else:
            username = 'testadmin'
            totp_secret = 'JBSWY3DPEHPK3PXP' # Fixed secret for reproducible tests
            admin = Admin(username=username, totp_secret=totp_secret)
            db.session.add(admin)
            print(f"Admin '{username}' created with TOTP secret: {totp_secret}")

        # Create a sample store item
        existing_item = StoreItem.query.filter_by(name="Test Item").first()
        if existing_item:
            print("Test item already exists.")
        else:
            item = StoreItem(
                name="Test Item",
                description="A test item for verification",
                price=123.45,
                item_type='delayed',
                inventory=10
            )
            db.session.add(item)
            print("Added sample store item.")

        db.session.commit()
        print("Database seeded successfully.")

if __name__ == '__main__':
    create_admin_and_item()