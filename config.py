import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'digiserve-secret-key-2026-mongo')
    
    # MongoDB Configuration
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    MONGO_DB = os.environ.get('MONGO_DB', 'digiserve')
    
    # File Upload Configuration
    UPLOAD_FOLDER = 'uploads/'
    DOCUMENT_FOLDER = 'uploads/documents/'
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Admin Configuration
    ADMIN_PHONE = '9999999999'
    ADMIN_NAME = 'Admin User'
    ADMIN_EMAIL = 'admin@digiserve.com'
    
    # Contact Information
    CONTACT_PHONE = '9421456959'
    CONTACT_EMAIL = 'support@digiserve.com'
    
    # Company Info
    COMPANY_NAME = 'DigiSoft'
    COPYRIGHT_YEAR = '2026'
    COPYRIGHT_HOLDER = 'DK'

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # In production, use environment variables for MongoDB URI

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}