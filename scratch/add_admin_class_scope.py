import re

filepath = 'tests/test_rent_item_types.py'
with open(filepath, 'r') as f:
    content = f.read()

def process_test(match):
    test_def = match.group(1)
    test_body = match.group(2)
    
    # If the test uses admin_class_scope or admin_class_scope.class_id but doesn't have it in signature
    if "admin_class_scope" in test_body and "admin_class_scope" not in test_def:
        # insert admin_class_scope before closing parenthesis
        test_def = re.sub(r'\):', ', admin_class_scope):', test_def)
    
    return test_def + test_body

new_content = re.sub(r'(def test_[^\(]+\([^\)]+\):)([\s\S]*?)(?=\ndef test_|\Z)', process_test, content)

with open(filepath, 'w') as f:
    f.write(new_content)

