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
    "logs": "logs",
    "qr_tokens": "qr_tokens"  # NEW: Store dynamic QR tokens
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
    "session_timeout_minutes": 30,
    # NEW: Dynamic QR settings
    "qr_refresh_interval": 15,  # QR refreshes every 15 seconds
    "verification_code_length": 6,  # Length of live verification code
    "enable_device_fingerprinting": True,
    "enable_verification_code": True
}

# ====================================================================
# APP CONFIGURATION
# ====================================================================
APP_NAME = "Smart Attendance System"
APP_VERSION = "3.1.0"  # Updated version
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

# Session configuration
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Rate limiting
RATE_LIMIT = "100 per minute"

# ====================================================================
# UI THEME - Professional Blue Theme (No Gradients)
# ====================================================================
THEME = {
    # Primary Blue Palette
    "primary": "#1a3a6b",        # Dark navy blue
    "primary-dark": "#0f2347",   # Very dark blue
    "primary-light": "#2a5298",  # Medium blue
    "primary-soft": "#e8edf5",   # Very light blue
    
    # Accent Colors (Subdued)
    "accent": "#1e4d8c",         # Blue accent
    "accent-hover": "#163d73",   # Darker blue accent
    
    # Status Colors
    "success": "#28a745",        # Green
    "success-soft": "#d4edda",   
    "warning": "#ffc107",        # Yellow
    "warning-soft": "#fff3cd",
    "danger": "#dc3545",         # Red
    "danger-soft": "#f8d7da",
    "info": "#17a2b8",           # Cyan
    "info-soft": "#d1ecf1",
    
    # Neutral Colors
    "dark": "#1a1a2e",
    "light": "#f8f9fa",
    "gray": "#6c757d",
    "gray-light": "#e9ecef",
    "gray-dark": "#343a40",
    
    # UI Elements
    "card-bg": "#ffffff",
    "text-primary": "#1a3a6b",
    "text-secondary": "#495057",
    "text-muted": "#6c757d",
    "border-color": "#dee2e6",
    
    # Shadows (Professional - no color tint)
    "shadow-sm": "0 1px 3px rgba(0,0,0,0.08)",
    "shadow-md": "0 4px 12px rgba(0,0,0,0.10)",
    "shadow-lg": "0 8px 24px rgba(0,0,0,0.12)",
    
    # Radius
    "radius-sm": "4px",
    "radius-md": "8px",
    "radius-lg": "12px"
}