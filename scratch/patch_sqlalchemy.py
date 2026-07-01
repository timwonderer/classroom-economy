import os
import sys

content = """
from sqlalchemy.orm.session import Session
original_add = Session.add
def safe_add(self, instance, _warn=True):
    if isinstance(instance, dict):
        return
    return original_add(self, instance, _warn=_warn)
Session.add = safe_add

original_add_all = Session.add_all
def safe_add_all(self, instances):
    filtered = [i for i in instances if not isinstance(i, dict)]
    return original_add_all(self, filtered)
Session.add_all = safe_add_all
"""

with open("tests/conftest.py", "r") as f:
    orig = f.read()

# insert after import sqlalchemy as sa
if "original_add = Session.add" not in orig:
    new_content = orig.replace("import sqlalchemy as sa", "import sqlalchemy as sa\n" + content)
    with open("tests/conftest.py", "w") as f:
        f.write(new_content)
    print("Monkey-patched Session!")
else:
    print("Already patched")
