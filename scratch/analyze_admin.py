import ast

def analyze_admin_routes(filepath):
    with open(filepath, 'r') as f:
        source = f.read()

    tree = ast.parse(source)

    violations = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_source = ast.get_source_segment(source, node)
            if not func_source: continue
            
            # Look for get_current_admin() or session.get('admin_id')
            if 'get_current_admin(' in func_source or "session.get('admin_id')" in func_source or 'session.get("admin_id")' in func_source or "session['admin_id']" in func_source or 'session["admin_id"]' in func_source:
                
                # Check if it has a route decorator
                route_path = "Helper/Utility"
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        if decorator.func.attr == 'route':
                            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                route_path = decorator.args[0].value
                
                violations.append((route_path, node.name))

    # Group by basic prefixes
    groups = {
        "Dashboard & Context": [],
        "Store & Economy": [],
        "Payroll & Transactions": [],
        "Hall Pass": [],
        "Settings & Setup": [],
        "Student & Roster Management": [],
        "Utilities & Misc": []
    }
    
    for path, name in violations:
        if path.startswith('/store') or path.startswith('/economy') or path.startswith('/items'):
            groups["Store & Economy"].append((path, name))
        elif 'payroll' in path or 'transaction' in path or path.startswith('/bonus'):
            groups["Payroll & Transactions"].append((path, name))
        elif path.startswith('/hall-pass'):
            groups["Hall Pass"].append((path, name))
        elif path.startswith('/settings') or path.startswith('/setup') or path.startswith('/class'):
            groups["Settings & Setup"].append((path, name))
        elif path.startswith('/student') or path.startswith('/roster'):
            groups["Student & Roster Management"].append((path, name))
        elif path == '/' or path.startswith('/select-class'):
            groups["Dashboard & Context"].append((path, name))
        else:
            groups["Utilities & Misc"].append((path, name))

    for group, items in groups.items():
        print(f"\n### {group} ({len(items)} sites)")
        for path, name in items:
            print(f"- {name} (`{path}`)")

analyze_admin_routes('app/routes/admin.py')
