# ====================================================================
# SIMPLE MONGODB CONNECTION TEST
# ====================================================================

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

uri = os.getenv("MONGO_URI")

if not uri:
    print("❌ MONGO_URI not found in .env file!")
    exit(1)

print("=" * 60)
print("🔌 Testing MongoDB Connection...")
print("=" * 60)

try:
    display_uri = uri.split('@')[0][:30] + "...@" + uri.split('@')[1] if '@' in uri else uri[:50]
    print(f"\n📡 Connecting to: {display_uri}")
    
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    client.admin.command('ping')
    print("\n✅ MongoDB Connection SUCCESSFUL!")
    
    db_name = os.getenv("DB_NAME", "smart_attendance")
    db = client[db_name]
    collections = db.list_collection_names()
    print(f"\n📚 Database: {db_name}")
    print(f"📋 Collections found: {len(collections)}")
    
    for col in collections:
        count = db[col].count_documents({})
        print(f"   - {col}: {count} documents")
    
    print("\n🎉 Your database is ready to use!")
    
except Exception as e:
    print(f"\n❌ Connection FAILED: {e}")
    print("\n🔧 Troubleshooting:")
    print("1. Check your internet connection")
    print("2. Go to MongoDB Atlas → Network Access → Add IP Address 0.0.0.0/0")
    print("3. Verify username and password in .env file")

print("\n" + "=" * 60)