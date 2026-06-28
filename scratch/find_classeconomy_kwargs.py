import ast
import os

class ClassEconomyVisitor(ast.NodeTransformer):
    def visit_Call(self, node):
        self.generic_visit(node)
        
        # Check if the call is ClassEconomy()
        if isinstance(node.func, ast.Name) and node.func.id == 'ClassEconomy':
            for keyword in node.keywords:
                if keyword.arg == 'teacher_id':
                    keyword.arg = 'user_id'
                    
        # Or if it's a call to a builder that sets teacher_id for class economy
        # Not sure, let's just stick to ClassEconomy constructor for now
        return node

    # We also want to catch things like ClassEconomy.query.filter_by(teacher_id=...)
    def visit_Call_filter_by(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'filter_by':
            # It's hard to know if it's ClassEconomy without complex analysis
            # We'll just rely on grep for those.
            pass

def process_file(filepath):
    with open(filepath, 'r') as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except Exception:
        return False

    visitor = ClassEconomyVisitor()
    new_tree = visitor.visit(tree)
    
    # We use ast.unparse which is available in Python 3.9+
    new_source = ast.unparse(new_tree)
    
    if source != new_source:
        # ast.unparse removes some formatting (comments etc.)
        # so this is destructive. A better way is using a token-based replacer like tokenize
        # or simple regex on the original file
        return True
    return False

# Since ast.unparse ruins comments and formatting, let's write a regex that matches ClassEconomy constructor
import re

def process_file_regex(filepath):
    with open(filepath, 'r') as f:
        source = f.read()
        
    # We want to find ClassEconomy(*args, teacher_id=..., **kwargs)
    # This regex is a bit complex. Let's just find "teacher_id=" and check if "ClassEconomy" is in the same file.
    # It might be easier to just manually fix the 10-20 files that fail testing.

    # But we can do this: replace "ClassEconomy(" ... "teacher_id=" with "user_id="
    
    # Let's just look for 'teacher_id=' in files that import or use ClassEconomy.
    # And replace it manually or print them out so I can see them.
    if 'ClassEconomy' in source and 'teacher_id=' in source:
        print(f"Needs manual inspection: {filepath}")

for root, dirs, files in os.walk('.'):
    if 'venv' in root or '.git' in root: continue
    for file in files:
        if file.endswith('.py'):
            process_file_regex(os.path.join(root, file))
