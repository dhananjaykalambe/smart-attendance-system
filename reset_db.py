# reset_db.py
import os

db_path = 'digiserve.db'
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"✅ Deleted existing database: {db_path}")

print("✅ Database reset complete. Now run 'python app.py'")