
import os

db_file = 'dev.db'
if os.path.exists(db_file):
    os.remove(db_file)
    print(f"Successfully deleted {db_file}")
else:
    print(f"Database file '{db_file}' not found.")
