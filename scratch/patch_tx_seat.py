import re

filepaths = ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']

for filepath in filepaths:
    with open(filepath, 'r') as f:
        content = f.read()

    # Find `Transaction(user_id=student_user.id` and add `seat_id=Seat.query.filter_by(user_id=student_user.id).first().id`
    content = content.replace("Transaction(user_id=student_user.id,", "Transaction(user_id=student_user.id, seat_id=Seat.query.filter_by(user_id=student_user.id).first().id,")
    
    with open(filepath, 'w') as f:
        f.write(content)

