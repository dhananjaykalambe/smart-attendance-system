# config.py
# ====================================================================
# SMART ATTENDANCE SYSTEM - PRODUCTION CONFIGURATION
# ====================================================================

import os
import secrets
from dotenv import load_dotenv

load_dotenv()

# ====================================================================
# MONGODB CONNECTION
# ====================================================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "smart_attendance")

# ====================================================================
# COLLECTIONS
# ====================================================================
COLLECTIONS = {
    "students": "students",
    "faculty": "faculty",
    "admins": "admins",
    "sessions": "sessions",
    "attendance": "attendance",
    "notices": "notices",
    "settings": "settings",
    "logs": "logs"
}

# ====================================================================
# DEFAULT SYSTEM SETTINGS
# ====================================================================
DEFAULT_SETTINGS = {
    "attendance_threshold": 75,
    "qr_expiry_seconds": 60,
    "session_duration_minutes": 5,
    "college_name": "Priyadarshini Bhagwati College of Engineering",
    "college_location": "Nagpur",
    "college_header": "Smart Attendance System",
    "academic_year": "2024-25",
    "enable_location_tracking": True,
    "enable_ip_tracking": True,
    "maintenance_mode": False,
    "max_login_attempts": 5,
    "session_timeout_minutes": 30
}

# ====================================================================
# APP CONFIGURATION
# ====================================================================
APP_NAME = "Smart Attendance System"
APP_VERSION = "3.0.0"
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

# Session configuration
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Rate limiting
RATE_LIMIT = "100 per minute"

# Single Color Vibrant Theme - Deep Blue/Indigo
THEME = {
    "primary": "#1a237e",
    "primary-dark": "#0d1445",
    "primary-light": "#283593",
    "primary-soft": "#e8eaf6",
    "accent": "#3f51b5",
    "success": "#1a237e",
    "warning": "#283593",
    "danger": "#1a237e",
    "info": "#3f51b5",
    "dark": "#0d1445",
    "light": "#f5f6fa",
    "gray": "#757575",
    "card-bg": "#ffffff",
    "text-primary": "#1a237e",
    "text-secondary": "#424242"
}