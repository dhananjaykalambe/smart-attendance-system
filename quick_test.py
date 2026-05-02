# quick_test.py - Simple connection test
from pymongo import MongoClient

# Your corrected connection string
uri = "mongodb+srv://admin_user2324:Attendance%402324@smartattendancecluster.mrbdlvp.mongodb.net/?retryWrites=true&w=majority"

print("Testing connection...")
try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ Connection successful!")
    print("✅ Database is ready to use!")
    
    # List databases
    print("\n📚 Available databases:")
    for db in client.list_database_names():
        print(f"   - {db}")
        
except Exception as e:
    print(f"❌ Connection failed: {e}")