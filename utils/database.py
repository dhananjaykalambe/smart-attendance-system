# utils/database.py
# ====================================================================
# DATABASE UTILITIES
# ====================================================================

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

class Database:
    """MongoDB database wrapper"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.collections = {}
    
    def connect(self, uri, db_name):
        """Connect to MongoDB"""
        try:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[db_name]
            
            # Initialize collections
            self.collections = {
                'students': self.db['students'],
                'faculty': self.db['faculty'],
                'admins': self.db['admins'],
                'sessions': self.db['sessions'],
                'attendance': self.db['attendance'],
                'notices': self.db['notices'],
                'settings': self.db['settings'],
                'logs': self.db['logs'],
                'qr_tokens': self.db['qr_tokens'],  # NEW
                'attendance_attempts': self.db['attendance_attempts']  # NEW
            }
            
            # Create indexes
            self._create_indexes()
            
            logger.info(f"Connected to MongoDB database: {db_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection failed: {e}")
            return False
    
    def _create_indexes(self):
        """Create database indexes for performance"""
        try:
            # QR tokens indexes
            self.db['qr_tokens'].create_index('session_id')
            self.db['qr_tokens'].create_index('token_id', unique=True)
            self.db['qr_tokens'].create_index('expires_at')
            self.db['qr_tokens'].create_index([('created_at', -1)])
            
            # Attendance attempts indexes
            self.db['attendance_attempts'].create_index('session_id')
            self.db['attendance_attempts'].create_index('student_id')
            self.db['attendance_attempts'].create_index('timestamp')
            
            # Existing indexes
            self.db['attendance'].create_index('student_id')
            self.db['attendance'].create_index('session_id')
            self.db['sessions'].create_index('session_id', unique=True)
            self.db['students'].create_index('roll_no', unique=True)
            self.db['faculty'].create_index('faculty_id', unique=True)
            self.db['admins'].create_index('admin_id', unique=True)
            
            logger.info("Database indexes created")
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")
    
    def __getattr__(self, name):
        """Access collections directly"""
        if name in self.collections:
            return self.collections[name]
        raise AttributeError(f"'Database' object has no attribute '{name}'")

# Global database instance
db = Database()

def get_db():
    """Get database instance"""
    return db

def init_db(app):
    """Initialize database with default data"""
    from config import MONGO_URI, DB_NAME, DEFAULT_SETTINGS
    
    # Connect to database
    if not db.connect(MONGO_URI, DB_NAME):
        logger.error("Database connection failed. Exiting...")
        return False
    
    # Initialize settings
    if db.settings.count_documents({}) == 0:
        db.settings.insert_one(DEFAULT_SETTINGS)
        logger.info("✓ Settings initialized")
    
    # Initialize admin
    if db.admins.count_documents({}) == 0:
        db.admins.insert_one({
            "admin_id": "ADMIN001",
            "name": "System Administrator",
            "email": "admin@pbcoe.edu",
            "password": "admin123",
            "role": "super_admin",
            "created_at": datetime.now()
        })
        logger.info("✓ Admin account created: ADMIN001 / admin123")
    
    # Initialize faculty
    if db.faculty.count_documents({}) == 0:
        faculty_data = [
            {"faculty_id": "FAC001", "name": "Prof. Rahul Khadse", "email": "khadse@pbcoe.edu", 
             "department": "CSE", "password": "faculty123", "created_at": datetime.now()},
            {"faculty_id": "FAC002", "name": "Prof. Swati Tikle", "email": "tikle@pbcoe.edu", 
             "department": "CSE", "password": "faculty123", "created_at": datetime.now()},
            {"faculty_id": "FAC003", "name": "Prof. Priyanka Katore", "email": "katore@pbcoe.edu", 
             "department": "CSE", "password": "faculty123", "created_at": datetime.now()},
        ]
        db.faculty.insert_many(faculty_data)
        logger.info("✓ Faculty accounts created")
    
    # Initialize students
    if db.students.count_documents({}) == 0:
        student_data = [
            {"roll_no": "CS001", "name": "Alice Johnson", "branch": "CSE", "year": 3, 
             "semester": 6, "email": "alice@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CS002", "name": "Bob Williams", "branch": "CSE", "year": 3, 
             "semester": 6, "email": "bob@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CS003", "name": "Charlie Brown", "branch": "CSE", "year": 3, 
             "semester": 6, "email": "charlie@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CS004", "name": "Diana Prince", "branch": "CSE", "year": 3, 
             "semester": 6, "email": "diana@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CS005", "name": "Evan Parker", "branch": "CSE", "year": 3, 
             "semester": 6, "email": "evan@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "ME001", "name": "John Mechanical", "branch": "ME", "year": 3, 
             "semester": 6, "email": "john@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CE001", "name": "Sarah Civil", "branch": "CE", "year": 3, 
             "semester": 6, "email": "sarah@pbcoe.edu", "created_at": datetime.now()},
        ]
        db.students.insert_many(student_data)
        logger.info("✓ Student accounts created")
    
    # Initialize sample notice
    if db.notices.count_documents({}) == 0:
        db.notices.insert_one({
            "title": "Welcome to Smart Attendance System",
            "content": "All students are requested to mark their attendance using the QR code system.",
            "author": "Admin",
            "created_at": datetime.now(),
            "is_active": True,
            "priority": "high"
        })
        logger.info("✓ Sample notice created")
    
    logger.info("✓ Database initialization complete!")
    return True