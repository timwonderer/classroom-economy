import hmac
import hashlib
import csv
import os
from app import db, Student, app
from dotenv import load_dotenv

load_dotenv()

def compute_name_code(first_name, last_name):
    import re
    vowels = re.findall(r'[AEIOUaeiou]', first_name)
    consonants = re.findall(r'[^AEIOUaeiou\W\d_]', last_name)
    return ''.join(vowels + consonants).lower()

def compute_dob_sum(dob_str):
    mm, dd, yyyy = map(int, dob_str.split('/'))
    return mm + dd + yyyy

def validate_from_csv():
    pepper = os.getenv('PEPPER_KEY', 'dev_pepper_here').encode()
    csv_path = "sample_students.csv"

    # Load CSV into a list for easy lookup
    student_data = []
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            student_data.append(row)

    with app.app_context():
        students = Student.query.all()
        for student in students:
            # Find the corresponding CSV row
            match = next((r for r in student_data if r['first_name'].strip() == student.first_name.strip() and r['block'].strip().upper() == student.block.strip().upper()), None)
            if not match:
                print(f"No CSV match found for {student.first_name} in block {student.block}")
                continue

            last_name = match['last_name'].strip()
            dob_str = match['date_of_birth'].strip()

            name_code = compute_name_code(student.first_name, last_name)
            dob_sum = compute_dob_sum(dob_str)

            # Validate dob_sum matches
            if student.dob_sum != dob_sum:
                print(f"DOB SUM MISMATCH for {student.first_name}: stored {student.dob_sum}, computed {dob_sum}")

            first_half_hash_check = hmac.new(pepper, student.salt + name_code.encode(), hashlib.sha256).hexdigest()
            second_half_hash_check = hmac.new(pepper, student.salt + str(dob_sum).encode(), hashlib.sha256).hexdigest()

            is_first_match = (student.first_half_hash == first_half_hash_check)
            is_second_match = (student.second_half_hash == second_half_hash_check)

            print(f"Student ID: {student.id}")
            print(f"Name: {student.first_name}")
            print(f"Expected First Half Hash: {first_half_hash_check}")
            print(f"Stored First Half Hash:   {student.first_half_hash}")
            print(f"Match: {is_first_match}")
            print(f"Expected Second Half Hash: {second_half_hash_check}")
            print(f"Stored Second Half Hash:   {student.second_half_hash}")
            print(f"Match: {is_second_match}")
            print("-" * 40)

if __name__ == "__main__":
    validate_from_csv()