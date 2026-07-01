import re

filepaths = ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']

for filepath in filepaths:
    with open(filepath, 'r') as f:
        content = f.read()

    # Add seat_id to StudentItem
    content = content.replace("StudentItem(correlation_id", "StudentItem(seat_id=Seat.query.filter_by(user_id=student_user.id).first().id, correlation_id")
    
    # Let's also check StudentBlock. Wait, does StudentBlock have seat_id?
    # Usually StudentBlock doesn't use correlation_id. Let's just find StudentBlock(student_id=student.id
    content = content.replace("StudentBlock(student_id=student.id", "StudentBlock(student_id=student.id, seat_id=Seat.query.filter_by(user_id=student_user.id).first().id")
    
    with open(filepath, 'w') as f:
        f.write(content)

