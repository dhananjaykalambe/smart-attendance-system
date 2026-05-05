# utils/__init__.py
"""Utility modules for Smart Attendance System"""
from .database import db, init_db, get_db
from .auth import login_required, faculty_required, student_required, admin_required
from .helpers import *
from .pdf_export import *