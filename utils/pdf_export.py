# utils/pdf_export.py
# ====================================================================
# PDF EXPORT FUNCTIONS
# ====================================================================

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime
import io
from flask import send_file

def get_college_header_text(db):
    """Get college header for PDF"""
    settings = db.settings.find_one({})
    if settings:
        return settings.get('college_name', 'Priyadarshini Bhagwati College of Engineering')
    return 'Priyadarshini Bhagwati College of Engineering'

def create_pdf_response(buffer, filename):
    """Create PDF response"""
    buffer.seek(0)
    return send_file(buffer, download_name=filename, as_attachment=True, mimetype='application/pdf')

def export_attendance_report(session_id, db):
    """Export session attendance as PDF"""
    session_data = db.sessions.find_one({"session_id": session_id})
    if not session_data:
        return "Session not found"
    
    attendance_records = list(db.attendance.find({"session_id": session_id}).sort("time", 1))
    records = []
    for record in attendance_records:
        student = db.students.find_one({"roll_no": record['student_id']})
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
    
    # Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a1a2e'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#e94560'), fontName='Helvetica-Bold')
    
    college_name = get_college_header_text(db)
    elements.append(Paragraph(college_name, college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"Attendance Report - {session_data['subject']}", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Date:</b> {session_data['start_time'].strftime('%Y-%m-%d')} &nbsp;&nbsp; <b>Time:</b> {session_data['start_time'].strftime('%H:%M:%S')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Total Students Present:</b> {len(records)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Table
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Footer
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    return create_pdf_response(buffer, f"attendance_{session_id}.pdf")

def export_student_report(roll_no, db):
    """Export individual student report as PDF"""
    student = db.students.find_one({"roll_no": roll_no})
    if not student:
        return "Student not found"
    
    attendance_records = list(db.attendance.find({"student_id": roll_no}).sort("time", -1))
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
    
    for subject, data in subject_stats.items():
        data["percentage"] = round((data["attended"] / data["total"]) * 100, 2) if data["total"] > 0 else 0
    
    total_attended = len(attendance_records)
    total_sessions = len(all_sessions)
    overall_percentage = round((total_attended / total_sessions) * 100, 2) if total_sessions > 0 else 0
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    # Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a1a2e'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#e94560'), fontName='Helvetica-Bold')
    
    college_name = get_college_header_text(db)
    elements.append(Paragraph(college_name, college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Student Attendance Report", title_style))
    elements.append(Spacer(1, 12))
    
    # Student Info
    elements.append(Paragraph(f"<b>Name:</b> {student['name']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Roll Number:</b> {student['roll_no']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Branch:</b> {student['branch']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Overall Attendance:</b> {overall_percentage}%", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Subject-wise Table
    table_data = [['Subject', 'Attended', 'Total Classes', 'Percentage', 'Status']]
    for subject, data in subject_stats.items():
        status = "Good" if data['percentage'] >= 85 else "Average" if data['percentage'] >= 75 else "Needs Improvement"
        table_data.append([subject, str(data['attended']), str(data['total']), f"{data['percentage']}%", status])
    
    table = Table(table_data, colWidths=[100, 80, 80, 80, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Footer
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    return create_pdf_response(buffer, f"student_{roll_no}_report.pdf")

def export_all_students_report(db):
    """Export all students report as PDF"""
    students_list = list(db.students.find({}))
    all_sessions = list(db.sessions.find({}))
    
    total_sessions_dict = {}
    for session_item in all_sessions:
        subject = session_item['subject']
        total_sessions_dict[subject] = total_sessions_dict.get(subject, 0) + 1
    
    table_data = [['Roll No', 'Name', 'Branch', 'Overall %', 'Performance']]
    for student in students_list:
        total_attended = 0
        total_possible = 0
        for subject, total in total_sessions_dict.items():
            attended = db.attendance.count_documents({"student_id": student['roll_no'], "subject": subject})
            total_attended += attended
            total_possible += total
        overall = round((total_attended / total_possible) * 100, 2) if total_possible > 0 else 0
        performance = "Excellent" if overall >= 85 else "Good" if overall >= 75 else "Needs Improvement"
        table_data.append([student['roll_no'], student['name'], student['branch'], f"{overall}%", performance])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    
    # Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a1a2e'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#e94560'), fontName='Helvetica-Bold')
    
    college_name = get_college_header_text(db)
    elements.append(Paragraph(college_name, college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Complete Student Attendance Report", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Students:</b> {len(students_list)} &nbsp;&nbsp; <b>Total Sessions:</b> {len(all_sessions)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 120, 80, 80, 120])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Footer
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    return create_pdf_response(buffer, "all_students_report.pdf")

def export_subject_report(subject, db):
    """Export subject-wise report as PDF"""
    sessions_list = list(db.sessions.find({"subject": subject}))
    students_list = list(db.students.find({}))
    
    table_data = [['Roll No', 'Name', 'Branch', 'Attended', 'Total', 'Percentage', 'Status']]
    for student in students_list:
        attended = db.attendance.count_documents({"student_id": student['roll_no'], "subject": subject})
        percent = round((attended / len(sessions_list)) * 100, 2) if len(sessions_list) > 0 else 0
        status = "Good" if percent >= 85 else "Average" if percent >= 75 else "Low"
        table_data.append([student['roll_no'], student['name'], student['branch'], str(attended), str(len(sessions_list)), f"{percent}%", status])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    
    # Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a1a2e'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#e94560'), fontName='Helvetica-Bold')
    
    college_name = get_college_header_text(db)
    elements.append(Paragraph(college_name, college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"{subject} - Attendance Report", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Sessions:</b> {len(sessions_list)} &nbsp;&nbsp; <b>Total Students:</b> {len(students_list)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 100, 80, 70, 60, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Footer
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    return create_pdf_response(buffer, f"{subject}_report.pdf")

def export_overall_report(db):
    """Export overall report as PDF"""
    subjects = ["ML", "DS", "CD", "IPR", "EOII", "OE-1"]
    subject_stats = []
    for subject in subjects:
        sessions_count = db.sessions.count_documents({"subject": subject})
        attended_count = db.attendance.count_documents({"subject": subject})
        percent = round((attended_count / sessions_count) * 100, 2) if sessions_count > 0 else 0
        subject_stats.append({"subject": subject, "total": sessions_count, "attended": attended_count, "percentage": percent})
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    
    # Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a1a2e'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#e94560'), fontName='Helvetica-Bold')
    
    college_name = get_college_header_text(db)
    elements.append(Paragraph(college_name, college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Overall Attendance Report", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Students:</b> {db.students.count_documents({})} &nbsp;&nbsp; <b>Total Sessions:</b> {db.sessions.count_documents({})}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table_data = [['Subject', 'Total Sessions', 'Total Attendance', 'Percentage', 'Performance']]
    for stat in subject_stats:
        performance = "Good" if stat['percentage'] >= 85 else "Average" if stat['percentage'] >= 75 else "Low"
        table_data.append([stat['subject'], str(stat['total']), str(stat['attended']), f"{stat['percentage']}%", performance])
    
    table = Table(table_data, colWidths=[100, 100, 100, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Footer
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    return create_pdf_response(buffer, "overall_report.pdf")

def export_all_attendance_report(session, db):
    """Export all attendance records as PDF"""
    if session.get('role') == 'student':
        records = list(db.attendance.find({"student_id": session['user_id']}).sort("time", -1))
    else:
        records = list(db.attendance.find({}).sort("time", -1))
    
    table_data = [['Roll No', 'Name', 'Branch', 'Session ID', 'Subject', 'Date & Time']]
    for record in records:
        student = db.students.find_one({"roll_no": record['student_id']})
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
    
    # Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a1a2e'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#e94560'), fontName='Helvetica-Bold')
    
    college_name = get_college_header_text(db)
    elements.append(Paragraph(college_name, college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Complete Attendance Records", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Records:</b> {len(records)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 100, 80, 100, 80, 120])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Footer
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    return create_pdf_response(buffer, "all_attendance_records.pdf")

def export_faculty_report(db):
    """Export faculty list as PDF"""
    faculties = list(db.faculty.find({}).sort("faculty_id", 1))
    table_data = [['Faculty ID', 'Name', 'Email', 'Department', 'Created Date']]
    for faculty in faculties:
        table_data.append([faculty['faculty_id'], faculty['name'], faculty['email'], faculty['department'],
                          faculty['created_at'].strftime('%Y-%m-%d') if faculty.get('created_at') else 'N/A'])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    
    # Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a1a2e'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#e94560'), fontName='Helvetica-Bold')
    
    college_name = get_college_header_text(db)
    elements.append(Paragraph(college_name, college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Faculty Directory", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Faculty:</b> {len(faculties)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 120, 150, 80, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Footer
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    return create_pdf_response(buffer, "faculty_list.pdf")

def export_students_directory(db):
    """Export students directory as PDF"""
    students_list = list(db.students.find({}).sort("roll_no", 1))
    table_data = [['Roll No', 'Name', 'Branch', 'Email', 'Year', 'Semester']]
    for student in students_list:
        table_data.append([student['roll_no'], student['name'], student['branch'], student.get('email', 'N/A'),
                          f"{student.get('year', 'N/A')} Year", f"Sem {student.get('semester', 'N/A')}"])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []
    
    # Header
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1, textColor=colors.HexColor('#1a1a2e'))
    college_style = ParagraphStyle('CollegeName', parent=styles['Normal'], fontSize=14, alignment=1, textColor=colors.HexColor('#e94560'), fontName='Helvetica-Bold')
    
    college_name = get_college_header_text(db)
    elements.append(Paragraph(college_name, college_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Student Directory", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Total Students:</b> {len(students_list)}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    table = Table(table_data, colWidths=[80, 120, 80, 120, 70, 70])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # Footer
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, textColor=colors.grey, alignment=0)
    elements.append(Paragraph(f"Report Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", timestamp_style))
    
    doc.build(elements)
    return create_pdf_response(buffer, "student_list.pdf")