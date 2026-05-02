# ====================================================================
# SMART ATTENDANCE SYSTEM - MAIN APPLICATION (app.py)
# ====================================================================

from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_file
from config import MONGO_URI, DB_NAME, COLLECTIONS, DEFAULT_SETTINGS
from datetime import datetime, timedelta
import uuid
import qrcode
import os
import hashlib
import hmac
from functools import wraps
from io import BytesIO
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "smart_attendance_secret_key_2024"

# ====================================================================
# MONGODB CONNECTION
# ====================================================================
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print(f"❌ MongoDB Connection Failed: {e}")

db = client[DB_NAME]

# Collections
students_col = db[COLLECTIONS["students"]]
faculty_col = db[COLLECTIONS["faculty"]]
admins_col = db[COLLECTIONS["admins"]]
sessions_col = db[COLLECTIONS["sessions"]]
attendance_col = db[COLLECTIONS["attendance"]]
notices_col = db[COLLECTIONS["notices"]]
settings_col = db[COLLECTIONS["settings"]]

# Create indexes
try:
    students_col.create_index("roll_no", unique=True)
    faculty_col.create_index("faculty_id", unique=True)
    admins_col.create_index("admin_id", unique=True)
    sessions_col.create_index("session_id", unique=True)
    attendance_col.create_index([("student_id", 1), ("session_id", 1)], unique=True)
    print("✅ Database indexes created")
except Exception as e:
    print(f"Index creation warning: {e}")

# ====================================================================
# INITIALIZE DATABASE
# ====================================================================
def init_db():
    if settings_col.count_documents({}) == 0:
        settings_col.insert_one(DEFAULT_SETTINGS)
        print("✓ Settings initialized")
    
    if admins_col.count_documents({}) == 0:
        admins_col.insert_one({
            "admin_id": "ADMIN001", "name": "System Administrator", "email": "admin@pbcoe.edu",
            "password": "admin123", "role": "super_admin", "created_at": datetime.now()
        })
        print("✓ Admin account created: ADMIN001 / admin123")
    
    if faculty_col.count_documents({}) == 0:
        faculty_data = [
            {"faculty_id": "FAC001", "name": "Prof. Rahul Khadse", "email": "khadse@pbcoe.edu", "department": "CSE", "password": "faculty123", "created_at": datetime.now()},
            {"faculty_id": "FAC002", "name": "Prof. Swati Tikle", "email": "tikle@pbcoe.edu", "department": "CSE", "password": "faculty123", "created_at": datetime.now()},
            {"faculty_id": "FAC003", "name": "Prof. Priyanka Katore", "email": "katore@pbcoe.edu", "department": "CSE", "password": "faculty123", "created_at": datetime.now()},
        ]
        faculty_col.insert_many(faculty_data)
        print("✓ Faculty accounts created (FAC001, FAC002, FAC003 / password: faculty123)")
    
    if students_col.count_documents({}) == 0:
        student_data = [
            {"roll_no": "CS001", "name": "Alice Johnson", "branch": "CSE", "year": 3, "semester": 6, "email": "alice@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CS002", "name": "Bob Williams", "branch": "CSE", "year": 3, "semester": 6, "email": "bob@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CS003", "name": "Charlie Brown", "branch": "CSE", "year": 3, "semester": 6, "email": "charlie@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CS004", "name": "Diana Prince", "branch": "CSE", "year": 3, "semester": 6, "email": "diana@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CS005", "name": "Evan Parker", "branch": "CSE", "year": 3, "semester": 6, "email": "evan@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "ME001", "name": "John Mechanical", "branch": "ME", "year": 3, "semester": 6, "email": "john@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "CE001", "name": "Sarah Civil", "branch": "CE", "year": 3, "semester": 6, "email": "sarah@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "EC001", "name": "David Electronics", "branch": "ECE", "year": 3, "semester": 6, "email": "david@pbcoe.edu", "created_at": datetime.now()},
            {"roll_no": "IT001", "name": "Emma IT", "branch": "IT", "year": 3, "semester": 6, "email": "emma@pbcoe.edu", "created_at": datetime.now()},
        ]
        students_col.insert_many(student_data)
        print("✓ Student accounts created")
    
    if notices_col.count_documents({}) == 0:
        notices_col.insert_one({
            "title": "Welcome to Smart Attendance System", "content": "All students are requested to mark their attendance using the QR code system.",
            "author": "Admin", "created_at": datetime.now(), "is_active": True
        })
        print("✓ Sample notices created")
    
    print("✓ Database initialization complete!")

init_db()

# ====================================================================
# HELPER FUNCTIONS
# ====================================================================

def get_settings():
    settings = settings_col.find_one({})
    return settings if settings else DEFAULT_SETTINGS

def generate_secure_qr_hash(session_id, timestamp):
    secret = app.secret_key.encode()
    message = f"{session_id}:{timestamp}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:16]

def verify_qr_hash(session_id, timestamp, provided_hash):
    expected_hash = generate_secure_qr_hash(session_id, timestamp)
    return hmac.compare_digest(expected_hash, provided_hash)

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]
    else:
        ip = request.remote_addr
    return ip

def is_session_active(end_time):
    if not end_time:
        return True
    return datetime.now() <= end_time

def get_dashboard_stats():
    total_students = students_col.count_documents({})
    total_faculty = faculty_col.count_documents({})
    total_sessions = sessions_col.count_documents({})
    total_attendance = attendance_col.count_documents({})
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sessions = sessions_col.count_documents({"created_at": {"$gte": today_start}})
    active_sessions = sessions_col.count_documents({"end_time": {"$gt": datetime.now()}, "is_active": True})
    recent_notices = list(notices_col.find({}).sort("created_at", -1).limit(5))
    
    return {
        "total_students": total_students, "total_faculty": total_faculty,
        "total_sessions": total_sessions, "total_attendance": total_attendance,
        "today_sessions": today_sessions, "active_sessions": active_sessions,
        "recent_notices": recent_notices
    }

def check_low_attendance(student_id):
    settings = get_settings()
    threshold = settings.get("attendance_threshold", 75)
    attendance_records = list(attendance_col.find({"student_id": student_id}))
    all_sessions = list(sessions_col.find({}))
    
    subject_stats = {}
    for session_item in all_sessions:
        subject = session_item.get("subject")
        if subject not in subject_stats:
            subject_stats[subject] = {"total": 0, "attended": 0}
        subject_stats[subject]["total"] += 1
    
    for record in attendance_records:
        subject = record.get("subject")
        if subject in subject_stats:
            subject_stats[subject]["attended"] += 1
    
    alerts = []
    for subject, data in subject_stats.items():
        percentage = (data["attended"] / data["total"]) * 100 if data["total"] > 0 else 0
        if percentage < threshold:
            alerts.append({"subject": subject, "percentage": round(percentage, 2), "required": threshold, "shortage": round(threshold - percentage, 2)})
    return alerts

# ====================================================================
# DECORATORS
# ====================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def faculty_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'faculty':
            return "Access Denied: Faculty only", 403
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'student':
            return "Access Denied: Students only", 403
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return "Access Denied: Admin only", 403
        return f(*args, **kwargs)
    return decorated_function

# ====================================================================
# ROUTES
# ====================================================================

@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('role') == 'faculty':
            return redirect(url_for('faculty_dashboard'))
        elif session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    stats = get_dashboard_stats()
    settings = get_settings()
    return render_template("index.html", stats=stats, settings=settings)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user_id = request.form['user_id'].strip()
        role = request.form.get('role', 'student')
        password = request.form.get('password', '')
        
        if role == 'admin':
            admin = admins_col.find_one({"admin_id": user_id})
            if not admin:
                error = "❌ Invalid Admin ID"
            elif password != admin['password']:
                error = "❌ Invalid Password"
            else:
                session['user_id'] = user_id
                session['user_name'] = admin['name']
                session['role'] = 'admin'
                return redirect(url_for('admin_dashboard'))
        elif role == 'faculty':
            faculty = faculty_col.find_one({"faculty_id": user_id})
            if not faculty:
                error = "❌ Invalid Faculty ID"
            elif password != faculty['password']:
                error = "❌ Invalid Password"
            else:
                session['user_id'] = user_id
                session['user_name'] = faculty['name']
                session['role'] = 'faculty'
                return redirect(url_for('faculty_dashboard'))
        else:
            student = students_col.find_one({"roll_no": user_id})
            if not student:
                error = "❌ Invalid Roll Number"
            else:
                session['user_id'] = user_id
                session['user_name'] = student['name']
                session['role'] = 'student'
                return redirect(url_for('student_dashboard'))
    return render_template("login.html", error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ====================================================================
# STUDENT ROUTES
# ====================================================================

@app.route('/student_dashboard')
@login_required
@student_required
def student_dashboard():
    student_id = session['user_id']
    attendance_records = list(attendance_col.find({"student_id": student_id}))
    all_sessions = list(sessions_col.find({}))
    
    subject_stats = {}
    for session_item in all_sessions:
        subject = session_item.get("subject")
        if subject not in subject_stats:
            subject_stats[subject] = {"total": 0, "attended": 0}
        subject_stats[subject]["total"] += 1
    
    for record in attendance_records:
        subject = record.get("subject")
        if subject in subject_stats:
            subject_stats[subject]["attended"] += 1
    
    for subject, data in subject_stats.items():
        data["percentage"] = round((data["attended"] / data["total"]) * 100, 2) if data["total"] > 0 else 0
    
    total_attended = len(attendance_records)
    total_sessions = len(all_sessions)
    overall_percentage = round((total_attended / total_sessions) * 100, 2) if total_sessions > 0 else 0
    
    stats = {"subject_stats": subject_stats, "total_attended": total_attended, "total_sessions": total_sessions, "overall_percentage": overall_percentage}
    alerts = check_low_attendance(student_id)
    recent_attendance = list(attendance_col.find({"student_id": student_id}).sort("time", -1).limit(10))
    today_sessions = list(sessions_col.find({"end_time": {"$gt": datetime.now()}, "is_active": True}).limit(5))
    
    return render_template("student_dashboard.html", name=session['user_name'], stats=stats, alerts=alerts, recent_attendance=recent_attendance, today_sessions=today_sessions)

@app.route('/scan')
@login_required
@student_required
def scan():
    return render_template("scan.html", name=session['user_name'])

# ====================================================================
# FACULTY ROUTES
# ====================================================================

@app.route('/faculty_dashboard')
@login_required
@faculty_required
def faculty_dashboard():
    total_students = students_col.count_documents({})
    total_sessions = sessions_col.count_documents({})
    total_attendance = attendance_col.count_documents({})
    
    subjects = ["ML", "DS", "CD", "IPR", "EOII", "OE-1"]
    subject_stats = []
    for subject in subjects:
        sessions_count = sessions_col.count_documents({"subject": subject})
        attended_count = attendance_col.count_documents({"subject": subject})
        percent = round((attended_count / sessions_count) * 100, 2) if sessions_count > 0 else 0
        subject_stats.append({"subject": subject, "total": sessions_count, "attended": attended_count, "percentage": percent})
    
    recent_sessions = list(sessions_col.find({}).sort("start_time", -1).limit(10))
    return render_template("faculty_dashboard.html", name=session['user_name'], total_students=total_students, 
                          total_sessions=total_sessions, total_attendance=total_attendance, subject_stats=subject_stats, 
                          recent_sessions=recent_sessions, now=datetime.now())

@app.route('/create_session', methods=['GET', 'POST'])
@login_required
@faculty_required
def create_session():
    settings = get_settings()
    if request.method == 'POST':
        subject = request.form.get('subject')
        duration = int(request.form.get('duration', settings.get("session_duration_minutes", 5)))
        if not subject:
            return "Please select a subject"
        
        session_id = str(uuid.uuid4())[:6]
        timestamp = int(datetime.now().timestamp())
        qr_hash = generate_secure_qr_hash(session_id, timestamp)
        
        qr_folder = os.path.join("static", "qr_codes")
        os.makedirs(qr_folder, exist_ok=True)
        
        # ✅ FIXED - Use environment variable for base URL
        # Get the base URL from environment or use request.host_url as fallback
        base_url = os.environ.get('BASE_URL', request.host_url)
        # Ensure base_url doesn't end with /
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        
        # Create the full URL for QR code
        url = f"{base_url}/mark?session_id={session_id}&t={timestamp}&h={qr_hash}"
        
        qr_filename = f"qr_{session_id}.png"
        qr_path = os.path.join(qr_folder, qr_filename)
        img = qrcode.make(url)
        img.save(qr_path)
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration)
        
        session_data = {"session_id": session_id, "subject": subject, "start_time": start_time, "end_time": end_time,
                       "duration": duration, "qr_hash": qr_hash, "qr_filename": qr_filename, "is_active": True,
                       "created_at": datetime.now(), "created_by": session['user_id']}
        sessions_col.insert_one(session_data)
        return render_template("session.html", session_id=session_id, subject=subject, qr=qr_filename, end_time=end_time.isoformat())
    return render_template("create_session.html")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration)
        
        session_data = {"session_id": session_id, "subject": subject, "start_time": start_time, "end_time": end_time,
                       "duration": duration, "qr_hash": qr_hash, "qr_filename": qr_filename, "is_active": True,
                       "created_at": datetime.now(), "created_by": session['user_id']}
        sessions_col.insert_one(session_data)
        return render_template("session.html", session_id=session_id, subject=subject, qr=qr_filename, end_time=end_time.isoformat())
    return render_template("create_session.html")

# ====================================================================
# ADD STUDENT (FACULTY) - FIXED
# ====================================================================
@app.route('/add_student', methods=['GET', 'POST'])
@login_required
@faculty_required
def add_student():
    if request.method == 'POST':
        roll = request.form['roll']
        name = request.form['name']
        branch = request.form['branch']
        
        try:
            student_data = {
                "roll_no": roll,
                "name": name,
                "branch": branch,
                "year": 3,
                "semester": 6,
                "email": "",
                "created_at": datetime.now()
            }
            students_col.insert_one(student_data)
        except Exception as e:
            return "Student already exists or error occurred"
    
    # Get all students to display in the list
    students = list(students_col.find({}).sort("roll_no", 1))
    
    return render_template("add_student.html", students=students)

@app.route('/delete_student/<roll_no>')
@login_required
@faculty_required
def delete_student(roll_no):
    attendance_col.delete_many({"student_id": roll_no})
    students_col.delete_one({"roll_no": roll_no})
    return redirect(url_for('add_student'))

# ====================================================================
# MARK ATTENDANCE
# ====================================================================

@app.route('/mark', methods=['GET', 'POST'])
def mark():
    session_id = request.args.get('session_id') or request.form.get('session_id')
    qr_timestamp = request.args.get('t')
    qr_hash = request.args.get('h')
    
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    student_id = session['user_id']
    
    if qr_timestamp and qr_hash:
        try:
            timestamp_int = int(qr_timestamp)
            current_time = int(datetime.now().timestamp())
            settings = get_settings()
            qr_expiry = settings.get("qr_expiry_seconds", 60)
            if current_time - timestamp_int > qr_expiry:
                return "❌ QR Code Expired. Please scan again."
            if not verify_qr_hash(session_id, qr_timestamp, qr_hash):
                return "❌ Invalid QR Code. Tampering detected."
        except:
            return "❌ Invalid QR Code"
    
    session_data = sessions_col.find_one({"session_id": session_id})
    if not session_data:
        return "❌ Invalid Session"
    if not is_session_active(session_data['end_time']):
        sessions_col.update_one({"session_id": session_id}, {"$set": {"is_active": False}})
        return "❌ Session Expired"
    
    existing = attendance_col.find_one({"student_id": student_id, "session_id": session_id})
    if existing:
        return "❌ Already Marked"
    
    client_ip = get_client_ip()
    attendance_record = {"student_id": student_id, "session_id": session_id, "subject": session_data['subject'],
                        "time": datetime.now(), "ip_address": client_ip}
    attendance_col.insert_one(attendance_record)
    return "<h2 style='color:green;text-align:center;margin-top:50px;'>✅ Attendance Marked Successfully!</h2>"

# ====================================================================
# ATTENDANCE & REPORTS
# ====================================================================

@app.route('/attendance')
@login_required
def attendance():
    if session.get('role') == 'student':
        records = list(attendance_col.find({"student_id": session['user_id']}).sort("time", -1))
    else:
        records = list(attendance_col.find({}).sort("time", -1))
    
    enriched_records = []
    for record in records:
        student = students_col.find_one({"roll_no": record['student_id']})
        enriched_records.append({"roll_no": record['student_id'], "name": student['name'] if student else 'Unknown',
                                "branch": student['branch'] if student else 'Unknown', "session_id": record['session_id'],
                                "subject": record['subject'], "time": record['time'].strftime('%Y-%m-%d %H:%M:%S') if record['time'] else 'N/A'})
    return render_template("attendance.html", data=enriched_records)

@app.route('/students_report', methods=['GET', 'POST'])
@login_required
@faculty_required
def students_report():
    students_list = list(students_col.find({}))
    all_sessions = list(sessions_col.find({}))
    
    total_sessions_dict = {}
    for session in all_sessions:
        subject = session['subject']
        total_sessions_dict[subject] = total_sessions_dict.get(subject, 0) + 1
    
    report_data = []
    for student in students_list:
        student_attendance = []
        total_attended_all = 0
        total_possible_all = 0
        for subject, total in total_sessions_dict.items():
            attendance_count = attendance_col.count_documents({"student_id": student['roll_no'], "subject": subject})
            percent = round((attendance_count / total) * 100, 2) if total > 0 else 0
            student_attendance.append({"subject": subject, "attended": attendance_count, "total": total, "percentage": percent})
            total_attended_all += attendance_count
            total_possible_all += total
        
        overall_percent = round((total_attended_all / total_possible_all) * 100, 2) if total_possible_all > 0 else 0
        report_data.append({"roll_no": student['roll_no'], "name": student['name'], "branch": student['branch'],
                           "overall_percentage": overall_percent, "subjects": student_attendance})
    return render_template("students_report.html", data=report_data, total_sessions_dict=total_sessions_dict)

# ====================================================================
# PDF EXPORT ROUTES - ALL WITH CENTERED HEADER & BOTTOM LEFT TIMESTAMP
# ====================================================================

@app.route('/export_report/<session_id>')
@login_required
@faculty_required
def export_report(session_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    session_data = sessions_col.find_one({"session_id": session_id})
    if not session_data:
        return "Session not found"
    
    attendance_records = list(attendance_col.find({"session_id": session_id}).sort("time", 1))
    records = []
    for record in attendance_records:
        student = students_col.find_one({"roll_no": record['student_id']})
        records.append({
            "roll_no": record['student_id'],
            "name": student['name'] if student else 'Unknown',
            "branch": student['branch'] if student else 'Unknown',
            "time": record['time'],
            "ip_address": record.get('ip_address', 'N/A')
        })
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    settings = get_settings()
    
    # Centered Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a3c61'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#2a5298'), fontName='Helvetica-Bold')
    
    elements.append(Paragraph(settings.get('college_name', 'Smart Attendance System'), college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Attendance Report - {session_data['subject']}", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Date:</b> {session_data['start_time'].strftime('%Y-%m-%d')} &nbsp;&nbsp; <b>Time:</b> {session_data['start_time'].strftime('%H:%M:%S')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Total Students Present:</b> {len(records)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table_data = [['Roll No', 'Name', 'Branch', 'Time', 'IP Address']]
    for record in records:
        table_data.append([
            record['roll_no'],
            record['name'],
            record['branch'],
            record['time'].strftime('%H:%M:%S') if record['time'] else 'N/A',
            record['ip_address']
        ])
    
    table = Table(table_data, colWidths=[80, 100, 80, 80, 120])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Timestamp at Bottom Left
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name=f"attendance_{session_id}.pdf", as_attachment=True, mimetype='application/pdf')


@app.route('/export_student_pdf/<roll_no>')
@login_required
def export_student_pdf(roll_no):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    student = students_col.find_one({"roll_no": roll_no})
    if not student:
        return "Student not found"
    
    attendance_records = list(attendance_col.find({"student_id": roll_no}).sort("time", -1))
    all_sessions = list(sessions_col.find({}))
    
    subject_stats = {}
    for session in all_sessions:
        subject = session.get("subject")
        if subject not in subject_stats:
            subject_stats[subject] = {"total": 0, "attended": 0}
        subject_stats[subject]["total"] += 1
    
    for record in attendance_records:
        subject = record.get("subject")
        if subject in subject_stats:
            subject_stats[subject]["attended"] += 1
    
    for subject, data in subject_stats.items():
        data["percentage"] = round((data["attended"] / data["total"]) * 100, 2) if data["total"] > 0 else 0
    
    total_attended = len(attendance_records)
    total_sessions = len(all_sessions)
    overall_percentage = round((total_attended / total_sessions) * 100, 2) if total_sessions > 0 else 0
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    settings = get_settings()
    
    # Centered Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a3c61'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#2a5298'), fontName='Helvetica-Bold')
    
    elements.append(Paragraph(settings.get('college_name', 'Smart Attendance System'), college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Student Attendance Report", title_style))
    elements.append(Spacer(1, 12))
    
    # Student Info
    elements.append(Paragraph(f"<b>Name:</b> {student['name']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Roll Number:</b> {student['roll_no']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Branch:</b> {student['branch']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Year:</b> {student.get('year', 'N/A')} &nbsp;&nbsp; <b>Semester:</b> {student.get('semester', 'N/A')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Overall Attendance:</b> {overall_percentage}%", styles['Normal']))
    elements.append(Paragraph(f"<b>Total Classes Attended:</b> {total_attended} out of {total_sessions}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Subject-wise Table
    table_data = [['Subject', 'Attended', 'Total Classes', 'Percentage', 'Status']]
    for subject, data in subject_stats.items():
        status = "Good" if data['percentage'] >= 85 else "Average" if data['percentage'] >= 75 else "Needs Improvement"
        table_data.append([subject, str(data['attended']), str(data['total']), f"{data['percentage']}%", status])
    
    table = Table(table_data, colWidths=[100, 80, 80, 80, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Recent Attendance
    elements.append(Paragraph("<b>Recent Attendance Records</b>", styles['Normal']))
    recent_data = [['Date', 'Subject', 'Session ID', 'Time']]
    for record in attendance_records[:20]:
        recent_data.append([
            record['time'].strftime('%Y-%m-%d') if record['time'] else 'N/A',
            record['subject'],
            record['session_id'],
            record['time'].strftime('%H:%M:%S') if record['time'] else 'N/A'
        ])
    
    recent_table = Table(recent_data, colWidths=[100, 100, 100, 80])
    recent_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(recent_table)
    elements.append(Spacer(1, 20))
    
    # Timestamp at Bottom Left
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name=f"student_{roll_no}_report.pdf", as_attachment=True, mimetype='application/pdf')


@app.route('/export_all_students_pdf')
@login_required
@faculty_required
def export_all_students_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    students_list = list(students_col.find({}))
    all_sessions = list(sessions_col.find({}))
    total_sessions_dict = {}
    for session in all_sessions:
        subject = session['subject']
        total_sessions_dict[subject] = total_sessions_dict.get(subject, 0) + 1
    
    table_data = [['Roll No', 'Name', 'Branch', 'Overall %', 'Performance']]
    for student in students_list:
        total_attended = 0
        total_possible = 0
        for subject, total in total_sessions_dict.items():
            attended = attendance_col.count_documents({"student_id": student['roll_no'], "subject": subject})
            total_attended += attended
            total_possible += total
        overall = round((total_attended / total_possible) * 100, 2) if total_possible > 0 else 0
        performance = "Excellent" if overall >= 85 else "Good" if overall >= 75 else "Needs Improvement"
        table_data.append([student['roll_no'], student['name'], student['branch'], f"{overall}%", performance])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    settings = get_settings()
    
    # Centered Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a3c61'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#2a5298'), fontName='Helvetica-Bold')
    
    elements.append(Paragraph(settings.get('college_name', 'Smart Attendance System'), college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Complete Student Attendance Report", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Students:</b> {len(students_list)} &nbsp;&nbsp; <b>Total Sessions:</b> {len(all_sessions)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 120, 80, 80, 120])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Timestamp at Bottom Left
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name="all_students_report.pdf", as_attachment=True, mimetype='application/pdf')


@app.route('/export_subject_pdf/<subject>')
@login_required
@faculty_required
def export_subject_pdf(subject):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    sessions_list = list(sessions_col.find({"subject": subject}))
    students_list = list(students_col.find({}))
    
    table_data = [['Roll No', 'Name', 'Branch', 'Attended', 'Total', 'Percentage', 'Status']]
    for student in students_list:
        attended = attendance_col.count_documents({"student_id": student['roll_no'], "subject": subject})
        percent = round((attended / len(sessions_list)) * 100, 2) if len(sessions_list) > 0 else 0
        status = "Good" if percent >= 85 else "Average" if percent >= 75 else "Low"
        table_data.append([student['roll_no'], student['name'], student['branch'], str(attended), str(len(sessions_list)), f"{percent}%", status])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    settings = get_settings()
    
    # Centered Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a3c61'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#2a5298'), fontName='Helvetica-Bold')
    
    elements.append(Paragraph(settings.get('college_name', 'Smart Attendance System'), college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"{subject} - Attendance Report", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Sessions:</b> {len(sessions_list)} &nbsp;&nbsp; <b>Total Students:</b> {len(students_list)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 100, 80, 70, 60, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Timestamp at Bottom Left
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name=f"{subject}_report.pdf", as_attachment=True, mimetype='application/pdf')


@app.route('/export_overall_pdf')
@login_required
@faculty_required
def export_overall_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    subjects = ["ML", "DS", "CD", "IPR", "EOII", "OE-1"]
    subject_stats = []
    for subject in subjects:
        sessions_count = sessions_col.count_documents({"subject": subject})
        attended_count = attendance_col.count_documents({"subject": subject})
        percent = round((attended_count / sessions_count) * 100, 2) if sessions_count > 0 else 0
        subject_stats.append({"subject": subject, "total": sessions_count, "attended": attended_count, "percentage": percent})
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    settings = get_settings()
    
    # Centered Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a3c61'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#2a5298'), fontName='Helvetica-Bold')
    
    elements.append(Paragraph(settings.get('college_name', 'Smart Attendance System'), college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Overall Attendance Report", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Students:</b> {students_col.count_documents({})} &nbsp;&nbsp; <b>Total Sessions:</b> {sessions_col.count_documents({})}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table_data = [['Subject', 'Total Sessions', 'Total Attendance', 'Percentage', 'Performance']]
    for stat in subject_stats:
        performance = "Good" if stat['percentage'] >= 85 else "Average" if stat['percentage'] >= 75 else "Low"
        table_data.append([stat['subject'], str(stat['total']), str(stat['attended']), f"{stat['percentage']}%", performance])
    
    table = Table(table_data, colWidths=[100, 100, 100, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Timestamp at Bottom Left
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name="overall_report.pdf", as_attachment=True, mimetype='application/pdf')


@app.route('/export_all_attendance_pdf')
@login_required
def export_all_attendance_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    if session.get('role') == 'student':
        records = list(attendance_col.find({"student_id": session['user_id']}).sort("time", -1))
    else:
        records = list(attendance_col.find({}).sort("time", -1))
    
    table_data = [['Roll No', 'Name', 'Branch', 'Session ID', 'Subject', 'Date & Time']]
    for record in records:
        student = students_col.find_one({"roll_no": record['student_id']})
        table_data.append([
            record['student_id'],
            student['name'] if student else 'Unknown',
            student['branch'] if student else 'Unknown',
            record['session_id'],
            record['subject'],
            record['time'].strftime('%Y-%m-%d %H:%M:%S') if record['time'] else 'N/A'
        ])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    settings = get_settings()
    
    # Centered Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a3c61'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#2a5298'), fontName='Helvetica-Bold')
    
    elements.append(Paragraph(settings.get('college_name', 'Smart Attendance System'), college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Complete Attendance Records", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Records:</b> {len(records)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 100, 80, 100, 80, 120])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Timestamp at Bottom Left
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name="all_attendance_records.pdf", as_attachment=True, mimetype='application/pdf')


@app.route('/export_faculty_pdf')
@login_required
@admin_required
def export_faculty_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    faculties = list(faculty_col.find({}).sort("faculty_id", 1))
    table_data = [['Faculty ID', 'Name', 'Email', 'Department', 'Created Date']]
    for faculty in faculties:
        table_data.append([faculty['faculty_id'], faculty['name'], faculty['email'], faculty['department'],
                          faculty['created_at'].strftime('%Y-%m-%d') if faculty.get('created_at') else 'N/A'])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    settings = get_settings()
    
    # Centered Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a3c61'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#2a5298'), fontName='Helvetica-Bold')
    
    elements.append(Paragraph(settings.get('college_name', 'Smart Attendance System'), college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Faculty Directory", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Faculty:</b> {len(faculties)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 120, 150, 80, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Timestamp at Bottom Left
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name="faculty_list.pdf", as_attachment=True, mimetype='application/pdf')


@app.route('/export_students_pdf')
@login_required
@admin_required
def export_students_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io
    
    students_list = list(students_col.find({}).sort("roll_no", 1))
    table_data = [['Roll No', 'Name', 'Branch', 'Email', 'Year', 'Semester', 'Created Date']]
    for student in students_list:
        table_data.append([student['roll_no'], student['name'], student['branch'], student.get('email', 'N/A'),
                          f"{student.get('year', 'N/A')} Year", f"Sem {student.get('semester', 'N/A')}",
                          student['created_at'].strftime('%Y-%m-%d') if student.get('created_at') else 'N/A'])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    settings = get_settings()
    
    # Centered Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a3c61'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#2a5298'), fontName='Helvetica-Bold')
    
    elements.append(Paragraph(settings.get('college_name', 'Smart Attendance System'), college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Student Directory", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Students:</b> {len(students_list)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 120, 80, 120, 70, 70, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Timestamp at Bottom Left
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name="student_list.pdf", as_attachment=True, mimetype='application/pdf')

# ====================================================================
# ADMIN ROUTES
# ====================================================================

@app.route('/admin_dashboard')
@login_required
@admin_required
def admin_dashboard():
    stats = get_dashboard_stats()
    recent_sessions = list(sessions_col.find({}).sort("start_time", -1).limit(5))
    all_notices = list(notices_col.find({}).sort("created_at", -1))
    return render_template("admin_dashboard.html", name=session['user_name'], stats=stats, recent_sessions=recent_sessions, notices=all_notices, now=datetime.now())

@app.route('/admin/manage_faculty')
@login_required
@admin_required
def admin_manage_faculty():
    faculties = list(faculty_col.find({}).sort("faculty_id", 1))
    return render_template("admin_manage_faculty.html", faculties=faculties)

@app.route('/admin/add_faculty', methods=['POST'])
@login_required
@admin_required
def admin_add_faculty():
    faculty_data = {"faculty_id": request.form['faculty_id'], "name": request.form['name'], "email": request.form['email'],
                    "department": request.form['department'], "password": request.form['password'], "created_at": datetime.now()}
    try:
        faculty_col.insert_one(faculty_data)
    except:
        pass
    return redirect(url_for('admin_manage_faculty'))

@app.route('/admin/edit_faculty/<faculty_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_faculty(faculty_id):
    faculty = faculty_col.find_one({"faculty_id": faculty_id})
    if request.method == 'POST':
        updated_data = {"name": request.form['name'], "email": request.form['email'], "department": request.form['department']}
        if request.form.get('password'):
            updated_data["password"] = request.form['password']
        faculty_col.update_one({"faculty_id": faculty_id}, {"$set": updated_data})
        return redirect(url_for('admin_manage_faculty'))
    return render_template("admin_edit_faculty.html", faculty=faculty)

@app.route('/admin/delete_faculty/<faculty_id>')
@login_required
@admin_required
def admin_delete_faculty(faculty_id):
    faculty_col.delete_one({"faculty_id": faculty_id})
    return redirect(url_for('admin_manage_faculty'))

@app.route('/admin/manage_students')
@login_required
@admin_required
def admin_manage_students():
    students_list = list(students_col.find({}).sort("roll_no", 1))
    return render_template("admin_manage_students.html", students=students_list)

@app.route('/admin/add_student', methods=['POST'])
@login_required
@admin_required
def admin_add_student():
    student_data = {"roll_no": request.form['roll_no'], "name": request.form['name'], "branch": request.form['branch'],
                    "year": int(request.form.get('year', 3)), "semester": int(request.form.get('semester', 6)),
                    "email": request.form.get('email', ''), "created_at": datetime.now()}
    try:
        students_col.insert_one(student_data)
    except:
        pass
    return redirect(url_for('admin_manage_students'))

@app.route('/admin/edit_student/<roll_no>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_student(roll_no):
    student = students_col.find_one({"roll_no": roll_no})
    if request.method == 'POST':
        updated_data = {"name": request.form['name'], "branch": request.form['branch'], "email": request.form.get('email', ''),
                        "year": int(request.form.get('year', 3)), "semester": int(request.form.get('semester', 6))}
        students_col.update_one({"roll_no": roll_no}, {"$set": updated_data})
        return redirect(url_for('admin_manage_students'))
    return render_template("admin_edit_student.html", student=student)

@app.route('/admin/delete_student/<roll_no>')
@login_required
@admin_required
def admin_delete_student(roll_no):
    attendance_col.delete_many({"student_id": roll_no})
    students_col.delete_one({"roll_no": roll_no})
    return redirect(url_for('admin_manage_students'))

@app.route('/admin/manage_sessions')
@login_required
@admin_required
def admin_manage_sessions():
    sessions_list = list(sessions_col.find({}).sort("start_time", -1))
    for session in sessions_list:
        session['attendance_count'] = attendance_col.count_documents({"session_id": session['session_id']})
    return render_template("admin_manage_sessions.html", sessions=sessions_list, now=datetime.now())

@app.route('/admin/view_session/<session_id>')
@login_required
@admin_required
def admin_view_session(session_id):
    session_data = sessions_col.find_one({"session_id": session_id})
    records = list(attendance_col.find({"session_id": session_id}).sort("time", 1))
    for record in records:
        student = students_col.find_one({"roll_no": record['student_id']})
        record['name'] = student['name'] if student else 'Unknown'
        record['branch'] = student['branch'] if student else 'Unknown'
    return render_template("admin_view_session.html", session=session_data, records=records)

@app.route('/admin/delete_session/<session_id>')
@login_required
@admin_required
def admin_delete_session(session_id):
    attendance_col.delete_many({"session_id": session_id})
    sessions_col.delete_one({"session_id": session_id})
    return redirect(url_for('admin_manage_sessions'))

@app.route('/admin/system_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_system_settings():
    message = None
    if request.method == 'POST':
        settings_col.update_one({}, {"$set": {"attendance_threshold": int(request.form.get('attendance_threshold', 75)),
                    "qr_expiry_seconds": int(request.form.get('qr_expiry', 60)), "session_duration_minutes": int(request.form.get('session_duration', 5)),
                    "college_name": request.form.get('college_name'), "college_location": request.form.get('college_location'),
                    "academic_year": request.form.get('academic_year')}}, upsert=True)
        message = "✅ Settings updated successfully!"
    settings = get_settings()
    return render_template("admin_system_settings.html", settings=settings, message=message)

@app.route('/admin/change_password', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_change_password():
    message = None
    error = None
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        admin = admins_col.find_one({"admin_id": session['user_id']})
        if current_password != admin['password']:
            error = "❌ Current password is incorrect"
        elif new_password != confirm_password:
            error = "❌ New passwords do not match"
        elif len(new_password) < 6:
            error = "❌ Password must be at least 6 characters"
        else:
            admins_col.update_one({"admin_id": session['user_id']}, {"$set": {"password": new_password}})
            message = "✅ Password changed successfully!"
    return render_template("admin_change_password.html", message=message, error=error)

@app.route('/admin/add_notice', methods=['POST'])
@login_required
@admin_required
def admin_add_notice():
    notice = {"title": request.form.get('title'), "content": request.form.get('content'), "author": session['user_name'],
              "created_at": datetime.now(), "is_active": True}
    notices_col.insert_one(notice)
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_notice/<notice_id>')
@login_required
@admin_required
def admin_delete_notice(notice_id):
    notices_col.delete_one({"_id": ObjectId(notice_id)})
    return redirect(url_for('admin_dashboard'))

# ====================================================================
# STATIC PAGES
# ====================================================================

@app.route('/subject_details')
def subject_details():
    return render_template("subject_details.html")

@app.route('/about')
def about():
    return render_template("about.html")

# ====================================================================
# RUN APPLICATION
# ====================================================================

if __name__ == "__main__":
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get("PORT", 5000))
    
    print("\n" + "=" * 60)
    print("🚀 SMART ATTENDANCE SYSTEM")
    print("=" * 60)
    print(f"📊 Database: {DB_NAME}")
    print(f"🌐 Server running on port: {port}")
    print("\n👥 Login Credentials:")
    print("   Admin:   ADMIN001 / admin123")
    print("   Faculty: FAC001 / faculty123")
    print("   Student: CS001 (no password)")
    print("\n" + "=" * 60 + "\n")
    
    # For production, don't use debug mode
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode, host='0.0.0.0', port=port)