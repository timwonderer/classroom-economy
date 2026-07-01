import re

filepaths = ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']

for filepath in filepaths:
    with open(filepath, 'r') as f:
        content = f.read()

    # Revert for StudentItem
    content = re.sub(r'StudentItem\([^)]*user_id=student_user.id', lambda m: m.group(0).replace('user_id=student_user.id', 'student_id=student.id'), content)
    content = re.sub(r'StudentItem\.query\.filter_by\([^)]*user_id=student_user.id', lambda m: m.group(0).replace('user_id=student_user.id', 'student_id=student.id'), content)
    
    # Revert for StudentBlock
    content = re.sub(r'StudentBlock\([^)]*user_id=student_user.id', lambda m: m.group(0).replace('user_id=student_user.id', 'student_id=student.id'), content)
    content = re.sub(r'StudentBlock\.query\.filter_by\([^)]*user_id=student_user.id', lambda m: m.group(0).replace('user_id=student_user.id', 'student_id=student.id'), content)

    # Revert for RecoveryRequest (if it has student_id, wait, did it?)
    content = re.sub(r'RecoveryRequest\([^)]*user_id=student_user.id', lambda m: m.group(0).replace('user_id=student_user.id', 'student_id=student.id'), content)
    
    with open(filepath, 'w') as f:
        f.write(content)

