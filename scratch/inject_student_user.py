import re

filepath = 'tests/test_rent_item_types.py'
with open(filepath, 'r') as f:
    content = f.read()

def process_test(match):
    test_def = match.group(1)
    test_body = match.group(2)
    
    if "student_user" in test_body and "student_user =" not in test_body:
        # We need to define student_user.
        # Find where to put it. Best place is right after `student = student_in_class`
        # or at the very beginning of the test body.
        injection = '\n    student_user = User.query.filter_by(username_hash=f"auto_{student_in_class.id}").first()'
        
        if "student = student_in_class" in test_body:
            test_body = test_body.replace("student = student_in_class", "student = student_in_class" + injection)
        else:
            # just put it at the top of the test body
            test_body = injection + test_body
            
    return test_def + test_body

new_content = re.sub(r'(def test_[^\(]+\([^\)]+\):)([\s\S]*?)(?=\ndef test_|\Z)', process_test, content)

with open(filepath, 'w') as f:
    f.write(new_content)

