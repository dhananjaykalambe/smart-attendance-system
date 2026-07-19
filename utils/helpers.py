# utils/helpers.py
# ====================================================================
# HELPER FUNCTIONS
# ====================================================================

from datetime import datetime
import hashlib
import hmac
from flask import request, session
import os

def get_settings():
    """Get system settings from database"""
    from utils.database import db
    from config import DEFAULT_SETTINGS
    
    settings = db.settings.find_one({})
    return settings if settings else DEFAULT_SETTINGS

def get_college_header():
    """Get college header text"""
    settings = get_settings()
    college_name = settings.get("college_name", "Priyadarshini Bhagwati College of Engineering")
    college_location = settings.get("college_location", "Nagpur")
    return f"🎓 {college_name}, {college_location}"

def generate_secure_qr_hash(session_id, timestamp):
    """Generate secure hash for QR code"""
    secret = os.getenv("SECRET_KEY", "smart_attendance_secret_key_2024").encode()
    message = f"{session_id}:{timestamp}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:16]

def verify_qr_hash(session_id, timestamp, provided_hash):
    """Verify QR code hash"""
    expected_hash = generate_secure_qr_hash(session_id, timestamp)
    return hmac.compare_digest(expected_hash, provided_hash)

def get_client_ip():
    """Get client IP address"""
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]
    elif request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
    else:
        ip = request.remote_addr
    return ip

def is_session_active(end_time):
    """Check if session is still active"""
    if not end_time:
        return True
    return datetime.now() <= end_time

def get_sidebar_links():
    """Get sidebar navigation links based on user role"""
    role = session.get('role')
    
    common_links = [
        {"url": "/attendance", "icon": "📜", "text": "Attendance Records"},
        {"url": "/subject_details", "icon": "📚", "text": "Subject Details"},
        {"url": "/about", "icon": "ℹ️", "text": "About"}
    ]
    
    if role == 'faculty':
        main_links = [
            {"url": "/faculty_dashboard", "icon": "📊", "text": "Dashboard"},
            {"url": "/create_session", "icon": "➕", "text": "Create Session"},
            {"url": "/add_student", "icon": "👥", "text": "Manage Students"},
            {"url": "/students_report", "icon": "📑", "text": "Reports"}
        ]
        return {"main": main_links, "common": common_links}
    
    elif role == 'admin':
        main_links = [
            {"url": "/admin_dashboard", "icon": "👑", "text": "Dashboard"},
            {"url": "/admin/manage_faculty", "icon": "👥", "text": "Manage Faculty"},
            {"url": "/admin/manage_students", "icon": "👨‍🎓", "text": "Manage Students"},
            {"url": "/admin/manage_sessions", "icon": "📊", "text": "Manage Sessions"},
            {"url": "/admin/system_settings", "icon": "⚙️", "text": "System Settings"},
            {"url": "/admin/change_password", "icon": "🔐", "text": "Change Password"}
        ]
        return {"main": main_links, "common": common_links}
    
    elif role == 'student':
        main_links = [
            {"url": "/student_dashboard", "icon": "📊", "text": "Dashboard"},
            {"url": "/scan", "icon": "📷", "text": "Scan QR"}
        ]
        return {"main": main_links, "common": common_links}
    
    else:
        main_links = [
            {"url": "/", "icon": "🏠", "text": "Home"},
            {"url": "/login", "icon": "🔐", "text": "Login"}
        ]
        return {"main": main_links, "common": [
            {"url": "/subject_details", "icon": "📚", "text": "Subject Details"},
            {"url": "/about", "icon": "ℹ️", "text": "About"}
        ]}

def get_dashboard_stats():
    """Get dashboard statistics"""
    from utils.database import db
    from datetime import datetime
    
    total_students = db.students.count_documents({})
    total_faculty = db.faculty.count_documents({})
    total_sessions = db.sessions.count_documents({})
    total_attendance = db.attendance.count_documents({})
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sessions = db.sessions.count_documents({"created_at": {"$gte": today_start}})
    active_sessions = db.sessions.count_documents({"end_time": {"$gt": datetime.now()}, "is_active": True})
    
    recent_notices = list(db.notices.find({}).sort("created_at", -1).limit(5))
    
    return {
        "total_students": total_students,
        "total_faculty": total_faculty,
        "total_sessions": total_sessions,
        "total_attendance": total_attendance,
        "today_sessions": today_sessions,
        "active_sessions": active_sessions,
        "recent_notices": recent_notices
    }

def check_low_attendance(student_id):
    """Check for low attendance alerts"""
    from utils.database import db
    
    settings = get_settings()
    threshold = settings.get("attendance_threshold", 75)
    
    attendance_records = list(db.attendance.find({"student_id": student_id}))
    all_sessions = list(db.sessions.find({}))
    
    subject_stats = {}
    for session_item in all_sessions:
        subject = session_item.get("subject")
        if subject:
            if subject not in subject_stats:
                subject_stats[subject] = {"total": 0, "attended": 0}
            subject_stats[subject]["total"] += 1
    
    for record in attendance_records:
        subject = record.get("subject")
        if subject and subject in subject_stats:
            subject_stats[subject]["attended"] += 1
    
    alerts = []
    for subject, data in subject_stats.items():
        percentage = (data["attended"] / data["total"]) * 100 if data["total"] > 0 else 0
        if percentage < threshold:
            alerts.append({
                "subject": subject,
                "percentage": round(percentage, 2),
                "required": threshold,
                "shortage": round(threshold - percentage, 2)
            })
    return alerts

def log_activity(action, user_id, ip_address, details=""):
    """Log user activity"""
    from utils.database import db
    from datetime import datetime
    
    log_entry = {
        "action": action,
        "user_id": user_id,
        "role": session.get('role', 'unknown'),
        "ip_address": ip_address,
        "details": details,
        "timestamp": datetime.now()
    }
    db.logs.insert_one(log_entry)