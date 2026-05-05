# utils/auth.py
# ====================================================================
# AUTHENTICATION DECORATORS
# ====================================================================

from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def faculty_required(f):
    """Decorator to require faculty role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'faculty':
            flash('Access Denied: Faculty only', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    """Decorator to require student role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'student':
            flash('Access Denied: Students only', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Access Denied: Admin only', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function