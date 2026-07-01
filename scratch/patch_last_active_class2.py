import re

filepaths = ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']

for filepath in filepaths:
    with open(filepath, 'r') as f:
        content = f.read()

    # Replace `student_user.last_active_class_id = ClassEconomy.query.first().class_id`
    # with `student_user.last_active_class_id = Seat.query.filter_by(user_id=student_user.id).first().class_id`
    
    content = content.replace(
        "student_user.last_active_class_id = ClassEconomy.query.first().class_id",
        "student_user.last_active_class_id = Seat.query.filter_by(user_id=student_user.id).first().class_id"
    )
    
    with open(filepath, 'w') as f:
        f.write(content)

