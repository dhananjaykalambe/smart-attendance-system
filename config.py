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

# Color Theme - Modern Dark/Light Hybrid
THEME = {
    "primary": "#1a1a2e",
    "primary-dark": "#0f0f1a",
    "primary-light": "#16213e",
    "accent": "#e94560",
    "accent-success": "#0f3460",
    "success": "#00b4d8",
    "warning": "#f4a261",
    "danger": "#e76f51",
    "info": "#48cae4",
    "dark": "#0a0a0a",
    "light": "#f8f9fa",
    "gray": "#6c757d",
    "card-bg": "#1e1e2e",
    "text-primary": "#e0e0e0",
    "text-secondary": "#a0a0a0"
}