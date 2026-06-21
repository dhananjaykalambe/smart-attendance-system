# database.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class ServiceRequest(db.Model):
    __tablename__ = 'service_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    service_name = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    priority = db.Column(db.String(20), default='normal')
    reference_number = db.Column(db.String(50), unique=True, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    attachments = db.Column(db.String(500))
    
    user = db.relationship('User', backref='requests', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'reference_number': self.reference_number,
            'service_type': self.service_type,
            'service_name': self.service_name,
            'details': self.details,
            'status': self.status,
            'priority': self.priority,
            'submitted_at': self.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
            'processed_at': self.processed_at.strftime('%Y-%m-%d %H:%M:%S') if self.processed_at else None
        }

class Feedback(db.Model):
    __tablename__ = 'feedbacks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='feedbacks')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_name': self.user.name,
            'rating': self.rating,
            'message': self.message,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }