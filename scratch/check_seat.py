import re

filepath = 'tests/test_rent_item_types.py'
with open(filepath, 'r') as f:
    content = f.read()

# I will add a print statement to see what the seat's class_id is!
content = content.replace("student_user.last_active_class_id = Seat.query.filter_by(user_id=student_user.id).first().class_id", "seat = Seat.query.filter_by(user_id=student_user.id).first()\n    print(f'DEBUG_SEAT: id={seat.id}, class_id={seat.class_id}')\n    student_user.last_active_class_id = seat.class_id")

with open(filepath, 'w') as f:
    f.write(content)

