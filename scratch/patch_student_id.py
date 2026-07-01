import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content
    
    # 1. Inject student_user into fixtures
    # In test_rent_item_types.py, `student_in_class`
    # In test_decimal_precision.py, `_attach_class_scope`
    
    seat_creation_pattern = re.compile(
        r'^([ \t]+)(?:([a-zA-Z0-9_]+)[ \t]*=[ \t]*)?(?:_tb_seat[ \t]*=[ \t]*)?Seat\([ \t]*(.*?student_id=([a-zA-Z0-9_]+)\.id.*?)\)', 
        re.MULTILINE | re.DOTALL
    )

    def seat_replacement(match):
        indent = match.group(1)
        var_name = match.group(2) or "_seat"
        inner_args = match.group(3)
        student_var = match.group(4)
        
        # If user_id is already there, skip
        if "user_id=" in inner_args:
            return match.group(0)

        user_var_name = f"{student_var}_user"
        
        # Check if we already injected user for this student
        injection = ""
        # Just safely use get_or_create pattern inline
        injection += (
            f"{indent}# Auto-injected Canonical User\n"
            f"{indent}{user_var_name} = User.query.filter_by(username_hash=f\"auto_{{{student_var}.id}}\").first()\n"
            f"{indent}if not {user_var_name}:\n"
            f"{indent}    {user_var_name} = User(username_hash=f\"auto_{{{student_var}.id}}\", username_lookup_hash=f\"auto_l_{{{student_var}.id}}\", user_role=UserRole.STUDENT)\n"
            f"{indent}    db.session.add({user_var_name})\n"
            f"{indent}    db.session.flush()\n"
            f"{indent}"
        )
        
        new_inner = re.sub(r'student_id=[a-zA-Z0-9_]+\.id', f'user_id={user_var_name}.id', inner_args)
        
        if var_name == "_seat" and "_tb_seat" not in match.group(0):
             new_seat_call = f"Seat({new_inner})"
        else:
             assigned_var = match.group(2) if match.group(2) else "_tb_seat"
             new_seat_call = f"{assigned_var} = Seat({new_inner})"
             
        return injection + new_seat_call

    content = seat_creation_pattern.sub(seat_replacement, content)

    # 2. Fix other uses of student_id in Transaction, Seat.query, etc.
    def filter_by_replacement(match):
        student_var = match.group(1)
        return f"user_id={student_var}_user.id"
        
    content = re.sub(r'student_id=([a-zA-Z0-9_]+)\.id', filter_by_replacement, content)
    
    # What about Transaction(student_id=student.id)? 
    # Since filter_by_replacement will replace student_id=student.id with user_id=student_user.id,
    # This will automatically fix Transaction(student_id=student.id) -> Transaction(user_id=student_user.id)!

    # 3. Handle Seat.student_id attribute access
    content = re.sub(r'Seat\.student_id', r'Seat.user_id', content)
    content = re.sub(r'seat\.student_id', r'seat.user_id', content)
    
    # 4. Handle sess['student_id'] = student.id -> we leave sess['student_id'] alone because 
    # it's the session key which the legacy endpoints read. Wait, V2 deprecated it? 
    # "extinct session key dependencies (e.g., admin_id, student_id)" -> yes, V2 uses 'user_id' in session!
    content = re.sub(r"sess\['student_id'\]", "sess['user_id']", content)
    # also we need to make sure we assign it student_user.id
    content = re.sub(r"sess\['user_id'\] = student\.id", "sess['user_id'] = student_user.id", content)

    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Patched {filepath}")

for fp in ['tests/test_rent_item_types.py', 'tests/test_decimal_precision.py']:
    patch_file(fp)

