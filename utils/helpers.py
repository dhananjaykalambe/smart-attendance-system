# utils/helpers.py
# ====================================================================
# HELPER FUNCTIONS
# ====================================================================

from datetime import datetime, timedelta
import hashlib
import hmac
import secrets
import string
from flask import request, session
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

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
    return f"{college_name}, {college_location}"

# ====================================================================
# LEGACY QR FUNCTIONS (Preserved for backward compatibility)
# ====================================================================

def generate_secure_qr_hash(session_id, timestamp):
    """Generate secure hash for QR code (legacy compatibility)"""
    secret = os.getenv("SECRET_KEY", "smart_attendance_secret_key_2024").encode()
    message = f"{session_id}:{timestamp}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:16]

def verify_qr_hash(session_id, timestamp, provided_hash):
    """Verify QR code hash (legacy compatibility)"""
    expected_hash = generate_secure_qr_hash(session_id, timestamp)
    return hmac.compare_digest(expected_hash, provided_hash)

# ====================================================================
# DYNAMIC QR TOKEN FUNCTIONS
# ====================================================================

def get_encryption_key():
    """Get or generate encryption key for QR token encryption"""
    key = os.getenv("QR_ENCRYPTION_KEY")
    if not key:
        # Generate key from SECRET_KEY
        secret = os.getenv("SECRET_KEY", "smart_attendance_secret_key_2024").encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"smart_attendance_salt",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret))
    return key

def generate_qr_token(session_id, subject, duration_minutes=5):
    """
    Generate a new dynamic QR token for a session
    
    Returns:
        dict: {
            'token': encrypted_token_string,
            'verification_code': str,
            'expires_at': datetime,
            'created_at': datetime
        }
    """
    from utils.database import db
    
    settings = get_settings()
    refresh_interval = settings.get("qr_refresh_interval", 15)
    code_length = settings.get("verification_code_length", 6)
    
    # Generate verification code
    verification_code = ''.join(secrets.choice(string.digits) for _ in range(code_length))
    
    # Generate unique token ID
    token_id = secrets.token_hex(16)
    
    # Create token payload
    payload = {
        'token_id': token_id,
        'session_id': session_id,
        'subject': subject,
        'verification_code': verification_code,
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(seconds=refresh_interval)).isoformat()
    }
    
    # Encrypt payload
    key = get_encryption_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(json.dumps(payload).encode())
    token = base64.urlsafe_b64encode(encrypted).decode()
    
    # Store token in database
    token_doc = {
        'token_id': token_id,
        'session_id': session_id,
        'token': token,
        'verification_code': verification_code,
        'created_at': datetime.now(),
        'expires_at': datetime.now() + timedelta(seconds=refresh_interval),
        'is_used': False,
        'revoked': False
    }
    db.qr_tokens.insert_one(token_doc)
    
    # Clean up old tokens (keep only last 100 per session)
    cleanup_old_tokens(session_id)
    
    return {
        'token': token,
        'verification_code': verification_code,
        'expires_at': token_doc['expires_at'],
        'created_at': token_doc['created_at']
    }

def verify_qr_token(token, verification_code=None):
    """
    Verify a dynamic QR token
    
    Args:
        token: The encrypted token string
        verification_code: Optional verification code to match
    
    Returns:
        dict: {
            'valid': bool,
            'session_id': str or None,
            'subject': str or None,
            'error': str or None
        }
    """
    from utils.database import db
    
    try:
        # Decrypt token
        key = get_encryption_key()
        fernet = Fernet(key)
        decoded = base64.urlsafe_b64decode(token.encode())
        decrypted = fernet.decrypt(decoded)
        payload = json.loads(decrypted.decode())
        
        # Check if token exists and is valid
        token_doc = db.qr_tokens.find_one({'token_id': payload['token_id']})
        if not token_doc:
            return {'valid': False, 'error': 'Invalid token'}
        
        if token_doc.get('revoked', False):
            return {'valid': False, 'error': 'Token has been revoked'}
        
        if token_doc.get('is_used', False):
            return {'valid': False, 'error': 'Token has already been used'}
        
        # Check expiry
        expires_at = datetime.fromisoformat(payload['expires_at'])
        if datetime.now() > expires_at:
            return {'valid': False, 'error': 'Token has expired'}
        
        # Verify verification code if provided
        if verification_code is not None:
            if payload['verification_code'] != verification_code:
                return {'valid': False, 'error': 'Invalid verification code'}
        
        return {
            'valid': True,
            'session_id': payload['session_id'],
            'subject': payload['subject'],
            'token_id': payload['token_id'],
            'verification_code': payload['verification_code']
        }
        
    except Exception as e:
        return {'valid': False, 'error': f'Token verification failed: {str(e)}'}

def cleanup_old_tokens(session_id, keep_count=100):
    """Clean up old tokens for a session, keeping only the most recent ones"""
    from utils.database import db
    
    # Get tokens for this session, sorted by creation time
    tokens = list(db.qr_tokens.find(
        {'session_id': session_id}
    ).sort('created_at', -1))
    
    # Keep only the most recent 'keep_count' tokens
    if len(tokens) > keep_count:
        to_delete = tokens[keep_count:]
        for token in to_delete:
            db.qr_tokens.delete_one({'_id': token['_id']})

def get_current_qr_token(session_id):
    """
    Get the current valid QR token for a session
    If no valid token exists, generate one
    """
    from utils.database import db
    
    settings = get_settings()
    refresh_interval = settings.get("qr_refresh_interval", 15)
    
    # Find the most recent valid token for this session
    current_time = datetime.now()
    token = db.qr_tokens.find_one({
        'session_id': session_id,
        'expires_at': {'$gt': current_time},
        'revoked': False
    }, sort=[('created_at', -1)])
    
    # If no valid token exists, generate one
    if not token:
        session_data = db.sessions.find_one({'session_id': session_id})
        if session_data:
            token_data = generate_qr_token(session_id, session_data.get('subject', 'Unknown'))
            return token_data
    
    if token:
        return {
            'token': token['token'],
            'verification_code': token['verification_code'],
            'expires_at': token['expires_at'],
            'created_at': token['created_at']
        }
    
    return None

def get_qr_status(session_id):
    """
    Get the current QR status for a session
    Returns: dict with status and current token info
    """
    from utils.database import db
    
    current_time = datetime.now()
    
    # Check if session exists and is active
    session_data = db.sessions.find_one({'session_id': session_id})
    if not session_data:
        return {'status': 'error', 'message': 'Session not found'}
    
    if not session_data.get('is_active', False):
        return {'status': 'inactive', 'message': 'Session is not active'}
    
    if session_data.get('end_time') and current_time > session_data['end_time']:
        return {'status': 'expired', 'message': 'Session has expired'}
    
    # Get current token
    token_data = get_current_qr_token(session_id)
    if not token_data:
        return {'status': 'error', 'message': 'Could not generate QR token'}
    
    # Calculate time until expiry
    expires_at = token_data['expires_at']
    seconds_remaining = max(0, int((expires_at - current_time).total_seconds()))
    
    return {
        'status': 'active',
        'token': token_data['token'],
        'verification_code': token_data['verification_code'],
        'expires_at': expires_at.isoformat(),
        'seconds_remaining': seconds_remaining,
        'refresh_interval': session_data.get('qr_refresh_interval', 15)
    }

def validate_attendance_request(session_id, token, verification_code, student_id):
    """
    Validate an attendance marking request
    Returns: dict with validation result
    """
    from utils.database import db
    
    # Verify the QR token
    token_result = verify_qr_token(token, verification_code)
    if not token_result['valid']:
        return {'success': False, 'error': token_result.get('error', 'Invalid QR token')}
    
    # Verify the token is for the correct session
    if token_result['session_id'] != session_id:
        return {'success': False, 'error': 'Token is for a different session'}
    
    # Check if session is active
    session_data = db.sessions.find_one({'session_id': session_id})
    if not session_data:
        return {'success': False, 'error': 'Session not found'}
    
    if not session_data.get('is_active', False):
        return {'success': False, 'error': 'Session is not active'}
    
    current_time = datetime.now()
    if session_data.get('end_time') and current_time > session_data['end_time']:
        return {'success': False, 'error': 'Session has expired'}
    
    # Check if student exists
    student = db.students.find_one({'roll_no': student_id})
    if not student:
        return {'success': False, 'error': 'Student not found'}
    
    # Check if already marked
    existing = db.attendance.find_one({
        'student_id': student_id,
        'session_id': session_id
    })
    if existing:
        return {'success': False, 'error': 'Attendance already marked for this session'}
    
    # All checks passed
    return {
        'success': True,
        'session_data': session_data,
        'student': student
    }

def log_attendance_attempt(student_id, session_id, ip_address, device_fingerprint, status, error=None):
    """Log an attendance attempt (for security auditing)"""
    from utils.database import db
    from datetime import datetime
    
    log_entry = {
        'student_id': student_id,
        'session_id': session_id,
        'ip_address': ip_address,
        'device_fingerprint': device_fingerprint,
        'status': status,
        'error': error,
        'timestamp': datetime.now()
    }
    db.attendance_attempts.insert_one(log_entry)

def get_device_fingerprint():
    """Generate a device fingerprint from request headers"""
    user_agent = request.headers.get('User-Agent', '')
    accept_language = request.headers.get('Accept-Language', '')
    accept_encoding = request.headers.get('Accept-Encoding', '')
    
    fingerprint_string = f"{user_agent}|{accept_language}|{accept_encoding}"
    
    # Hash the fingerprint
    fingerprint = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]
    return fingerprint

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
        {"url": "/attendance", "icon": "📋", "text": "Attendance Records"},
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