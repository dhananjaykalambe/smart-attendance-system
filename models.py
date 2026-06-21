from datetime import datetime, timezone, timedelta
from bson import ObjectId
import random
import json

class DateTimeEncoder:
    @staticmethod
    def to_iso(dt):
        """Convert datetime to ISO format string with timezone info"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # Assume UTC for naive datetime
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    
    @staticmethod
    def from_iso(iso_string):
        """Convert ISO format string to datetime"""
        if iso_string is None:
            return None
        return datetime.fromisoformat(iso_string)

class BaseModel:
    @staticmethod
    def to_dict(doc):
        """Convert MongoDB document to dictionary with string ID and formatted dates"""
        if doc is None:
            return None
        doc_dict = dict(doc)
        if '_id' in doc_dict:
            doc_dict['id'] = str(doc_dict.pop('_id'))
        
        # Convert datetime fields to readable format
        for field in ['created_at', 'last_login', 'processed_at', 'submitted_at', 'uploaded_at']:
            if field in doc_dict and doc_dict[field]:
                if isinstance(doc_dict[field], datetime):
                    # Format as "YYYY-MM-DD HH:MM:SS" without milliseconds
                    doc_dict[field] = doc_dict[field].strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(doc_dict[field], str):
                    # Already string, keep as is
                    pass
        
        # Handle nested dates in notifications
        if 'created_at' in doc_dict and isinstance(doc_dict['created_at'], str):
            pass  # Already formatted
            
        return doc_dict

class User(BaseModel):
    COLLECTION = 'users'
    
    @staticmethod
    def create(name, phone, email=None, role='user', address=None, city=None, state=None, pincode=None):
        """Create a new user document"""
        return {
            'name': name,
            'phone': phone,
            'email': email,
            'role': role,
            'is_active': True,
            'created_at': datetime.now(timezone.utc),
            'last_login': None,
            'address': address,
            'city': city,
            'state': state,
            'pincode': pincode
        }
    
    @staticmethod
    def to_dict(user):
        """Convert user document to dictionary with formatted dates"""
        if user is None:
            return None
        user_dict = BaseModel.to_dict(user)
        return user_dict

class Service(BaseModel):
    COLLECTION = 'services'
    
    @staticmethod
    def create(category, name, slug, description, eligibility=None, documents_required=None, 
               instructions=None, processing_time=None, service_charge=0, icon='fas fa-file-alt'):
        """Create a new service document"""
        return {
            'category': category,
            'name': name,
            'slug': slug,
            'description': description,
            'eligibility': eligibility,
            'documents_required': documents_required,
            'instructions': instructions,
            'processing_time': processing_time,
            'service_charge': service_charge,
            'is_active': True,
            'icon': icon,
            'created_at': datetime.now(timezone.utc)
        }

class ServiceRequest(BaseModel):
    COLLECTION = 'service_requests'
    
    @staticmethod
    def generate_reference_number():
        """Generate unique reference number"""
        return f'DS{datetime.now().strftime("%Y%m%d%H%M%S")}{random.randint(1000, 9999)}'
    
    @staticmethod
    def create(user_id, service_id, service_type, service_name, details, amount=0, 
               sub_service=None, applicant_name=None, applicant_dob=None, applicant_gender=None,
               applicant_category=None, applicant_address=None, applicant_city=None, 
               applicant_state=None, applicant_pincode=None, applicant_email=None,
               qualification=None, institute_name=None, course_name=None, 
               passing_year=None, percentage=None, additional_details=None):
        """Create a new service request document"""
        return {
            'user_id': user_id,
            'service_id': service_id,
            'service_type': service_type,
            'service_name': service_name,
            'sub_service': sub_service,
            'details': details,
            'amount': amount,
            'payment_status': 'pending',
            'status': 'pending',
            'reference_number': ServiceRequest.generate_reference_number(),
            'submitted_at': datetime.now(timezone.utc),
            'processed_at': None,
            'admin_remarks': None,
            # Applicant details
            'applicant_name': applicant_name,
            'applicant_dob': applicant_dob,
            'applicant_gender': applicant_gender,
            'applicant_category': applicant_category,
            'applicant_address': applicant_address,
            'applicant_city': applicant_city,
            'applicant_state': applicant_state,
            'applicant_pincode': applicant_pincode,
            'applicant_email': applicant_email,
            'qualification': qualification,
            'institute_name': institute_name,
            'course_name': course_name,
            'passing_year': passing_year,
            'percentage': percentage,
            'additional_details': additional_details
        }
    
    @staticmethod
    def to_dict(request, include_details_json=True):
        """Convert request to formatted dictionary with readable data"""
        if request is None:
            return None
        
        request_dict = BaseModel.to_dict(request)
        
        # Try to parse details JSON if it exists
        if include_details_json and request_dict.get('details'):
            try:
                details_data = json.loads(request_dict['details'])
                request_dict['parsed_details'] = details_data
            except:
                pass
        
        # Ensure dates are formatted properly
        if 'submitted_at' in request_dict:
            if isinstance(request_dict['submitted_at'], datetime):
                request_dict['submitted_at'] = request_dict['submitted_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        if 'processed_at' in request_dict and request_dict['processed_at']:
            if isinstance(request_dict['processed_at'], datetime):
                request_dict['processed_at'] = request_dict['processed_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return request_dict
    
    @staticmethod
    def format_for_display(request):
        """Format the request data for professional display"""
        if not request:
            return {}
        
        # Create a clean, formatted display version
        display_data = {
            'reference_number': request.get('reference_number', 'N/A'),
            'service_name': request.get('service_name', 'N/A'),
            'status': request.get('status', 'pending').upper(),
            'payment_status': request.get('payment_status', 'pending').upper(),
            'amount': f"₹{request.get('amount', 0):.2f}",
            'submitted_at': request.get('submitted_at', 'N/A'),
            'processed_at': request.get('processed_at', 'Not processed yet'),
            'admin_remarks': request.get('admin_remarks', 'No remarks'),
        }
        
        # Applicant Information section
        display_data['applicant_info'] = {
            'Full Name': request.get('applicant_name', 'Not provided'),
            'Date of Birth': request.get('applicant_dob', 'Not provided'),
            'Gender': request.get('applicant_gender', 'Not provided'),
            'Category': request.get('applicant_category', 'Not provided'),
            'Email': request.get('applicant_email', 'Not provided'),
            'Address': request.get('applicant_address', 'Not provided'),
            'City': request.get('applicant_city', 'Not provided'),
            'State': request.get('applicant_state', 'Not provided'),
            'Pincode': request.get('applicant_pincode', 'Not provided'),
        }
        
        # Educational Information section
        if any([request.get('qualification'), request.get('institute_name'), 
                request.get('course_name'), request.get('passing_year'), request.get('percentage')]):
            display_data['educational_info'] = {
                'Highest Qualification': request.get('qualification', 'Not provided'),
                'Institute/College Name': request.get('institute_name', 'Not provided'),
                'Course/Exam Name': request.get('course_name', 'Not provided'),
                'Passing/Appearing Year': request.get('passing_year', 'Not provided'),
                'Percentage/CGPA': request.get('percentage', 'Not provided'),
            }
        
        # Additional Details section
        if request.get('additional_details'):
            display_data['additional_details'] = request.get('additional_details')
        
        return display_data

class RequestDocument(BaseModel):
    COLLECTION = 'request_documents'
    
    @staticmethod
    def create(request_id, document_type, original_filename, stored_filename, file_path, file_size):
        """Create a document record"""
        return {
            'request_id': request_id,
            'document_type': document_type,
            'original_filename': original_filename,
            'stored_filename': stored_filename,
            'file_path': file_path,
            'file_size': file_size,
            'uploaded_at': datetime.now(timezone.utc)
        }

class PaymentTransaction(BaseModel):
    COLLECTION = 'payment_transactions'
    
    @staticmethod
    def create(user_id, request_id, transaction_id, amount, payment_method='online', status='pending'):
        """Create a payment record"""
        return {
            'user_id': user_id,
            'request_id': request_id,
            'transaction_id': transaction_id,
            'amount': amount,
            'payment_method': payment_method,
            'status': status,
            'created_at': datetime.now(timezone.utc)
        }

class Notification(BaseModel):
    COLLECTION = 'notifications'
    
    @staticmethod
    def create(user_id, request_id, title, message, type='info'):
        """Create a notification"""
        return {
            'user_id': user_id,
            'request_id': request_id,
            'title': title,
            'message': message,
            'type': type,
            'is_read': False,
            'created_at': datetime.now(timezone.utc)
        }
    
    @staticmethod
    def to_dict(notification):
        """Convert notification to dictionary with formatted date"""
        if notification is None:
            return None
        notif_dict = BaseModel.to_dict(notification)
        
        # Format time for display (e.g., "2 hours ago" or specific date)
        if 'created_at' in notif_dict:
            created_at = notif_dict['created_at']
            if isinstance(created_at, str):
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    notif_dict['time_ago'] = Notification.time_ago(dt)
                except:
                    notif_dict['time_ago'] = created_at
            elif isinstance(created_at, datetime):
                notif_dict['time_ago'] = Notification.time_ago(created_at)
                notif_dict['created_at'] = created_at.strftime('%Y-%m-%d %H:%M:%S')
        
        return notif_dict
    
    @staticmethod
    def time_ago(dt):
        """Calculate time ago string"""
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