import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Student
from hash_utils import hash_username_lookup

def validate_hash(username):
    lookup_hash = hash_username_lookup(username)
    student = Student.query.filter_by(username_lookup_hash=lookup_hash).first()
    
    if student:
        print(f"Found student: {student.username}")
        return True
    else:
        print(f"No student found with hash for '{username}'")
        return False

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        # Run your validation
        validate_hash("alicea2008")

