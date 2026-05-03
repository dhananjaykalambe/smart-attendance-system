# ====================================================================
# SMART ATTENDANCE SYSTEM - CONFIGURATION
# ====================================================================

import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "smart_attendance")

# Collections
COLLECTIONS = {
    "students": "students",
    "faculty": "faculty",
    "admins": "admins",
    "sessions": "sessions",
    "attendance": "attendance",
    "notices": "notices",
    "settings": "settings"
}

# Default System Settings
DEFAULT_SETTINGS = {
    "attendance_threshold": 75,
    "qr_expiry_seconds": 60,
    "session_duration_minutes": 5,
    "college_name": "Priyadarshini Bhagwati College of Engineering",
    "college_location": "Nagpur",
    "academic_year": "2024-25"
}

# App Settings
APP_NAME = "Smart Attendance System"
APP_VERSION = "2.0.0"