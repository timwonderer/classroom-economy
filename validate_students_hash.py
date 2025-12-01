from app.models import Student
from hash_utils import hash_username_lookup

# Find Emma
username = "emmae2009"
lookup_hash = hash_username_lookup(username)
student = Student.query.filter_by(username_lookup_hash=lookup_hash).first()

if student:
    print(f"✓ Found student: {student.full_name}")
    print(f"  Has username_hash: {student.username_hash is not None}")
    print(f"  Has first_half_hash: {student.first_half_hash is not None}")
else:
    print("✗ Student not found with that username hash")
    
