# app.py
# ====================================================================
# SMART ATTENDANCE SYSTEM - MAIN APPLICATION (PRODUCTION READY)
# ====================================================================

from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file, flash, g
from config import SECRET_KEY, SESSION_COOKIE_SECURE, SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE, THEME
from datetime import datetime, timedelta
from functools import wraps
import uuid
import os
import hashlib
import hmac
import logging
from logging.handlers import RotatingFileHandler
import time
import json
import base64
from io import BytesIO
import random
import string

# Initialize Flask app
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SESSION_COOKIE_SECURE'] = SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = SESSION_COOKIE_SAMESITE
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = RotatingFileHandler('logs/smart_attendance.log', maxBytes=10485760, backupCount=10)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Smart Attendance System v3.1 Startup')

# Import utilities
from utils.database import db, init_db, get_db
from utils.auth import login_required, faculty_required, student_required, admin_required

# Import helpers - with error handling for missing functions
try:
    from utils.helpers import (
        get_settings, get_college_header, get_sidebar_links, get_dashboard_stats,
        generate_secure_qr_hash, verify_qr_hash, get_client_ip, is_session_active,
        check_low_attendance, log_activity,
        # Dynamic QR functions
        generate_qr_token, verify_qr_token, get_current_qr_token,
        get_qr_status, validate_attendance_request, log_attendance_attempt,
        get_device_fingerprint
    )
except ImportError as e:
    app.logger.error(f"Import error in helpers: {e}")
    # Fallback imports
    from utils.helpers import (
        get_settings, get_college_header, get_sidebar_links, get_dashboard_stats,
        generate_secure_qr_hash, verify_qr_hash, get_client_ip, is_session_active,
        check_low_attendance, log_activity
    )
    # Define fallback functions
    def generate_qr_token(session_id, subject, duration_minutes=5):
        return {
            'token': session_id,
            'verification_code': '123456',
            'expires_at': datetime.now() + timedelta(minutes=5),
            'created_at': datetime.now()
        }
    def verify_qr_token(token, verification_code=None):
        return {'valid': True, 'session_id': token, 'subject': 'Unknown'}
    def get_current_qr_token(session_id):
        return None
    def get_qr_status(session_id):
        return {'status': 'active', 'message': 'QR system active'}
    def validate_attendance_request(session_id, token, verification_code, student_id):
        from utils.database import db
        session_data = db.sessions.find_one({'session_id': session_id})
        if not session_data:
            return {'success': False, 'error': 'Session not found'}
        student = db.students.find_one({'roll_no': student_id})
        if not student:
            return {'success': False, 'error': 'Student not found'}
        return {'success': True, 'session_data': session_data, 'student': student}
    def log_attendance_attempt(student_id, session_id, ip_address, device_fingerprint, status, error=None):
        pass
    def get_device_fingerprint():
        return hashlib.sha256(request.headers.get('User-Agent', '').encode()).hexdigest()[:32]

from utils.pdf_export import (
    export_attendance_report, export_student_report, export_all_students_report,
    export_subject_report, export_overall_report, export_all_attendance_report,
    export_faculty_report, export_students_directory
)

# Initialize database
try:
    init_db(app)
except Exception as e:
    app.logger.error(f"Database initialization error: {e}")

# ====================================================================
# HELPER FUNCTION - Generate Session ID
# ====================================================================

def generate_session_id():
    """Generate a 4-5 digit alphanumeric session ID"""
    length = random.choice([4, 5])  # Randomly choose 4 or 5 characters
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))

# ====================================================================
# MIDDLEWARE
# ====================================================================

@app.before_request
def before_request():
    """Common middleware - maintenance mode check, request timing"""
    g.start_time = time.time()
    
    # Check maintenance mode
    try:
        settings = get_settings()
        if settings.get('maintenance_mode') and not request.path.startswith('/admin'):
            return render_template('maintenance.html'), 503
    except:
        pass
    
    # Session security
    if 'user_id' in session:
        session.permanent = True

@app.after_request
def after_request(response):
    """Log request duration"""
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        app.logger.info(f"{request.method} {request.path} - {elapsed:.3f}s")
    return response

@app.context_processor
def inject_theme():
    """Inject theme colors into all templates"""
    return {
        'theme': THEME,
        'app_version': '3.1.0',
        'current_year': datetime.now().year
    }

# ====================================================================
# ROUTES
# ====================================================================

@app.route('/')
def home():
    """Home page"""
    if 'user_id' in session:
        role = session.get('role')
        if role == 'faculty':
            return redirect(url_for('faculty_dashboard'))
        elif role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    
    # Get stats with error handling to prevent crashes
    try:
        stats = get_dashboard_stats()
    except Exception as e:
        app.logger.error(f"Error getting dashboard stats: {e}")
        stats = {
            "total_students": 0,
            "total_faculty": 0,
            "total_sessions": 0,
            "total_attendance": 0,
            "today_sessions": 0,
            "active_sessions": 0,
            "recent_notices": []
        }
    
    # Get settings with error handling
    try:
        settings = get_settings()
    except Exception as e:
        app.logger.error(f"Error getting settings: {e}")
        settings = {}
    
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    
    return render_template("index.html", 
                          stats=stats, 
                          settings=settings, 
                          sidebar_links=sidebar_links, 
                          college_header=college_header)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page - supports student, faculty, admin roles"""
    error = None
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    
    if request.method == 'POST':
        user_id = request.form['user_id'].strip()
        role = request.form.get('role', 'student')
        password = request.form.get('password', '')
        ip_address = get_client_ip()
        
        if role == 'admin':
            admin = db.admins.find_one({"admin_id": user_id})
            if not admin:
                error = "❌ Invalid Admin ID"
                log_activity('admin_login_failed', user_id, ip_address, 'Invalid ID')
            elif password != admin['password']:
                error = "❌ Invalid Password"
                log_activity('admin_login_failed', user_id, ip_address, 'Invalid password')
            else:
                session.clear()
                session['user_id'] = user_id
                session['user_name'] = admin['name']
                session['role'] = 'admin'
                session['email'] = admin['email']
                log_activity('admin_login', user_id, ip_address, 'Successful login')
                return redirect(url_for('admin_dashboard'))
                
        elif role == 'faculty':
            faculty = db.faculty.find_one({"faculty_id": user_id})
            if not faculty:
                error = "❌ Invalid Faculty ID"
                log_activity('faculty_login_failed', user_id, ip_address, 'Invalid ID')
            elif password != faculty['password']:
                error = "❌ Invalid Password"
                log_activity('faculty_login_failed', user_id, ip_address, 'Invalid password')
            else:
                session.clear()
                session['user_id'] = user_id
                session['user_name'] = faculty['name']
                session['role'] = 'faculty'
                session['department'] = faculty.get('department', '')
                session['email'] = faculty.get('email', '')
                log_activity('faculty_login', user_id, ip_address, 'Successful login')
                return redirect(url_for('faculty_dashboard'))
                
        else:  # student
            student = db.students.find_one({"roll_no": user_id})
            if not student:
                error = "❌ Invalid Roll Number"
                log_activity('student_login_failed', user_id, ip_address, 'Invalid roll number')
            else:
                session.clear()
                session['user_id'] = user_id
                session['user_name'] = student['name']
                session['role'] = 'student'
                session['branch'] = student.get('branch', '')
                session['email'] = student.get('email', '')
                log_activity('student_login', user_id, ip_address, 'Successful login')
                return redirect(url_for('student_dashboard'))
    
    return render_template("login.html", error=error, sidebar_links=sidebar_links, college_header=college_header)

@app.route('/logout')
def logout():
    """Logout user"""
    if 'user_id' in session:
        log_activity('logout', session['user_id'], get_client_ip(), f"Logged out from {session.get('role', 'unknown')} role")
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# ====================================================================
# STUDENT ROUTES
# ====================================================================

@app.route('/student_dashboard')
@login_required
@student_required
def student_dashboard():
    """Student dashboard with attendance statistics and alerts"""
    student_id = session['user_id']
    
    # Get all attendance records
    attendance_records = list(db.attendance.find({"student_id": student_id}))
    all_sessions = list(db.sessions.find({}))
    
    # Calculate subject-wise statistics
    subject_stats = {}
    total_sessions_by_subject = {}
    
    for session_item in all_sessions:
        subject = session_item.get("subject")
        if subject:
            total_sessions_by_subject[subject] = total_sessions_by_subject.get(subject, 0) + 1
            if subject not in subject_stats:
                subject_stats[subject] = {"attended": 0, "total": 0, "percentage": 0}
            subject_stats[subject]["total"] = total_sessions_by_subject[subject]
    
    for record in attendance_records:
        subject = record.get("subject")
        if subject and subject in subject_stats:
            subject_stats[subject]["attended"] = subject_stats[subject].get("attended", 0) + 1
    
    for subject in subject_stats:
        total = subject_stats[subject]["total"]
        attended = subject_stats[subject]["attended"]
        subject_stats[subject]["percentage"] = round((attended / total) * 100, 2) if total > 0 else 0
    
    # Calculate overall statistics
    total_attended = len(attendance_records)
    total_sessions = len(all_sessions)
    overall_percentage = round((total_attended / total_sessions) * 100, 2) if total_sessions > 0 else 0
    
    stats = {
        "subject_stats": subject_stats,
        "total_attended": total_attended,
        "total_sessions": total_sessions,
        "overall_percentage": overall_percentage
    }
    
    # Check for low attendance alerts
    alerts = check_low_attendance(student_id)
    
    # Recent attendance records
    recent_attendance = list(db.attendance.find({"student_id": student_id}).sort("time", -1).limit(10))
    
    # Today's active sessions
    today_sessions = list(db.sessions.find({
        "end_time": {"$gt": datetime.now()},
        "is_active": True
    }).limit(5))
    
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    return render_template("student_dashboard.html",
                          name=session['user_name'],
                          stats=stats,
                          alerts=alerts,
                          recent_attendance=recent_attendance,
                          today_sessions=today_sessions,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/scan')
@login_required
@student_required
def scan():
    """QR code scanning page with dynamic QR support"""
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    return render_template("scan.html",
                          name=session['user_name'],
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

# ====================================================================
# FACULTY ROUTES
# ====================================================================

@app.route('/faculty_dashboard')
@login_required
@faculty_required
def faculty_dashboard():
    """Faculty dashboard with statistics and analytics"""
    total_students = db.students.count_documents({})
    total_sessions = db.sessions.count_documents({})
    total_attendance = db.attendance.count_documents({})
    
    subjects = ["ML", "DS", "CD", "IPR", "EOII", "OE-1"]
    subject_stats = []
    
    for subject in subjects:
        sessions_count = db.sessions.count_documents({"subject": subject})
        attended_count = db.attendance.count_documents({"subject": subject})
        percent = round((attended_count / sessions_count) * 100, 2) if sessions_count > 0 else 0
        subject_stats.append({
            "subject": subject,
            "total": sessions_count,
            "attended": attended_count,
            "percentage": percent
        })
    
    recent_sessions = list(db.sessions.find({}).sort("start_time", -1).limit(10))
    
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    return render_template("faculty_dashboard.html",
                          name=session['user_name'],
                          total_students=total_students,
                          total_sessions=total_sessions,
                          total_attendance=total_attendance,
                          subject_stats=subject_stats,
                          recent_sessions=recent_sessions,
                          now=datetime.now(),
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

# ====================================================================
# DYNAMIC QR SESSION CREATION
# ====================================================================

@app.route('/create_session', methods=['GET', 'POST'])
@login_required
@faculty_required
def create_session():
    """Create a new attendance session with dynamic QR code"""
    import qrcode
    
    settings = get_settings()
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    
    if request.method == 'POST':
        subject = request.form.get('subject')
        duration = int(request.form.get('duration', settings.get("session_duration_minutes", 5)))
        refresh_interval = int(request.form.get('refresh_interval', settings.get("qr_refresh_interval", 15)))
        
        if not subject:
            flash('Please select a subject', 'error')
            return redirect(url_for('create_session'))
        
        # Generate 4-5 digit alphanumeric session ID
        session_id = generate_session_id()
        # Ensure uniqueness
        while db.sessions.find_one({"session_id": session_id}):
            session_id = generate_session_id()
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration)
        
        # Generate initial QR token
        qr_token_data = generate_qr_token(session_id, subject, duration)
        
        # Create QR code as base64 image
        qr_code = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        # QR content includes token and verification code
        qr_content = f"{session_id}|{qr_token_data['token']}"
        qr_code.add_data(qr_content)
        qr_code.make(fit=True)
        
        img = qr_code.make_image(fill_color="#1a3a6b", back_color="white")
        
        # Convert to base64 for inline display
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # Store session data
        session_data = {
            "session_id": session_id,
            "subject": subject,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "qr_refresh_interval": refresh_interval,
            "is_active": True,
            "created_at": datetime.now(),
            "created_by": session['user_id'],
            "current_verification_code": qr_token_data['verification_code']
        }
        db.sessions.insert_one(session_data)
        
        log_activity('session_created', session['user_id'], get_client_ip(), 
                    f"Created dynamic session for {subject} (ID: {session_id})")
        
        return render_template("dynamic_session.html",
                      session_id=session_id,
                      subject=subject,
                      qr_base64=qr_base64,
                      verification_code=qr_token_data['verification_code'],
                      end_time=end_time.isoformat(),  # Keep as ISO format
                      duration=duration,
                      refresh_interval=refresh_interval,
                      sidebar_links=sidebar_links,
                      college_header=college_header,
                      settings=settings)
    
    return render_template("create_session.html",
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

# ====================================================================
# DYNAMIC QR API ENDPOINTS
# ====================================================================

@app.route('/api/qr/refresh/<session_id>', methods=['GET'])
@login_required
@faculty_required
def api_refresh_qr(session_id):
    """
    API endpoint to refresh QR code for a session
    Returns new QR code image and verification code
    """
    import qrcode
    
    # Check if session exists and is active
    session_data = db.sessions.find_one({"session_id": session_id})
    if not session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    if not session_data.get('is_active', False):
        return jsonify({'error': 'Session is not active'}), 400
    
    current_time = datetime.now()
    if session_data.get('end_time') and current_time > session_data['end_time']:
        return jsonify({'error': 'Session has expired'}), 400
    
    # Generate new QR token
    subject = session_data.get('subject', 'Unknown')
    duration = session_data.get('duration', 5)
    refresh_interval = session_data.get('qr_refresh_interval', 15)
    
    qr_token_data = generate_qr_token(session_id, subject, duration)
    
    # Update session with new verification code
    db.sessions.update_one(
        {"session_id": session_id},
        {"$set": {"current_verification_code": qr_token_data['verification_code']}}
    )
    
    # Generate QR code
    qr_code = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr_content = f"{session_id}|{qr_token_data['token']}"
    qr_code.add_data(qr_content)
    qr_code.make(fit=True)
    
    img = qr_code.make_image(fill_color="#1a3a6b", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        'qr_base64': qr_base64,
        'verification_code': qr_token_data['verification_code'],
        'expires_at': qr_token_data['expires_at'].isoformat(),
        'refresh_interval': refresh_interval
    })

@app.route('/api/qr/status/<session_id>', methods=['GET'])
@login_required
def api_qr_status(session_id):
    """Get current QR status for a session"""
    status_data = get_qr_status(session_id)
    return jsonify(status_data)

# ====================================================================
# MARK ATTENDANCE
# ====================================================================

@app.route('/mark', methods=['GET', 'POST'])
def mark():
    """Mark attendance via QR code scan with dynamic verification"""
    if 'user_id' not in session:
        flash('Please login to mark attendance', 'warning')
        return redirect(url_for('login'))
    
    student_id = session['user_id']
    ip_address = get_client_ip()
    device_fingerprint = get_device_fingerprint()
    
    # Handle QR data from scan
    if request.method == 'POST':
        qr_data = request.form.get('qr_data', '')
        verification_code = request.form.get('verification_code', '')
        session_id = request.form.get('session_id', '')
        
        # If QR data contains session_id and token
        if '|' in qr_data:
            parts = qr_data.split('|')
            if len(parts) == 2:
                session_id = parts[0]
                token = parts[1]
            else:
                flash('Invalid QR code format', 'error')
                return redirect(url_for('scan'))
        else:
            # Legacy format support
            token = qr_data
            if not session_id:
                session_id = request.args.get('session_id', '')
    
    # GET request (from legacy QR)
    else:
        session_id = request.args.get('session_id', '')
        token = request.args.get('token', '')
        qr_timestamp = request.args.get('t')
        qr_hash = request.args.get('h')
        
        # Legacy QR verification (for backward compatibility)
        if qr_timestamp and qr_hash:
            try:
                timestamp_int = int(qr_timestamp)
                current_time = int(datetime.now().timestamp())
                settings = get_settings()
                qr_expiry = settings.get("qr_expiry_seconds", 60)
                
                if current_time - timestamp_int > qr_expiry:
                    return render_template("message.html",
                                          title="QR Code Expired",
                                          message="The QR code has expired. Please scan a valid QR code.",
                                          type="error")
                
                if not verify_qr_hash(session_id, qr_timestamp, qr_hash):
                    return render_template("message.html",
                                          title="Invalid QR Code",
                                          message="Invalid QR code detected. Please scan a valid QR code.",
                                          type="error")
                
                # For legacy QR, token is session_id and verification_code is not required
                token = session_id
                verification_code = ''
                
            except Exception as e:
                app.logger.error(f"QR validation error: {e}")
                return render_template("message.html",
                                      title="Error",
                                      message="Invalid QR code format.",
                                      type="error")
    
    # Validate the attendance request
    validation_result = validate_attendance_request(session_id, token, verification_code, student_id)
    
    if not validation_result['success']:
        log_attendance_attempt(student_id, session_id, ip_address, device_fingerprint, 
                              'failed', validation_result.get('error'))
        flash(validation_result.get('error', 'Attendance marking failed'), 'error')
        return redirect(url_for('scan'))
    
    # Mark attendance
    session_data = validation_result['session_data']
    student = validation_result['student']
    
    attendance_record = {
        "student_id": student_id,
        "student_name": student['name'],
        "session_id": session_id,
        "subject": session_data['subject'],
        "time": datetime.now(),
        "ip_address": ip_address,
        "device_fingerprint": device_fingerprint,
        "user_agent": request.headers.get('User-Agent', ''),
        "verification_code_used": verification_code,
        "marked_at": datetime.now()
    }
    db.attendance.insert_one(attendance_record)
    
    log_attendance_attempt(student_id, session_id, ip_address, device_fingerprint, 'success')
    log_activity('attendance_marked', student_id, ip_address, f"Marked attendance for {session_data['subject']}")
    
    flash('Attendance marked successfully!', 'success')
    return redirect(url_for('student_dashboard'))

# ====================================================================
# STUDENT MANAGEMENT (FACULTY)
# ====================================================================

@app.route('/add_student', methods=['GET', 'POST'])
@login_required
@faculty_required
def add_student():
    """Add or manage students"""
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    message = None
    error = None
    
    if request.method == 'POST':
        roll = request.form['roll'].strip().upper()
        name = request.form['name'].strip()
        branch = request.form['branch'].strip().upper()
        email = request.form.get('email', '').strip()
        
        if not roll or not name or not branch:
            error = "❌ Please fill all required fields"
        elif db.students.find_one({"roll_no": roll}):
            error = f"❌ Student with roll number {roll} already exists"
        else:
            try:
                student_data = {
                    "roll_no": roll,
                    "name": name,
                    "branch": branch,
                    "year": 3,
                    "semester": 6,
                    "email": email,
                    "created_at": datetime.now(),
                    "created_by": session['user_id']
                }
                db.students.insert_one(student_data)
                message = f"✅ Student {name} added successfully!"
                log_activity('student_added', session['user_id'], get_client_ip(), f"Added student {roll}")
            except Exception as e:
                error = f"❌ Error adding student: {str(e)}"
    
    students = list(db.students.find({}).sort("roll_no", 1))
    
    return render_template("add_student.html",
                          students=students,
                          message=message,
                          error=error,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/faculty_bulk_upload', methods=['POST'])
@login_required
@faculty_required
def faculty_bulk_upload():
    """Bulk upload students from Excel or CSV file"""
    
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('add_student'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('add_student'))
    
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        flash('Please upload Excel (.xlsx, .xls) or CSV file only', 'error')
        return redirect(url_for('add_student'))
    
    try:
        import pandas as pd
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]
        
        roll_no_col = None
        name_col = None
        branch_col = None
        
        for col in df.columns:
            if 'roll' in col:
                roll_no_col = col
            if 'name' in col:
                name_col = col
            if 'branch' in col or 'dept' in col:
                branch_col = col
        
        if not roll_no_col:
            flash('Missing required column: roll number column', 'error')
            return redirect(url_for('add_student'))
        if not name_col:
            flash('Missing required column: name column', 'error')
            return redirect(url_for('add_student'))
        if not branch_col:
            flash('Missing required column: branch column', 'error')
            return redirect(url_for('add_student'))
        
        success_count = 0
        error_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                roll_no = str(row[roll_no_col]).strip().upper()
                name = str(row[name_col]).strip()
                branch = str(row[branch_col]).strip().upper()
                
                if not roll_no or not name or not branch or roll_no == 'NAN' or name == 'NAN':
                    continue
                
                if 'cse' in branch.lower() or 'computer' in branch.lower():
                    branch = 'CSE'
                elif 'it' in branch.lower():
                    branch = 'IT'
                elif 'ece' in branch.lower() or 'electronics' in branch.lower():
                    branch = 'ECE'
                elif 'me' in branch.lower() or 'mech' in branch.lower():
                    branch = 'ME'
                elif 'ce' in branch.lower() or 'civil' in branch.lower():
                    branch = 'CE'
                
                existing = db.students.find_one({"roll_no": roll_no})
                if existing:
                    error_count += 1
                    errors.append(f"Row {idx+2}: Roll number {roll_no} already exists")
                    continue
                
                email = ''
                if 'email' in df.columns and pd.notna(row['email']):
                    email = str(row['email']).strip()
                
                year = 3
                if 'year' in df.columns and pd.notna(row['year']):
                    try:
                        year_val = str(row['year']).strip().lower()
                        if 'rd' in year_val:
                            year = int(year_val[0])
                        else:
                            year = int(float(year_val))
                    except:
                        year = 3
                
                semester = 6
                if 'semester' in df.columns and pd.notna(row['semester']):
                    try:
                        semester = int(float(row['semester']))
                    except:
                        semester = 6
                
                student_data = {
                    "roll_no": roll_no,
                    "name": name,
                    "branch": branch,
                    "year": year,
                    "semester": semester,
                    "email": email,
                    "created_at": datetime.now(),
                    "created_by": session['user_id']
                }
                db.students.insert_one(student_data)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Row {idx+2}: {str(e)}")
        
        log_activity('faculty_bulk_upload', session['user_id'], get_client_ip(), 
                    f"Bulk uploaded {success_count} students, {error_count} errors")
        
        if success_count > 0:
            flash(f"✅ Successfully added {success_count} students!", 'success')
        if error_count > 0 and errors:
            for err in errors[:5]:
                flash(err, 'warning')
        if success_count == 0 and error_count > 0:
            flash(f"❌ No students added. {error_count} errors occurred. Check file format.", 'error')
        
    except Exception as e:
        app.logger.error(f"Bulk upload error: {str(e)}")
        flash(f"Error reading file: {str(e)}", 'error')
    
    return redirect(url_for('add_student'))

@app.route('/delete_student/<roll_no>')
@login_required
@faculty_required
def delete_student(roll_no):
    """Delete a student"""
    db.attendance.delete_many({"student_id": roll_no})
    db.students.delete_one({"roll_no": roll_no})
    log_activity('student_deleted', session['user_id'], get_client_ip(), f"Deleted student {roll_no}")
    flash(f'Student {roll_no} deleted successfully', 'success')
    return redirect(url_for('add_student'))

# ====================================================================
# ATTENDANCE & REPORTS
# ====================================================================

@app.route('/attendance')
@login_required
def attendance():
    """View attendance records"""
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    if session.get('role') == 'student':
        records = list(db.attendance.find({"student_id": session['user_id']}).sort("time", -1))
    else:
        records = list(db.attendance.find({}).sort("time", -1))
    
    enriched_records = []
    for record in records:
        student = db.students.find_one({"roll_no": record['student_id']})
        enriched_records.append({
            "roll_no": record['student_id'],
            "name": student['name'] if student else 'Unknown',
            "branch": student['branch'] if student else 'Unknown',
            "session_id": record['session_id'],
            "subject": record['subject'],
            "time": record['time'].strftime('%Y-%m-%d %H:%M:%S') if record['time'] else 'N/A',
            "ip_address": record.get('ip_address', 'N/A')
        })
    
    return render_template("attendance.html",
                          data=enriched_records,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/students_report', methods=['GET', 'POST'])
@login_required
@faculty_required
def students_report():
    """Student performance report"""
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    students_list = list(db.students.find({}))
    all_sessions = list(db.sessions.find({}))
    
    total_sessions_dict = {}
    for session_item in all_sessions:
        subject = session_item['subject']
        total_sessions_dict[subject] = total_sessions_dict.get(subject, 0) + 1
    
    report_data = []
    for student in students_list:
        student_attendance = []
        total_attended_all = 0
        total_possible_all = 0
        
        for subject, total in total_sessions_dict.items():
            attendance_count = db.attendance.count_documents({
                "student_id": student['roll_no'],
                "subject": subject
            })
            percent = round((attendance_count / total) * 100, 2) if total > 0 else 0
            student_attendance.append({
                "subject": subject,
                "attended": attendance_count,
                "total": total,
                "percentage": percent
            })
            total_attended_all += attendance_count
            total_possible_all += total
        
        overall_percent = round((total_attended_all / total_possible_all) * 100, 2) if total_possible_all > 0 else 0
        
        report_data.append({
            "roll_no": student['roll_no'],
            "name": student['name'],
            "branch": student['branch'],
            "overall_percentage": overall_percent,
            "subjects": student_attendance
        })
    
    return render_template("students_report.html",
                          data=report_data,
                          total_sessions_dict=total_sessions_dict,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

# ====================================================================
# PDF EXPORT ROUTES
# ====================================================================

@app.route('/export_report/<session_id>')
@login_required
def export_attendance(session_id):
    """Export session attendance as PDF"""
    if session.get('role') not in ['faculty', 'admin']:
        flash('Access denied', 'error')
        return redirect(url_for('attendance'))
    
    return export_attendance_report(session_id, db)

@app.route('/export_student_pdf/<roll_no>')
@login_required
def export_student(roll_no):
    """Export student individual report as PDF"""
    return export_student_report(roll_no, db)

@app.route('/export_all_students_pdf')
@login_required
def export_all_students():
    """Export all students report as PDF"""
    if session.get('role') not in ['faculty', 'admin']:
        flash('Access denied', 'error')
        return redirect(url_for('attendance'))
    
    return export_all_students_report(db)

@app.route('/export_subject_pdf/<subject>')
@login_required
def export_subject(subject):
    """Export subject-wise report as PDF"""
    if session.get('role') not in ['faculty', 'admin']:
        flash('Access denied', 'error')
        return redirect(url_for('attendance'))
    
    return export_subject_report(subject, db)

@app.route('/export_overall_pdf')
@login_required
def export_overall():
    """Export overall report as PDF"""
    if session.get('role') not in ['faculty', 'admin']:
        flash('Access denied', 'error')
        return redirect(url_for('attendance'))
    
    return export_overall_report(db)

@app.route('/export_all_attendance_pdf')
@login_required
def export_all_attendance():
    """Export all attendance records as PDF"""
    return export_all_attendance_report(session, db)

@app.route('/export_faculty_pdf')
@login_required
@admin_required
def export_faculty():
    """Export faculty list as PDF"""
    return export_faculty_report(db)

@app.route('/export_students_pdf')
@login_required
@admin_required
def export_students():
    """Export students directory as PDF"""
    return export_students_directory(db)

# ====================================================================
# ADMIN ROUTES
# ====================================================================

@app.route('/admin_dashboard')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    stats = get_dashboard_stats()
    recent_sessions = list(db.sessions.find({}).sort("start_time", -1).limit(5))
    all_notices = list(db.notices.find({}).sort("created_at", -1))
    recent_logs = list(db.logs.find({}).sort("timestamp", -1).limit(10))
    
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    return render_template("admin_dashboard.html",
                          name=session['user_name'],
                          stats=stats,
                          recent_sessions=recent_sessions,
                          notices=all_notices,
                          recent_logs=recent_logs,
                          now=datetime.now(),
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/admin/manage_faculty')
@login_required
@admin_required
def admin_manage_faculty():
    """Manage faculty members"""
    faculties = list(db.faculty.find({}).sort("faculty_id", 1))
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    return render_template("admin_manage_faculty.html",
                          faculties=faculties,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/admin/add_faculty', methods=['POST'])
@login_required
@admin_required
def admin_add_faculty():
    """Add new faculty member"""
    faculty_data = {
        "faculty_id": request.form['faculty_id'].strip().upper(),
        "name": request.form['name'].strip(),
        "email": request.form['email'].strip(),
        "department": request.form['department'].strip(),
        "password": request.form['password'],
        "created_at": datetime.now(),
        "created_by": session['user_id']
    }
    
    try:
        db.faculty.insert_one(faculty_data)
        log_activity('faculty_added', session['user_id'], get_client_ip(), f"Added faculty {faculty_data['faculty_id']}")
        flash(f"Faculty {faculty_data['name']} added successfully", 'success')
    except Exception as e:
        flash(f"Error: Faculty ID may already exist", 'error')
    
    return redirect(url_for('admin_manage_faculty'))

@app.route('/admin/edit_faculty/<faculty_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_faculty(faculty_id):
    """Edit faculty information"""
    faculty = db.faculty.find_one({"faculty_id": faculty_id})
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    if request.method == 'POST':
        updated_data = {
            "name": request.form['name'].strip(),
            "email": request.form['email'].strip(),
            "department": request.form['department'].strip()
        }
        if request.form.get('password'):
            updated_data["password"] = request.form['password']
        
        db.faculty.update_one({"faculty_id": faculty_id}, {"$set": updated_data})
        log_activity('faculty_edited', session['user_id'], get_client_ip(), f"Edited faculty {faculty_id}")
        flash('Faculty updated successfully', 'success')
        return redirect(url_for('admin_manage_faculty'))
    
    return render_template("admin_edit_faculty.html",
                          faculty=faculty,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/admin/delete_faculty/<faculty_id>')
@login_required
@admin_required
def admin_delete_faculty(faculty_id):
    """Delete faculty member"""
    db.faculty.delete_one({"faculty_id": faculty_id})
    log_activity('faculty_deleted', session['user_id'], get_client_ip(), f"Deleted faculty {faculty_id}")
    flash('Faculty deleted successfully', 'success')
    return redirect(url_for('admin_manage_faculty'))

@app.route('/admin/manage_students')
@login_required
@admin_required
def admin_manage_students():
    """Manage students"""
    students_list = list(db.students.find({}).sort("roll_no", 1))
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    return render_template("admin_manage_students.html",
                          students=students_list,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/admin/add_student', methods=['POST'])
@login_required
@admin_required
def admin_add_student():
    """Add new student"""
    student_data = {
        "roll_no": request.form['roll_no'].strip().upper(),
        "name": request.form['name'].strip(),
        "branch": request.form['branch'].strip().upper(),
        "year": int(request.form.get('year', 3)),
        "semester": int(request.form.get('semester', 6)),
        "email": request.form.get('email', '').strip(),
        "created_at": datetime.now(),
        "created_by": session['user_id']
    }
    
    try:
        db.students.insert_one(student_data)
        log_activity('student_added', session['user_id'], get_client_ip(), f"Added student {student_data['roll_no']}")
        flash(f"Student {student_data['name']} added successfully", 'success')
    except Exception as e:
        flash(f"Error: Student with roll number {student_data['roll_no']} may already exist", 'error')
    
    return redirect(url_for('admin_manage_students'))

@app.route('/admin/edit_student/<roll_no>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_student(roll_no):
    """Edit student information"""
    student = db.students.find_one({"roll_no": roll_no})
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    if request.method == 'POST':
        updated_data = {
            "name": request.form['name'].strip(),
            "branch": request.form['branch'].strip().upper(),
            "email": request.form.get('email', '').strip(),
            "year": int(request.form.get('year', 3)),
            "semester": int(request.form.get('semester', 6))
        }
        
        db.students.update_one({"roll_no": roll_no}, {"$set": updated_data})
        log_activity('student_edited', session['user_id'], get_client_ip(), f"Edited student {roll_no}")
        flash('Student updated successfully', 'success')
        return redirect(url_for('admin_manage_students'))
    
    return render_template("admin_edit_student.html",
                          student=student,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/admin/delete_student/<roll_no>')
@login_required
@admin_required
def admin_delete_student(roll_no):
    """Delete student"""
    db.attendance.delete_many({"student_id": roll_no})
    db.students.delete_one({"roll_no": roll_no})
    log_activity('student_deleted', session['user_id'], get_client_ip(), f"Deleted student {roll_no}")
    flash(f'Student {roll_no} deleted successfully', 'success')
    return redirect(url_for('admin_manage_students'))

@app.route('/admin/manage_sessions')
@login_required
@admin_required
def admin_manage_sessions():
    """Manage all sessions"""
    sessions_list = list(db.sessions.find({}).sort("start_time", -1))
    
    for session_item in sessions_list:
        session_item['attendance_count'] = db.attendance.count_documents({
            "session_id": session_item['session_id']
        })
    
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    return render_template("admin_manage_sessions.html",
                          sessions=sessions_list,
                          now=datetime.now(),
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/admin/view_session/<session_id>')
@login_required
@admin_required
def admin_view_session(session_id):
    """View session details"""
    session_data = db.sessions.find_one({"session_id": session_id})
    records = list(db.attendance.find({"session_id": session_id}).sort("time", 1))
    
    for record in records:
        student = db.students.find_one({"roll_no": record['student_id']})
        record['name'] = student['name'] if student else 'Unknown'
        record['branch'] = student['branch'] if student else 'Unknown'
    
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    return render_template("admin_view_session.html",
                          session=session_data,
                          records=records,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/admin/delete_session/<session_id>')
@login_required
@admin_required
def admin_delete_session(session_id):
    """Delete session"""
    db.attendance.delete_many({"session_id": session_id})
    db.sessions.delete_one({"session_id": session_id})
    db.qr_tokens.delete_many({"session_id": session_id})
    log_activity('session_deleted', session['user_id'], get_client_ip(), f"Deleted session {session_id}")
    flash('Session deleted successfully', 'success')
    return redirect(url_for('admin_manage_sessions'))

@app.route('/admin/system_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_system_settings():
    """System settings configuration"""
    message = None
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    if request.method == 'POST':
        updated_settings = {
            "attendance_threshold": int(request.form.get('attendance_threshold', 75)),
            "qr_expiry_seconds": int(request.form.get('qr_expiry', 60)),
            "session_duration_minutes": int(request.form.get('session_duration', 5)),
            "college_name": request.form.get('college_name', settings.get('college_name', '')),
            "college_location": request.form.get('college_location', settings.get('college_location', '')),
            "college_header": request.form.get('college_header', settings.get('college_header', '')),
            "academic_year": request.form.get('academic_year', settings.get('academic_year', '2024-25')),
            "maintenance_mode": request.form.get('maintenance_mode') == 'on',
            "enable_location_tracking": request.form.get('enable_location_tracking') == 'on',
            "enable_ip_tracking": request.form.get('enable_ip_tracking') == 'on',
            "max_login_attempts": int(request.form.get('max_login_attempts', 5)),
            "session_timeout_minutes": int(request.form.get('session_timeout_minutes', 30)),
            "qr_refresh_interval": int(request.form.get('qr_refresh_interval', 15)),
            "verification_code_length": int(request.form.get('verification_code_length', 6)),
            "enable_device_fingerprinting": request.form.get('enable_device_fingerprinting') == 'on',
            "enable_verification_code": request.form.get('enable_verification_code') == 'on'
        }
        
        db.settings.update_one({}, {"$set": updated_settings}, upsert=True)
        message = "✅ Settings updated successfully!"
        log_activity('settings_updated', session['user_id'], get_client_ip(), "System settings updated")
    
    settings = get_settings()
    
    return render_template("admin_system_settings.html",
                          settings=settings,
                          message=message,
                          sidebar_links=sidebar_links,
                          college_header=college_header)

@app.route('/admin/change_password', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_change_password():
    """Change admin password"""
    message = None
    error = None
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        admin = db.admins.find_one({"admin_id": session['user_id']})
        
        if current_password != admin['password']:
            error = "❌ Current password is incorrect"
        elif new_password != confirm_password:
            error = "❌ New passwords do not match"
        elif len(new_password) < 6:
            error = "❌ Password must be at least 6 characters"
        else:
            db.admins.update_one({"admin_id": session['user_id']}, {"$set": {"password": new_password}})
            message = "✅ Password changed successfully!"
            log_activity('password_changed', session['user_id'], get_client_ip(), "Admin password changed")
    
    return render_template("admin_change_password.html",
                          message=message,
                          error=error,
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/admin/add_notice', methods=['POST'])
@login_required
@admin_required
def admin_add_notice():
    """Add new notice"""
    notice = {
        "title": request.form.get('title'),
        "content": request.form.get('content'),
        "author": session['user_name'],
        "created_at": datetime.now(),
        "is_active": True,
        "priority": request.form.get('priority', 'normal')
    }
    db.notices.insert_one(notice)
    log_activity('notice_added', session['user_id'], get_client_ip(), f"Added notice: {notice['title']}")
    flash('Notice added successfully', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_notice/<notice_id>')
@login_required
@admin_required
def admin_delete_notice(notice_id):
    """Delete notice"""
    from bson.objectid import ObjectId
    db.notices.delete_one({"_id": ObjectId(notice_id)})
    flash('Notice deleted successfully', 'success')
    return redirect(url_for('admin_dashboard'))

# ====================================================================
# ADMIN BULK UPLOAD
# ====================================================================

import pandas as pd

@app.route('/admin/bulk_upload_students', methods=['POST'])
@login_required
@admin_required
def admin_bulk_upload_students():
    """Bulk upload students from Excel or CSV file"""
    
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('admin_manage_students'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin_manage_students'))
    
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        flash('Please upload Excel (.xlsx, .xls) or CSV file only', 'error')
        return redirect(url_for('admin_manage_students'))
    
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]
        
        roll_no_col = None
        name_col = None
        branch_col = None
        
        for col in df.columns:
            if 'roll' in col:
                roll_no_col = col
            if 'name' in col:
                name_col = col
            if 'branch' in col or 'dept' in col:
                branch_col = col
        
        if not roll_no_col:
            flash('Missing required column: roll number column', 'error')
            return redirect(url_for('admin_manage_students'))
        if not name_col:
            flash('Missing required column: name column', 'error')
            return redirect(url_for('admin_manage_students'))
        if not branch_col:
            flash('Missing required column: branch column', 'error')
            return redirect(url_for('admin_manage_students'))
        
        success_count = 0
        error_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                roll_no = str(row[roll_no_col]).strip().upper()
                name = str(row[name_col]).strip()
                branch = str(row[branch_col]).strip().upper()
                
                if not roll_no or not name or not branch or roll_no == 'NAN' or name == 'NAN':
                    continue
                
                if 'cse' in branch.lower() or 'computer' in branch.lower():
                    branch = 'CSE'
                elif 'it' in branch.lower():
                    branch = 'IT'
                elif 'ece' in branch.lower() or 'electronics' in branch.lower():
                    branch = 'ECE'
                elif 'me' in branch.lower() or 'mech' in branch.lower():
                    branch = 'ME'
                elif 'ce' in branch.lower() or 'civil' in branch.lower():
                    branch = 'CE'
                
                existing = db.students.find_one({"roll_no": roll_no})
                if existing:
                    error_count += 1
                    errors.append(f"Row {idx+2}: Roll number {roll_no} already exists")
                    continue
                
                email = ''
                if 'email' in df.columns and pd.notna(row['email']):
                    email = str(row['email']).strip()
                
                year = 3
                if 'year' in df.columns and pd.notna(row['year']):
                    try:
                        year_val = str(row['year']).strip().lower()
                        if 'rd' in year_val:
                            year = int(year_val[0])
                        else:
                            year = int(float(year_val))
                    except:
                        year = 3
                
                semester = 6
                if 'semester' in df.columns and pd.notna(row['semester']):
                    try:
                        semester = int(float(row['semester']))
                    except:
                        semester = 6
                
                student_data = {
                    "roll_no": roll_no,
                    "name": name,
                    "branch": branch,
                    "year": year,
                    "semester": semester,
                    "email": email,
                    "created_at": datetime.now(),
                    "created_by": session['user_id']
                }
                db.students.insert_one(student_data)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Row {idx+2}: {str(e)}")
        
        log_activity('admin_bulk_upload', session['user_id'], get_client_ip(), 
                    f"Bulk uploaded {success_count} students, {error_count} errors")
        
        if success_count > 0:
            flash(f"✅ Successfully added {success_count} students!", 'success')
        if error_count > 0 and errors:
            for err in errors[:5]:
                flash(err, 'warning')
        if success_count == 0 and error_count > 0:
            flash(f"❌ No students added. {error_count} errors occurred. Check file format.", 'error')
        
    except Exception as e:
        app.logger.error(f"Bulk upload error: {str(e)}")
        flash(f"Error reading file: {str(e)}", 'error')
    
    return redirect(url_for('admin_manage_students'))

# ====================================================================
# STATIC PAGES
# ====================================================================

@app.route('/subject_details')
def subject_details():
    """Subject details page"""
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    return render_template("subject_details.html",
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

@app.route('/about')
def about():
    """About page"""
    sidebar_links = get_sidebar_links()
    college_header = get_college_header()
    settings = get_settings()
    return render_template("about.html",
                          sidebar_links=sidebar_links,
                          college_header=college_header,
                          settings=settings)

# ====================================================================
# RUN APPLICATION
# ====================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    
    print("\n" + "=" * 60)
    print("🚀 SMART ATTENDANCE SYSTEM v3.1")
    print("=" * 60)
    print("📊 Database: " + os.getenv('DB_NAME', 'smart_attendance'))
    print("🌐 Server running on port: " + str(port))
    print("\n👥 Login Credentials:")
    print("   Admin:   ADMIN001 / admin123")
    print("   Faculty: FAC001 / faculty123")
    print("   Student: CS001 (no password)")
    print("\n✨ NEW FEATURES:")
    print("   • Dynamic QR Code (refreshes every 10-15s)")
    print("   • Live Verification Code")
    print("   • Device Fingerprinting")
    print("   • Enhanced Security")
    print("\n" + "=" * 60 + "\n")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)