from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from functools import wraps
from io import BytesIO
import os
import json
import random
import re
import csv
import sys
import traceback

app = Flask(__name__)

# ============== Configuration ==============
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'digiserve-secret-key-2026')
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # MongoDB Atlas Connection
    MONGO_URI = os.environ.get('MONGO_URI', "mongodb+srv://digiserve_admin:digiserve2324@digiserve-cluster.mrlhjs4.mongodb.net/digiserve?retryWrites=true&w=majority&appName=digiserve-cluster")
    
    # Upload Configuration
    UPLOAD_FOLDER = 'uploads/'
    DOCUMENT_FOLDER = 'uploads/documents/'
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'txt'}
    
    ADMIN_PHONE = '9999999999'
    ADMIN_NAME = 'Administrator'
    ADMIN_EMAIL = 'admin@digiserve.com'
    ITEMS_PER_PAGE = 10

app.config.from_object(Config)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOCUMENT_FOLDER'], exist_ok=True)

# Initialize MongoDB
try:
    mongo = PyMongo(app)
    db = mongo.db
    # Test connection
    db.command('ping')
    print("✅ MongoDB Atlas connected successfully!")
except Exception as e:
    print(f"❌ MongoDB connection error: {e}")
    db = None

# ============== Helper Functions ==============

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_by_id(user_id):
    if not db:
        return None
    try:
        return db.users.find_one({'_id': ObjectId(user_id)})
    except:
        return None

def get_user_by_phone(phone):
    if not db:
        return None
    try:
        return db.users.find_one({'phone': phone})
    except:
        return None

def validate_phone(phone):
    return bool(re.match(r'^[6-9]\d{9}$', phone))

def validate_pincode(pincode):
    return bool(re.match(r'^\d{6}$', pincode))

def validate_email(email):
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def validate_aadhar(number):
    return bool(re.match(r'^[2-9]{1}[0-9]{3}[0-9]{4}[0-9]{4}$', number))

def validate_pan(number):
    return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', number))

def calculate_fees(service_charge, convenience_fee_percent=2, gst_percent=18):
    convenience_fee = (service_charge * convenience_fee_percent) / 100
    subtotal = service_charge + convenience_fee
    gst = (subtotal * gst_percent) / 100
    total = subtotal + gst
    return {
        'service_charge': round(service_charge, 2),
        'convenience_fee': round(convenience_fee, 2),
        'convenience_fee_percent': convenience_fee_percent,
        'subtotal': round(subtotal, 2),
        'gst': round(gst, 2),
        'gst_percent': gst_percent,
        'total': round(total, 2)
    }

def generate_reference_number():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = random.randint(1000, 9999)
    return f'DS{timestamp}{random_part}'

def generate_transaction_id():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = random.randint(10000, 99999)
    return f'TXN{timestamp}{random_part}'

def create_notification(user_id, request_id, title, message, type='info'):
    if not db:
        return None
    try:
        notification = {
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'request_id': str(request_id) if request_id else None,
            'title': title,
            'message': message,
            'type': type,
            'is_read': False,
            'created_at': datetime.now(timezone.utc)
        }
        result = db.notifications.insert_one(notification)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error creating notification: {e}")
        return None

def format_time_ago(dt):
    if not dt:
        return "Unknown"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    if isinstance(dt, datetime):
        now = datetime.now(timezone.utc)
        diff = now - dt
        if diff.days > 365:
            return f"{diff.days // 365} year(s) ago"
        elif diff.days > 30:
            return f"{diff.days // 30} month(s) ago"
        elif diff.days > 0:
            return f"{diff.days} day(s) ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600} hour(s) ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60} minute(s) ago"
        else:
            return "Just now"
    return str(dt)

def get_service_by_slug(slug):
    if not db:
        return None
    try:
        return db.services.find_one({'slug': slug, 'is_active': True})
    except:
        return None

def get_service_by_id(service_id):
    if not db:
        return None
    try:
        return db.services.find_one({'_id': ObjectId(service_id)})
    except:
        return None

def get_all_services(limit=None):
    if not db:
        return []
    try:
        query = {'is_active': True}
        services = list(db.services.find(query).sort('created_at', 1))
        if limit:
            services = services[:limit]
        for service in services:
            service['id'] = str(service['_id'])
        return services
    except Exception as e:
        print(f"Error getting services: {e}")
        return []

def get_services_by_category():
    if not db:
        return {}
    try:
        query = {'is_active': True}
        services = list(db.services.find(query).sort('created_at', 1))
        categorized = {}
        for service in services:
            category = service.get('category', 'other')
            if category not in categorized:
                categorized[category] = []
            service['id'] = str(service['_id'])
            categorized[category].append(service)
        return categorized
    except Exception as e:
        print(f"Error getting services by category: {e}")
        return {}

def get_applicant_display_name(request_data):
    if request_data.get('applicant_name'):
        return request_data['applicant_name']
    try:
        if request_data.get('details'):
            details = json.loads(request_data['details'])
            return details.get('full_name', 'N/A')
    except:
        pass
    return 'N/A'

def auto_create_admin_user():
    if not db:
        return None
    try:
        existing_admin = db.users.find_one({'phone': Config.ADMIN_PHONE})
        if existing_admin:
            return existing_admin
        
        admin_user = {
            'name': Config.ADMIN_NAME,
            'phone': Config.ADMIN_PHONE,
            'email': Config.ADMIN_EMAIL,
            'role': 'admin',
            'is_active': True,
            'created_at': datetime.now(timezone.utc),
            'last_login': datetime.now(timezone.utc),
            'address': 'Admin Office',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400001'
        }
        result = db.users.insert_one(admin_user)
        admin_user['_id'] = result.inserted_id
        print(f"✅ Auto-created admin user: {Config.ADMIN_PHONE}")
        return admin_user
    except Exception as e:
        print(f"Error auto-creating admin: {e}")
        return None

# ============== Database Initialization ==============

def init_db():
    if not db:
        print("❌ Database not available")
        return False
    
    print("📦 Initializing database...")
    
    try:
        # Create indexes
        db.users.create_index('phone', unique=True)
        db.users.create_index('email', sparse=True)
        db.services.create_index('slug', unique=True)
        db.services.create_index('category')
        db.service_requests.create_index('reference_number', unique=True)
        db.service_requests.create_index('user_id')
        db.service_requests.create_index('status')
        db.service_requests.create_index('submitted_at')
        db.notifications.create_index('user_id')
        db.notifications.create_index('created_at')
        db.payment_transactions.create_index('transaction_id', unique=True)
        db.payment_transactions.create_index('user_id')
        db.request_documents.create_index('request_id')
        print("✅ Indexes created successfully")
        
        # Create admin user
        auto_create_admin_user()
        
        # Create default services
        default_services = [
            {
                'category': 'scholarship',
                'name': 'PMSSS Scholarship Application',
                'slug': 'pmsss-scholarship',
                'description': "Prime Minister's Special Scholarship Scheme for Jammu and Kashmir students.",
                'eligibility': 'Students who have passed 10+2 examination from J&K board with minimum 60% marks.',
                'documents_required': '10th Marksheet, 12th Marksheet, Domicile Certificate, Income Certificate',
                'instructions': 'Ensure all documents are self-attested. Upload clear scanned copies.',
                'processing_time': '15-20 working days',
                'service_charge': 0,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-graduation-cap',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'scholarship',
                'name': 'Post Matric Scholarship',
                'slug': 'post-matric-scholarship',
                'description': 'Post Matric Scholarship for SC/ST/OBC students.',
                'eligibility': 'Students belonging to SC/ST/OBC categories with family income less than ₹2.5 LPA.',
                'documents_required': 'Caste Certificate, Income Certificate, Previous Year Marksheet',
                'instructions': 'Fill all details carefully. Upload income certificate for verification.',
                'processing_time': '20-25 working days',
                'service_charge': 0,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-university',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'education',
                'name': 'MHT-CET Application Form',
                'slug': 'mht-cet-application',
                'description': 'Maharashtra Common Entrance Test for Engineering and Pharmacy admissions.',
                'eligibility': 'Indian citizen, passed 10+2 with PCM/PCB from recognized board.',
                'documents_required': '10th Marksheet, 12th Marksheet, Domicile Certificate, Photo, Signature',
                'instructions': 'Fill the form carefully. Double-check all entered information.',
                'processing_time': 'Same day processing',
                'service_charge': 800,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-file-alt',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'document',
                'name': 'PAN Card Application',
                'slug': 'pan-card-application',
                'description': 'Apply for new PAN card or request for reprint.',
                'eligibility': 'Indian citizen with valid address proof and identity proof.',
                'documents_required': 'Aadhar Card, Address Proof, Passport Size Photo',
                'instructions': 'Use clear photograph with white background.',
                'processing_time': '15-20 working days',
                'service_charge': 150,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-id-card',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'bill_payment',
                'name': 'Electricity Bill Payment',
                'slug': 'electricity-bill-payment',
                'description': 'Pay your electricity bill online instantly.',
                'eligibility': 'Valid electricity consumer number',
                'documents_required': 'Consumer Number',
                'instructions': 'Enter correct consumer number as shown on your bill.',
                'processing_time': 'Instant',
                'service_charge': 0,
                'convenience_fee_percent': 0,
                'gst_percent': 0,
                'is_active': True,
                'icon': 'fas fa-lightbulb',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'exams',
                'name': 'UPSC Civil Services Form',
                'slug': 'upsc-civil-services',
                'description': 'UPSC Civil Services Examination application form filling assistance.',
                'eligibility': 'Graduate in any discipline from recognized university',
                'documents_required': 'Graduation Certificate, Date of Birth Proof, Photo, Signature',
                'instructions': 'Fill DAF (Detailed Application Form) carefully.',
                'processing_time': '2-3 working days',
                'service_charge': 500,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-landmark',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'eseva',
                'name': 'Birth Certificate Application',
                'slug': 'birth-certificate',
                'description': 'Apply for new birth certificate online.',
                'eligibility': 'Birth registered within 21 days of occurrence',
                'documents_required': 'Hospital Discharge Certificate, Parents ID Proof',
                'instructions': 'Provide correct hospital name and date of birth.',
                'processing_time': '7-10 working days',
                'service_charge': 200,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-baby-carriage',
                'created_at': datetime.now(timezone.utc)
            },
            {
                'category': 'eseva',
                'name': 'Income Certificate Application',
                'slug': 'income-certificate',
                'description': 'Apply for income certificate for scholarship and government schemes.',
                'eligibility': 'Resident of the state with valid address proof.',
                'documents_required': 'Aadhar Card, Address Proof, Previous Income Certificate',
                'instructions': 'Provide correct income details from all sources.',
                'processing_time': '10-15 working days',
                'service_charge': 100,
                'convenience_fee_percent': 2,
                'gst_percent': 18,
                'is_active': True,
                'icon': 'fas fa-file-invoice-dollar',
                'created_at': datetime.now(timezone.utc)
            }
        ]
        
        for service in default_services:
            if not db.services.find_one({'slug': service['slug']}):
                db.services.insert_one(service)
                print(f"✅ Added service: {service['name']}")
        
        print("=" * 60)
        print("🚀 DigiServe eSeva Portal is ready!")
        print("📍 MongoDB Atlas: Connected")
        print("👑 Admin Login: 9999999999")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        traceback.print_exc()
        return False

# ============== Routes ==============

@app.route('/')
def index():
    try:
        services = get_all_services(6)
        stats = {
            'total_users': db.users.count_documents({'role': 'user'}) if db else 0,
            'total_applications': db.service_requests.count_documents({}) if db else 0,
            'total_services': db.services.count_documents({'is_active': True}) if db else 0
        }
        return render_template('index.html', services=services, stats=stats)
    except Exception as e:
        print(f"Error loading index: {e}")
        return render_template('index.html', services=[], stats={'total_users': 0, 'total_applications': 0, 'total_services': 0})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        
        if not phone or not validate_phone(phone):
            flash('Please enter a valid 10-digit mobile number', 'danger')
            return redirect(url_for('login'))
        
        try:
            user = get_user_by_phone(phone)
            
            if user:
                session['user_id'] = str(user['_id'])
                session['user_name'] = user['name']
                session['user_role'] = user.get('role', 'user')
                session['user_phone'] = user['phone']
                session.permanent = True
                
                if db:
                    db.users.update_one(
                        {'_id': user['_id']},
                        {'$set': {'last_login': datetime.now(timezone.utc)}}
                    )
                
                flash(f'Welcome back, {user["name"]}!', 'success')
                
                if user.get('role') == 'admin':
                    return redirect(url_for('admin_panel'))
                return redirect(url_for('services_dashboard'))
            
            else:
                if phone == Config.ADMIN_PHONE:
                    admin_user = auto_create_admin_user()
                    if admin_user:
                        session['user_id'] = str(admin_user['_id'])
                        session['user_name'] = admin_user['name']
                        session['user_role'] = 'admin'
                        session['user_phone'] = admin_user['phone']
                        session.permanent = True
                        flash('Welcome, Administrator!', 'success')
                        return redirect(url_for('admin_panel'))
                    else:
                        flash('Unable to create admin account.', 'danger')
                        return redirect(url_for('login'))
                else:
                    flash('New number detected! Please complete registration.', 'info')
                    return redirect(url_for('register', phone=phone))
                
        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    phone = request.args.get('phone', '')
    
    if phone == Config.ADMIN_PHONE:
        flash('This is an administrator number. Please use admin login.', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip() or None
        address = request.form.get('address', '').strip() or None
        city = request.form.get('city', '').strip() or None
        state = request.form.get('state', '').strip() or None
        pincode = request.form.get('pincode', '').strip() or None
        
        if not name or len(name) < 2:
            flash('Please enter a valid name (minimum 2 characters)', 'danger')
            return redirect(url_for('register', phone=phone))
        
        if not phone or not validate_phone(phone):
            flash('Please enter a valid 10-digit mobile number', 'danger')
            return redirect(url_for('register', phone=phone))
        
        if phone == Config.ADMIN_PHONE:
            flash('This number is reserved for administrator.', 'warning')
            return redirect(url_for('login'))
        
        if email and not validate_email(email):
            flash('Please enter a valid email address', 'danger')
            return redirect(url_for('register', phone=phone))
        
        if pincode and not validate_pincode(pincode):
            flash('Pincode must be 6 digits', 'danger')
            return redirect(url_for('register', phone=phone))
        
        try:
            existing_user = get_user_by_phone(phone)
            if existing_user:
                flash('Mobile number already registered. Please login.', 'info')
                return redirect(url_for('login'))
            
            new_user = {
                'name': name.title(),
                'phone': phone,
                'email': email,
                'role': 'user',
                'is_active': True,
                'created_at': datetime.now(timezone.utc),
                'last_login': None,
                'address': address,
                'city': city,
                'state': state,
                'pincode': pincode
            }
            result = db.users.insert_one(new_user)
            
            session['user_id'] = str(result.inserted_id)
            session['user_name'] = name
            session['user_role'] = 'user'
            session['user_phone'] = phone
            session.permanent = True
            
            create_notification(
                result.inserted_id,
                None,
                'Welcome to DigiServe! 🎉',
                f'Welcome {name}! Thank you for registering with DigiServe.',
                'success'
            )
            
            flash(f'Welcome to DigiServe, {name}!', 'success')
            return redirect(url_for('services_dashboard'))
            
        except Exception as e:
            print(f"Registration error: {e}")
            flash('An error occurred during registration. Please try again.', 'danger')
            return redirect(url_for('register', phone=phone))
    
    return render_template('register.html', phone=phone)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/services-dashboard')
@login_required
def services_dashboard():
    try:
        user = get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            flash('Session expired. Please login again.', 'warning')
            return redirect(url_for('login'))
        
        categorized_services = get_services_by_category()
        
        recent_count = db.service_requests.count_documents({
            'user_id': ObjectId(session['user_id']),
            'submitted_at': {'$gte': datetime.now(timezone.utc) - timedelta(days=30)}
        }) if db else 0
        
        completed_count = db.service_requests.count_documents({
            'user_id': ObjectId(session['user_id']),
            'status': 'completed'
        }) if db else 0
        
        pending_count = db.service_requests.count_documents({
            'user_id': ObjectId(session['user_id']),
            'status': {'$in': ['pending', 'in_progress']}
        }) if db else 0
        
        unread_count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        }) if db else 0
        
        return render_template('services_dashboard.html',
                             user=user,
                             services=categorized_services,
                             recent_count=recent_count,
                             completed_count=completed_count,
                             pending_count=pending_count,
                             unread_count=unread_count)
    except Exception as e:
        print(f"Error loading dashboard: {e}")
        flash('Unable to load services. Please try again.', 'danger')
        return redirect(url_for('index'))

@app.route('/service/<slug>')
@login_required
def service_detail(slug):
    try:
        service = get_service_by_slug(slug)
        if not service:
            flash('Service not found', 'danger')
            return redirect(url_for('services_dashboard'))
        
        service['id'] = str(service['_id'])
        user = get_user_by_id(session['user_id'])
        
        return render_template('service_detail.html', service=service, user=user)
    except Exception as e:
        print(f"Error loading service: {e}")
        flash('Unable to load service details.', 'danger')
        return redirect(url_for('services_dashboard'))

@app.route('/my-requests')
@login_required
def my_requests_page():
    try:
        user = get_user_by_id(session['user_id'])
        unread_count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        }) if db else 0
        
        return render_template('my_requests.html', user=user, unread_count=unread_count)
    except Exception as e:
        print(f"Error loading requests page: {e}")
        flash('Unable to load your requests.', 'danger')
        return redirect(url_for('services_dashboard'))

@app.route('/api/my-requests')
@login_required
def api_my_requests():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', Config.ITEMS_PER_PAGE))
        status = request.args.get('status', 'all')
        payment = request.args.get('payment', 'all')
        search = request.args.get('search', '').strip()
        
        query = {'user_id': ObjectId(session['user_id'])}
        if status != 'all':
            query['status'] = status
        if payment != 'all':
            query['payment_status'] = payment
        if search:
            query['$or'] = [
                {'reference_number': {'$regex': search, '$options': 'i'}},
                {'service_name': {'$regex': search, '$options': 'i'}},
                {'applicant_name': {'$regex': search, '$options': 'i'}}
            ]
        
        total = db.service_requests.count_documents(query) if db else 0
        skip = (page - 1) * per_page
        
        requests_list = list(db.service_requests.find(query).sort('submitted_at', -1).skip(skip).limit(per_page)) if db else []
        
        data = []
        for req in requests_list:
            data.append({
                'id': str(req['_id']),
                'reference': req['reference_number'],
                'service_name': req['service_name'],
                'status': req['status'],
                'payment_status': req['payment_status'],
                'amount': req['amount'],
                'submitted_at': req['submitted_at'].strftime('%Y-%m-%d %H:%M'),
                'documents_count': db.request_documents.count_documents({'request_id': req['_id']}) if db else 0,
                'applicant_name': req.get('applicant_name', get_applicant_display_name(req))
            })
        
        return jsonify({
            'requests': data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if per_page > 0 else 1
        })
    except Exception as e:
        print(f"Error fetching requests: {e}")
        return jsonify({'error': 'Unable to fetch requests'}), 500

@app.route('/request-details/<request_id>')
@login_required
def request_details(request_id):
    try:
        service_request = db.service_requests.find_one({'_id': ObjectId(request_id)}) if db else None
        if not service_request:
            return jsonify({'error': 'Request not found'}), 404
        
        if str(service_request['user_id']) != session['user_id'] and session.get('user_role') != 'admin':
            return jsonify({'error': 'Access denied'}), 403
        
        documents = list(db.request_documents.find({'request_id': ObjectId(request_id)})) if db else []
        
        for doc in documents:
            doc['id'] = str(doc['_id'])
            if isinstance(doc.get('uploaded_at'), datetime):
                doc['uploaded_at'] = doc['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        request_dict = {
            'id': str(service_request['_id']),
            'reference_number': service_request['reference_number'],
            'service_name': service_request['service_name'],
            'status': service_request['status'],
            'payment_status': service_request['payment_status'],
            'amount': service_request['amount'],
            'submitted_at': service_request['submitted_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(service_request['submitted_at'], datetime) else str(service_request['submitted_at']),
            'processed_at': service_request['processed_at'].strftime('%Y-%m-%d %H:%M:%S') if service_request.get('processed_at') and isinstance(service_request['processed_at'], datetime) else None,
            'admin_remarks': service_request.get('admin_remarks', ''),
            'applicant_name': service_request.get('applicant_name', ''),
            'applicant_dob': service_request.get('applicant_dob', ''),
            'applicant_gender': service_request.get('applicant_gender', ''),
            'applicant_category': service_request.get('applicant_category', ''),
            'applicant_address': service_request.get('applicant_address', ''),
            'applicant_city': service_request.get('applicant_city', ''),
            'applicant_state': service_request.get('applicant_state', ''),
            'applicant_pincode': service_request.get('applicant_pincode', ''),
            'applicant_email': service_request.get('applicant_email', ''),
            'qualification': service_request.get('qualification', ''),
            'institute_name': service_request.get('institute_name', ''),
            'course_name': service_request.get('course_name', ''),
            'passing_year': service_request.get('passing_year', ''),
            'percentage': service_request.get('percentage', ''),
            'additional_details': service_request.get('additional_details', ''),
            'timeline': service_request.get('timeline', [])
        }
        
        if service_request.get('details'):
            try:
                details_data = json.loads(service_request['details'])
                request_dict['details_data'] = details_data
            except:
                pass
        
        return jsonify({
            'request': request_dict,
            'documents': documents
        })
    except Exception as e:
        print(f"Error fetching request details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/submit-service-request', methods=['POST'])
@login_required
def submit_service_request():
    try:
        service_id = request.form.get('service_id')
        user = get_user_by_id(session['user_id'])
        service = get_service_by_id(service_id)
        
        if not service:
            return jsonify({'success': False, 'message': 'Service not found'}), 404
        
        full_name = request.form.get('full_name', '').strip()
        dob = request.form.get('dob', '')
        gender = request.form.get('gender', '')
        category = request.form.get('category', '')
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        email = request.form.get('email', '').strip()
        aadhar_number = request.form.get('aadhar_number', '').strip()
        pan_number = request.form.get('pan_number', '').strip()
        qualification = request.form.get('qualification', '')
        institute_name = request.form.get('institute_name', '')
        course_name = request.form.get('course_name', '')
        passing_year = request.form.get('passing_year', '')
        percentage = request.form.get('percentage', '')
        additional_details = request.form.get('additional_details', '').strip()
        
        required_fields = [full_name, dob, gender, category, address, city, state, pincode]
        if not all(required_fields):
            return jsonify({'success': False, 'message': 'Please fill all required fields'}), 400
        
        if pincode and not validate_pincode(pincode):
            return jsonify({'success': False, 'message': 'Invalid pincode format'}), 400
        
        service_charge = service.get('service_charge', 0)
        convenience_fee_percent = service.get('convenience_fee_percent', 2)
        gst_percent = service.get('gst_percent', 18)
        fee_details = calculate_fees(service_charge, convenience_fee_percent, gst_percent)
        
        details_json = {
            'full_name': full_name,
            'dob': dob,
            'gender': gender,
            'category': category,
            'address': address,
            'city': city,
            'state': state,
            'pincode': pincode,
            'email': email,
            'aadhar_number': aadhar_number,
            'pan_number': pan_number,
            'qualification': qualification,
            'institute_name': institute_name,
            'course_name': course_name,
            'passing_year': passing_year,
            'percentage': percentage,
            'additional_details': additional_details,
            'fee_details': fee_details,
            'submitted_by': user['name'],
            'submitted_phone': user['phone'],
            'submitted_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        details = json.dumps(details_json, indent=2)
        ref_number = generate_reference_number()
        
        request_data = {
            'user_id': ObjectId(session['user_id']),
            'service_id': ObjectId(service_id),
            'service_type': service['category'],
            'service_name': service['name'],
            'sub_service': None,
            'details': details,
            'amount': fee_details['total'],
            'payment_status': 'pending',
            'status': 'pending',
            'reference_number': ref_number,
            'submitted_at': datetime.now(timezone.utc),
            'processed_at': None,
            'admin_remarks': None,
            'applicant_name': full_name,
            'applicant_dob': dob,
            'applicant_gender': gender,
            'applicant_category': category,
            'applicant_address': address,
            'applicant_city': city,
            'applicant_state': state,
            'applicant_pincode': pincode,
            'applicant_email': email,
            'additional_details': additional_details,
            'timeline': [
                {
                    'title': 'Application Submitted',
                    'description': f'Your application for {service["name"]} has been submitted successfully.',
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'completed': True
                }
            ]
        }
        
        result = db.service_requests.insert_one(request_data)
        request_id = result.inserted_id
        
        uploaded_docs = []
        files = request.files.getlist('documents')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'pdf'
                stored_filename = f"{ref_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}.{file_ext}"
                file_path = os.path.join(app.config['DOCUMENT_FOLDER'], stored_filename)
                file.save(file_path)
                
                doc = {
                    'request_id': request_id,
                    'document_type': 'general',
                    'original_filename': original_filename,
                    'stored_filename': stored_filename,
                    'file_path': file_path,
                    'file_size': os.path.getsize(file_path),
                    'uploaded_at': datetime.now(timezone.utc)
                }
                db.request_documents.insert_one(doc)
                uploaded_docs.append(original_filename)
        
        create_notification(
            ObjectId(session['user_id']),
            str(request_id),
            'Application Submitted ✅',
            f'Your application for {service["name"]} has been submitted. Reference: {ref_number}',
            'success'
        )
        
        admins = list(db.users.find({'role': 'admin'})) if db else []
        for admin in admins:
            create_notification(
                admin['_id'],
                str(request_id),
                'New Application Received 🆕',
                f'New application from {full_name} for {service["name"]}. Ref: {ref_number}',
                'info'
            )
        
        return jsonify({
            'success': True,
            'message': 'Application submitted successfully',
            'reference_number': ref_number,
            'amount': fee_details['total'],
            'fee_details': fee_details,
            'requires_payment': fee_details['total'] > 0,
            'documents_uploaded': len(uploaded_docs)
        })
        
    except Exception as e:
        print(f"Error submitting request: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/initiate-payment/<ref_number>', methods=['POST'])
@login_required
def initiate_payment(ref_number):
    try:
        service_request = db.service_requests.find_one({
            'reference_number': ref_number,
            'user_id': ObjectId(session['user_id'])
        }) if db else None
        
        if not service_request:
            return jsonify({'success': False, 'message': 'Request not found'}), 404
        
        if service_request['payment_status'] == 'completed':
            return jsonify({'success': False, 'message': 'Payment already completed'}), 400
        
        transaction_id = generate_transaction_id()
        
        payment = {
            'user_id': ObjectId(session['user_id']),
            'request_id': service_request['_id'],
            'transaction_id': transaction_id,
            'amount': service_request['amount'],
            'payment_method': 'online',
            'status': 'completed',
            'created_at': datetime.now(timezone.utc)
        }
        
        db.payment_transactions.insert_one(payment)
        
        db.service_requests.update_one(
            {'_id': service_request['_id']},
            {'$set': {
                'payment_status': 'completed',
                'status': 'in_progress'
            }}
        )
        
        db.service_requests.update_one(
            {'_id': service_request['_id']},
            {'$push': {
                'timeline': {
                    'title': 'Payment Completed',
                    'description': f'Payment of ₹{service_request["amount"]} has been received. Transaction ID: {transaction_id}',
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'completed': True
                }
            }}
        )
        
        create_notification(
            ObjectId(session['user_id']),
            str(service_request['_id']),
            'Payment Successful 💰',
            f'Payment of ₹{service_request["amount"]} completed. Transaction ID: {transaction_id}',
            'success'
        )
        
        return jsonify({
            'success': True,
            'message': 'Payment successful!',
            'transaction_id': transaction_id
        })
    except Exception as e:
        print(f"Payment error: {e}")
        return jsonify({'success': False, 'message': 'Payment failed. Please try again.'}), 500

@app.route('/user-profile', methods=['GET'])
@login_required
def get_user_profile():
    try:
        user = get_user_by_id(session['user_id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'name': user['name'],
            'phone': user['phone'],
            'email': user.get('email', ''),
            'address': user.get('address', ''),
            'city': user.get('city', ''),
            'state': user.get('state', ''),
            'pincode': user.get('pincode', ''),
            'created_at': user['created_at'].strftime('%Y-%m-%d') if isinstance(user['created_at'], datetime) else str(user['created_at'])
        })
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return jsonify({'error': 'Unable to fetch profile'}), 500

@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        data = request.get_json()
        
        update_data = {}
        if 'email' in data:
            if data['email'] and not validate_email(data['email']):
                return jsonify({'success': False, 'message': 'Invalid email format'}), 400
            update_data['email'] = data['email'] or None
        if 'address' in data:
            update_data['address'] = data['address'] or None
        if 'city' in data:
            update_data['city'] = data['city'] or None
        if 'state' in data:
            update_data['state'] = data['state'] or None
        if 'pincode' in data:
            if data['pincode'] and not validate_pincode(data['pincode']):
                return jsonify({'success': False, 'message': 'Invalid pincode format'}), 400
            update_data['pincode'] = data['pincode'] or None
        
        if update_data:
            db.users.update_one(
                {'_id': ObjectId(session['user_id'])},
                {'$set': update_data}
            )
        
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        print(f"Error updating profile: {e}")
        return jsonify({'success': False, 'message': 'Unable to update profile'}), 500

@app.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    try:
        notifications = list(db.notifications.find(
            {'user_id': ObjectId(session['user_id'])}
        ).sort('created_at', -1).limit(50)) if db else []
        
        result = []
        for n in notifications:
            result.append({
                'id': str(n['_id']),
                'title': n['title'],
                'message': n['message'],
                'type': n['type'],
                'is_read': n['is_read'],
                'request_id': n.get('request_id'),
                'created_at': n['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'time_ago': format_time_ago(n.get('created_at'))
            })
        
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return jsonify([])

@app.route('/notifications/mark-read/<notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    try:
        notification = db.notifications.find_one({'_id': ObjectId(notification_id)}) if db else None
        if notification and str(notification['user_id']) == session['user_id']:
            db.notifications.update_one(
                {'_id': ObjectId(notification_id)},
                {'$set': {'is_read': True}}
            )
            return jsonify({'success': True})
        
        return jsonify({'error': 'Unauthorized'}), 403
    except Exception as e:
        print(f"Error marking notification: {e}")
        return jsonify({'error': 'Unable to mark notification as read'}), 500

@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    try:
        db.notifications.update_many(
            {'user_id': ObjectId(session['user_id']), 'is_read': False},
            {'$set': {'is_read': True}}
        )
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error marking all notifications: {e}")
        return jsonify({'error': 'Unable to mark notifications as read'}), 500

@app.route('/unread-count', methods=['GET'])
@login_required
def get_unread_count():
    try:
        count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        }) if db else 0
        return jsonify({'count': count})
    except:
        return jsonify({'count': 0})

# ============== Admin Routes ==============

@app.route('/admin')
@admin_required
def admin_panel():
    try:
        total_requests = db.service_requests.count_documents({}) if db else 0
        pending_requests = db.service_requests.count_documents({'status': 'pending'}) if db else 0
        in_progress_requests = db.service_requests.count_documents({'status': 'in_progress'}) if db else 0
        completed_requests = db.service_requests.count_documents({'status': 'completed'}) if db else 0
        rejected_requests = db.service_requests.count_documents({'status': 'rejected'}) if db else 0
        
        total_users = db.users.count_documents({'role': 'user'}) if db else 0
        total_services = db.services.count_documents({'is_active': True}) if db else 0
        
        revenue_pipeline = [
            {'$match': {'status': 'completed'}},
            {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
        ]
        revenue_result = list(db.payment_transactions.aggregate(revenue_pipeline)) if db else []
        total_revenue = revenue_result[0]['total'] if revenue_result else 0
        
        all_requests = list(db.service_requests.find().sort('submitted_at', -1)) if db else []
        for req in all_requests:
            req['_id'] = str(req['_id'])
            user = get_user_by_id(req['user_id'])
            req['user'] = {'name': user['name'], 'phone': user['phone']} if user else None
            req['applicant_name'] = get_applicant_display_name(req)
        
        users = list(db.users.find()) if db else []
        for user in users:
            user['_id'] = str(user['_id'])
            user['requests'] = list(db.service_requests.find({'user_id': ObjectId(user['_id'])})) if db else []
        
        payments = list(db.payment_transactions.find().sort('created_at', -1)) if db else []
        for payment in payments:
            payment['_id'] = str(payment['_id'])
            user = get_user_by_id(payment['user_id'])
            service_request = db.service_requests.find_one({'_id': payment['request_id']}) if db else None
            payment['user'] = {'name': user['name']} if user else None
            payment['service_name'] = service_request['service_name'] if service_request else 'N/A'
        
        services = list(db.services.find()) if db else []
        for service in services:
            service['_id'] = str(service['_id'])
        
        service_names = list(set([req.get('service_name') for req in all_requests if req.get('service_name')]))
        
        admin_notifications = list(db.notifications.find(
            {'user_id': ObjectId(session['user_id'])}
        ).sort('created_at', -1).limit(20)) if db else []
        
        unread_count = db.notifications.count_documents({
            'user_id': ObjectId(session['user_id']),
            'is_read': False
        }) if db else 0
        
        stats = {
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'in_progress_requests': in_progress_requests,
            'completed_requests': completed_requests,
            'rejected_requests': rejected_requests,
            'total_users': total_users,
            'total_revenue': total_revenue,
            'total_services': total_services
        }
        
        return render_template('admin.html',
                             requests=all_requests,
                             users=users,
                             payments=payments,
                             services=services,
                             stats=stats,
                             notifications=admin_notifications,
                             unread_count=unread_count,
                             service_names=service_names,
                             filters={})
    except Exception as e:
        print(f"Error loading admin panel: {e}")
        traceback.print_exc()
        flash('Unable to load admin panel.', 'danger')
        return redirect(url_for('index'))

@app.route('/admin/update-status/<request_id>', methods=['POST'])
@admin_required
def update_status(request_id):
    try:
        data = request.get_json()
        status = data.get('status')
        remarks = data.get('remarks', '')
        
        service_request = db.service_requests.find_one({'_id': ObjectId(request_id)}) if db else None
        if not service_request:
            return jsonify({'success': False, 'message': 'Request not found'}), 404
        
        db.service_requests.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {
                'status': status,
                'admin_remarks': remarks,
                'processed_at': datetime.now(timezone.utc)
            }}
        )
        
        status_titles = {
            'in_progress': 'Application Under Review',
            'completed': 'Application Approved ✅',
            'rejected': 'Application Update'
        }
        
        status_messages = {
            'in_progress': 'Your application has been received and is being processed by our team.',
            'completed': 'Your application has been approved and processed successfully!',
            'rejected': 'Your application has been reviewed. Please check the remarks for more information.'
        }
        
        title = status_titles.get(status, f'Status Updated: {status}')
        message = status_messages.get(status, f'Your application status has been updated to {status}')
        if remarks:
            message += f'\n\nRemarks: {remarks}'
        
        db.service_requests.update_one(
            {'_id': ObjectId(request_id)},
            {'$push': {
                'timeline': {
                    'title': title,
                    'description': message,
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'completed': status == 'completed'
                }
            }}
        )
        
        create_notification(
            service_request['user_id'],
            request_id,
            title,
            message,
            'success' if status == 'completed' else 'info'
        )
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating status: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/request-details/<request_id>')
@admin_required
def admin_request_details(request_id):
    try:
        service_request = db.service_requests.find_one({'_id': ObjectId(request_id)}) if db else None
        if not service_request:
            return jsonify({'error': 'Request not found'}), 404
        
        documents = list(db.request_documents.find({'request_id': ObjectId(request_id)})) if db else []
        for doc in documents:
            doc['_id'] = str(doc['_id'])
            if isinstance(doc.get('uploaded_at'), datetime):
                doc['uploaded_at'] = doc['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        user = get_user_by_id(service_request['user_id'])
        
        request_dict = {
            'id': str(service_request['_id']),
            'reference_number': service_request['reference_number'],
            'service_name': service_request['service_name'],
            'service_type': service_request['service_type'],
            'status': service_request['status'],
            'payment_status': service_request['payment_status'],
            'amount': service_request['amount'],
            'submitted_at': service_request['submitted_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(service_request['submitted_at'], datetime) else str(service_request['submitted_at']),
            'processed_at': service_request['processed_at'].strftime('%Y-%m-%d %H:%M:%S') if service_request.get('processed_at') and isinstance(service_request['processed_at'], datetime) else None,
            'admin_remarks': service_request.get('admin_remarks', ''),
            'applicant_name': service_request.get('applicant_name', get_applicant_display_name(service_request)),
            'applicant_dob': service_request.get('applicant_dob', ''),
            'applicant_gender': service_request.get('applicant_gender', ''),
            'applicant_category': service_request.get('applicant_category', ''),
            'applicant_address': service_request.get('applicant_address', ''),
            'applicant_city': service_request.get('applicant_city', ''),
            'applicant_state': service_request.get('applicant_state', ''),
            'applicant_pincode': service_request.get('applicant_pincode', ''),
            'applicant_email': service_request.get('applicant_email', ''),
            'qualification': service_request.get('qualification', ''),
            'institute_name': service_request.get('institute_name', ''),
            'course_name': service_request.get('course_name', ''),
            'passing_year': service_request.get('passing_year', ''),
            'percentage': service_request.get('percentage', ''),
            'additional_details': service_request.get('additional_details', ''),
            'timeline': service_request.get('timeline', [])
        }
        
        if service_request.get('details'):
            try:
                details_data = json.loads(service_request['details'])
                request_dict['details_data'] = details_data
            except:
                pass
        
        return jsonify({
            'request': request_dict,
            'documents': documents,
            'user': {
                'name': user['name'] if user else 'N/A',
                'phone': user['phone'] if user else 'N/A',
                'email': user.get('email', 'N/A') if user else 'N/A'
            }
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/add-service', methods=['POST'])
@admin_required
def add_service():
    try:
        data = request.get_json()
        
        slug = data.get('name', '').lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        
        if db.services.find_one({'slug': slug}):
            return jsonify({'success': False, 'message': 'Service with similar name already exists'}), 400
        
        service = {
            'category': data.get('category'),
            'name': data.get('name'),
            'slug': slug,
            'description': data.get('description'),
            'eligibility': data.get('eligibility', ''),
            'documents_required': data.get('documents_required', ''),
            'instructions': data.get('instructions', ''),
            'processing_time': data.get('processing_time', '7-10 working days'),
            'service_charge': float(data.get('service_charge', 0)),
            'convenience_fee_percent': float(data.get('convenience_fee_percent', 2)),
            'gst_percent': float(data.get('gst_percent', 18)),
            'is_active': True,
            'icon': data.get('icon', 'fas fa-file-alt'),
            'created_at': datetime.now(timezone.utc)
        }
        
        db.services.insert_one(service)
        
        users = list(db.users.find({'role': 'user'})) if db else []
        for user in users:
            create_notification(
                user['_id'],
                None,
                'New Service Added! 🎉',
                f'A new service "{data.get("name")}" has been added to our platform.',
                'info'
            )
        
        return jsonify({'success': True, 'message': 'Service added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/get-pending-count')
@admin_required
def get_pending_count():
    try:
        count = db.service_requests.count_documents({'status': 'pending'}) if db else 0
        return jsonify({'count': count})
    except:
        return jsonify({'count': 0})

@app.route('/admin/send-summary', methods=['POST'])
@admin_required
def send_summary():
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=999999)
        
        today_applications = db.service_requests.count_documents({
            'submitted_at': {'$gte': today_start, '$lte': today_end}
        }) if db else 0
        
        pending_applications = db.service_requests.count_documents({'status': 'pending'}) if db else 0
        
        create_notification(
            ObjectId(session['user_id']),
            None,
            'Daily Summary Report 📊',
            f"Today's Summary:\n• New Applications: {today_applications}\n• Pending Applications: {pending_applications}\n• Total Users: {db.users.count_documents({'role': 'user'}) if db else 0}",
            'info'
        )
        
        return jsonify({'success': True, 'message': 'Summary sent'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============== Export Routes ==============

@app.route('/export/applications/csv')
@admin_required
def export_applications_csv():
    try:
        applications = list(db.service_requests.find().sort('submitted_at', -1)) if db else []
        
        output = BytesIO()
        writer = csv.writer(output)
        writer.writerow(['Reference Number', 'Applicant Name', 'Service Name', 'Status', 'Payment Status', 'Amount', 'Submitted Date', 'User Phone'])
        
        for app in applications:
            user = get_user_by_id(app['user_id'])
            writer.writerow([
                app['reference_number'],
                get_applicant_display_name(app),
                app['service_name'],
                app['status'],
                app['payment_status'],
                app['amount'],
                app['submitted_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(app['submitted_at'], datetime) else str(app['submitted_at']),
                user['phone'] if user else ''
            ])
        
        output.seek(0)
        return send_file(
            output,
            download_name=f'applications_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            as_attachment=True,
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/revenue/csv')
@admin_required
def export_revenue_csv():
    try:
        payments = list(db.payment_transactions.find().sort('created_at', -1)) if db else []
        
        output = BytesIO()
        writer = csv.writer(output)
        writer.writerow(['Transaction ID', 'User Name', 'User Phone', 'Service Name', 'Amount', 'Payment Method', 'Status', 'Date'])
        
        for payment in payments:
            user = get_user_by_id(payment['user_id'])
            service_request = db.service_requests.find_one({'_id': payment['request_id']}) if db else None
            writer.writerow([
                payment['transaction_id'],
                user['name'] if user else '',
                user['phone'] if user else '',
                service_request['service_name'] if service_request else '',
                payment['amount'],
                payment['payment_method'],
                payment['status'],
                payment['created_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(payment['created_at'], datetime) else str(payment['created_at'])
            ])
        
        output.seek(0)
        return send_file(
            output,
            download_name=f'revenue_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            as_attachment=True,
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/users/csv')
@admin_required
def export_users_csv():
    try:
        users = list(db.users.find()) if db else []
        
        output = BytesIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Phone', 'Email', 'Role', 'Applications Count', 'Joined Date', 'Last Login'])
        
        for user in users:
            request_count = db.service_requests.count_documents({'user_id': user['_id']}) if db else 0
            writer.writerow([
                user['name'],
                user['phone'],
                user.get('email', ''),
                user['role'],
                request_count,
                user['created_at'].strftime('%Y-%m-%d') if isinstance(user['created_at'], datetime) else str(user['created_at']),
                user['last_login'].strftime('%Y-%m-%d %H:%M') if user.get('last_login') and isinstance(user['last_login'], datetime) else ''
            ])
        
        output.seek(0)
        return send_file(
            output,
            download_name=f'users_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            as_attachment=True,
            mimetype='text/csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============== Error Handlers ==============

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

# ============== Health Check ==============

@app.route('/health')
def health_check():
    status = {
        'status': 'healthy',
        'database': 'connected' if db else 'disconnected',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    return jsonify(status)

# ============== Application Entry Point ==============

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("DIGISERVE ESEVA PORTAL - PROFESSIONAL EDITION")
    print("=" * 60)
    
    init_db()
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"\n✅ Application started on port {port}!")
    print("=" * 60 + "\n")
    app.run(debug=debug, host='0.0.0.0', port=port)