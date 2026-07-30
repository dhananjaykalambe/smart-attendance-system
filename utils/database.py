# utils/database.py
# ====================================================================
# DATABASE UTILITIES
# ====================================================================

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime
import os
import logging
import random
import string

logger = logging.getLogger(__name__)


def generate_verification_code(length=6):
    """
    Generate a numeric verification code for QR attendance
    
    Args:
        length (int): Length of the verification code (default: 6)
    
    Returns:
        str: Numeric verification code
    """
    return ''.join(random.choices(string.digits, k=length))


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
                'verification_codes': self.db['verification_codes']  # New collection for tracking codes
            }
            
            logger.info(f"Connected to MongoDB database: {db_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection failed: {e}")
            return False
    
    def __getattr__(self, name):
        """Access collections directly"""
        if name in self.collections:
            return self.collections[name]
        raise AttributeError(f"'Database' object has no attribute '{name}'")
    
    def create_verification_code(self, session_id, length=6, expiry_seconds=60):
        """
        Create and store a verification code for a session
        
        Args:
            session_id (str): The session ID
            length (int): Length of the code
            expiry_seconds (int): How long the code is valid
        
        Returns:
            str: The generated verification code
        """
        code = generate_verification_code(length)
        expires_at = datetime.now().timestamp() + expiry_seconds
        
        # Store the verification code
        self.verification_codes.insert_one({
            'session_id': session_id,
            'code': code,
            'created_at': datetime.now(),
            'expires_at': datetime.fromtimestamp(expires_at),
            'expiry_timestamp': expires_at,
            'is_used': False,
            'used_by': None
        })
        
        # Also update the session with the current code for quick lookup
        self.sessions.update_one(
            {'session_id': session_id},
            {'$set': {
                'verification_code': code,
                'verification_expires_at': datetime.fromtimestamp(expires_at)
            }}
        )
        
        return code
    
    def verify_code(self, session_id, code):
        """
        Verify a verification code for a session
        
        Args:
            session_id (str): The session ID
            code (str): The code to verify
        
        Returns:
            bool: True if valid, False otherwise
        """
        now = datetime.now()
        
        # Find the verification code
        vc = self.verification_codes.find_one({
            'session_id': session_id,
            'code': code,
            'is_used': False,
            'expires_at': {'$gt': now}
        })
        
        if vc:
            # Mark as used
            self.verification_codes.update_one(
                {'_id': vc['_id']},
                {'$set': {'is_used': True}}
            )
            return True
        
        # Also check if there's a code directly in the session (for backward compatibility)
        session = self.sessions.find_one({'session_id': session_id})
        if session and session.get('verification_code') == code:
            expiry = session.get('verification_expires_at')
            if expiry and expiry > now:
                return True
        
        return False
    
    def refresh_verification_code(self, session_id, length=6, expiry_seconds=60):
        """
        Refresh the verification code for a session
        
        Args:
            session_id (str): The session ID
            length (int): Length of the code
            expiry_seconds (int): How long the code is valid
        
        Returns:
            str: The new verification code
        """
        # Mark old codes as used/expired
        self.verification_codes.update_many(
            {'session_id': session_id, 'is_used': False},
            {'$set': {'is_used': True}}
        )
        
        # Generate and store new code
        return self.create_verification_code(session_id, length, expiry_seconds)
    
    def get_active_verification_code(self, session_id):
        """
        Get the current active verification code for a session
        
        Args:
            session_id (str): The session ID
        
        Returns:
            str: The active verification code or None
        """
        now = datetime.now()
        
        vc = self.verification_codes.find_one({
            'session_id': session_id,
            'is_used': False,
            'expires_at': {'$gt': now}
        })
        
        if vc:
            return vc['code']
        
        # Check session for quick lookup
        session = self.sessions.find_one({'session_id': session_id})
        if session and session.get('verification_code'):
            expiry = session.get('verification_expires_at')
            if expiry and expiry > now:
                return session['verification_code']
        
        return None


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
    
    # Create indexes for better performance
    create_indexes(db)
    
    logger.info("✓ Database initialization complete!")
    return True


def create_indexes(db):
    """Create database indexes for better performance"""
    try:
        # Students indexes
        db.students.create_index("roll_no", unique=True)
        db.students.create_index("branch")
        
        # Faculty indexes
        db.faculty.create_index("faculty_id", unique=True)
        
        # Sessions indexes
        db.sessions.create_index("session_id", unique=True)
        db.sessions.create_index([("end_time", 1)])
        db.sessions.create_index([("is_active", 1)])
        
        # Attendance indexes
        db.attendance.create_index([("student_id", 1), ("session_id", 1)])
        db.attendance.create_index("subject")
        db.attendance.create_index("time")
        
        # Verification codes indexes
        db.verification_codes.create_index([("session_id", 1), ("expires_at", 1)])
        db.verification_codes.create_index([("expires_at", 1), ("is_used", 1)])
        
        # Logs indexes
        db.logs.create_index("timestamp")
        db.logs.create_index("user_id")
        
        # Notices indexes
        db.notices.create_index("created_at")
        
        logger.info("✓ Database indexes created")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")