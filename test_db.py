# ====================================================================
# MONGODB CONNECTION TEST FILE (test_db.py)
# ====================================================================
# Save this file in your project root directory
# Run: python test_db.py
# ====================================================================

import os
from pymongo import MongoClient
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_connection():
    """Test MongoDB connection and display database info"""
    
    print("\n" + "="*60)
    print("🔌 MONGODB CONNECTION TEST")
    print("="*60)
    
    # Get connection string
    MONGO_URI = os.getenv("MONGO_URI")
    DB_NAME = os.getenv("DB_NAME", "smart_attendance")
    
    if not MONGO_URI:
        print("\n❌ MONGO_URI not found in .env file!")
        print("Please add: MONGO_URI=your_connection_string")
        return False
    
    # Hide password in display
    display_uri = MONGO_URI.split('@')[0][:30] + "...@" + MONGO_URI.split('@')[1] if '@' in MONGO_URI else MONGO_URI[:50]
    print(f"\n📡 Connecting to: {display_uri}")
    
    try:
        # Try to connect with timeout
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # Ping the server
        client.admin.command('ping')
        print("✅ MongoDB connection successful!")
        
        # Get database
        db = client[DB_NAME]
        print(f"✅ Database selected: {DB_NAME}")
        
        # List all collections
        collections = db.list_collection_names()
        print(f"\n📚 Collections in database: {len(collections)}")
        for col in collections:
            count = db[col].count_documents({})
            print(f"   - {col}: {count} documents")
        
        # Insert test document
        from datetime import datetime
        test_collection = db['test_connection']
        test_doc = {
            "test": "connection_test",
            "timestamp": datetime.now(),
            "status": "success"
        }
        result = test_collection.insert_one(test_doc)
        print(f"\n✅ Test document inserted with ID: {result.inserted_id}")
        
        # Clean up test document
        test_collection.delete_one({"_id": result.inserted_id})
        print("✅ Test document cleaned up")
        
        # Display server info
        server_info = client.server_info()
        print(f"\n🖥️ MongoDB Server Version: {server_info.get('version', 'Unknown')}")
        
        print("\n" + "="*60)
        print("🎉 All tests passed! Your MongoDB is working perfectly!")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ MongoDB connection failed!")
        print(f"Error details: {str(e)}")
        
        print("\n🔧 Troubleshooting steps:")
        print("1. Check your password has special characters (@, !, #, $)")
        print("   - Encode @ as %40")
        print("   - Encode ! as %21")
        print("2. Verify username and password in MongoDB Atlas")
        print("3. Check Network Access IP whitelist (add 0.0.0.0/0)")
        print("4. Ensure cluster name is correct")
        
        print("\n📝 Your connection string should look like:")
        print("mongodb+srv://username:encoded_password@cluster.mongodb.net/")
        print("\nExample: If password is 'pass@123'")
        print("Use: 'pass%40123'")
        
        print("\n" + "="*60 + "\n")
        return False

def check_env_file():
    """Check .env file content"""
    env_path = '.env'
    
    print("\n📁 Checking .env file...")
    
    if not os.path.exists(env_path):
        print("❌ .env file not found!")
        print("\nCreate .env file with:")
        print('MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/')
        print('DB_NAME=smart_attendance')
        return False
    
    print("✅ .env file found")
    
    with open(env_path, 'r') as f:
        content = f.read()
        
    if 'MONGO_URI' in content:
        print("✅ MONGO_URI variable found")
    else:
        print("❌ MONGO_URI not found in .env file")
        
    if 'DB_NAME' in content:
        print("✅ DB_NAME variable found")
    else:
        print("❌ DB_NAME not found in .env file")
    
    return True

def check_atlas_settings():
    """Provide checklist for Atlas settings"""
    print("\n" + "="*60)
    print("📋 MONGODB ATLAS SETTINGS CHECKLIST")
    print("="*60)
    print("\nVerify these in MongoDB Atlas:")
    print("1. ✅ Database User exists (admin_user2324)")
    print("2. ✅ Password is correct (Attendance@2324)")
    print("3. ✅ Network Access has 0.0.0.0/0 (Allow Anywhere)")
    print("4. ✅ Cluster is deployed and running")
    print("5. ✅ Connection string uses encoded password")
    print("\n💡 Remember: @ in password must be %40")
    print("   Your password 'Attendance@2324' → 'Attendance%402324'")
    print("="*60 + "\n")

if __name__ == "__main__":
    print("\n🚀 Starting MongoDB Connection Test...")
    print("📌 Make sure you have created .env file with MONGO_URI")
    
    check_env_file()
    check_atlas_settings()
    test_connection()