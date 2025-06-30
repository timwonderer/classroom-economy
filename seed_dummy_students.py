# 📄 seed_dummy_students.py for Classroom Token Hub

from app import db, Student
from werkzeug.security import generate_password_hash
from hash_utils import hash_username, get_random_salt

# Replace with your pepper management if needed
PEPPER = b'static-pepper-for-dev'  # Replace with your actual pepper fetch if required

# Dummy pre-seeded students for advanced testing
students_to_seed = [
    {"first_name": "Alice", "last_name": "Johnson", "dob_sum": "2028", "block": "A", "challenge": "apple"},
    {"first_name": "Ben", "last_name": "Smith", "dob_sum": "2039", "block": "A", "challenge": "apple"},
    {"first_name": "Clara", "last_name": "Wu", "dob_sum": "2025", "block": "B", "challenge": "banana"},
    {"first_name": "David", "last_name": "Lee", "dob_sum": "2040", "block": "B", "challenge": "banana"},
    {"first_name": "Ella", "last_name": "Garcia", "dob_sum": "2033", "block": "C", "challenge": "cherry"},
    {"first_name": "Finn", "last_name": "Ramirez", "dob_sum": "2031", "block": "C", "challenge": "cherry"},
    {"first_name": "Grace", "last_name": "Chen", "dob_sum": "2022", "block": "D", "challenge": "date"},
    {"first_name": "Henry", "last_name": "Kumar", "dob_sum": "2028", "block": "D", "challenge": "date"},
]

def seed_dummy_students():
    for student in students_to_seed:
        salt = get_random_salt()
        initials = student["first_name"][0].lower() + student["last_name"][0].lower()
        username = f"{student['challenge']}-{student['dob_sum']}-{initials}"
        username_hash = hash_username(username, salt)

        new_student = Student(
            first_name=student["first_name"],
            last_initial=student["last_name"][0],
            block=student["block"],
            salt=salt,
            username_hash=username_hash,
            pin_hash=generate_password_hash("1234"),
            passphrase_hash=generate_password_hash("testingpass"),
        )
        db.session.add(new_student)

    db.session.commit()
    print("✅ Dummy students seeded successfully.")

if __name__ == "__main__":
    seed_dummy_students()
