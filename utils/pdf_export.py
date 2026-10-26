# utils/pdf_export.py
# ====================================================================
# PDF EXPORT FUNCTIONS - PROFESSIONAL DESIGN
# ====================================================================

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter, A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import inch, mm
from datetime import datetime
import io
from flask import send_file, session

# ====================================================================
# COLOR PALETTE
# ====================================================================
PRIMARY = colors.HexColor('#1a237e')
PRIMARY_LIGHT = colors.HexColor('#283593')
PRIMARY_SOFT = colors.HexColor('#e8eaf6')
ACCENT = colors.HexColor('#3f51b5')
DARK_TEXT = colors.HexColor('#0d1445')
GRAY_TEXT = colors.HexColor('#424242')
MUTED = colors.HexColor('#757575')
BORDER = colors.HexColor('#c5cae9')
ROW_ALT = colors.HexColor('#f5f6fa')
SUCCESS = colors.HexColor('#1b5e20')
DANGER = colors.HexColor('#b71c1c')


# ====================================================================
# HELPERS
# ====================================================================

def get_college_info(db):
    """Get college header info from settings"""
    settings = db.settings.find_one({}) or {}
    return {
        'name': settings.get('college_name', 'Priyadarshini Bhagwati College of Engineering'),
        'location': settings.get('college_location', 'Nagpur'),
        'year': settings.get('academic_year', '2024-25')
    }


def get_exporter_name():
    """Get current logged-in faculty name from session"""
    return session.get('user_name', 'Faculty')


def create_pdf_response(buffer, filename):
    buffer.seek(0)
    return send_file(buffer, download_name=filename, as_attachment=True, mimetype='application/pdf')


def build_styles():
    """Build all paragraph styles used across reports"""
    styles = getSampleStyleSheet()

    return {
        'college': ParagraphStyle(
            'College', parent=styles['Normal'],
            fontSize=16, alignment=TA_CENTER,
            textColor=PRIMARY, fontName='Helvetica-Bold',
            spaceAfter=2
        ),
        'location': ParagraphStyle(
            'Location', parent=styles['Normal'],
            fontSize=10, alignment=TA_CENTER,
            textColor=MUTED, fontName='Helvetica',
            spaceAfter=8
        ),
        'report_title': ParagraphStyle(
            'ReportTitle', parent=styles['Heading1'],
            fontSize=15, alignment=TA_CENTER,
            textColor=colors.white, fontName='Helvetica-Bold',
            spaceAfter=0, spaceBefore=0
        ),
        'section': ParagraphStyle(
            'Section', parent=styles['Normal'],
            fontSize=11, alignment=TA_LEFT,
            textColor=PRIMARY, fontName='Helvetica-Bold',
            spaceBefore=10, spaceAfter=6
        ),
        'body': ParagraphStyle(
            'Body', parent=styles['Normal'],
            fontSize=9.5, alignment=TA_LEFT,
            textColor=GRAY_TEXT, fontName='Helvetica',
            leading=13
        ),
        'body_bold': ParagraphStyle(
            'BodyBold', parent=styles['Normal'],
            fontSize=9.5, alignment=TA_LEFT,
            textColor=DARK_TEXT, fontName='Helvetica-Bold',
            leading=13
        ),
        'meta': ParagraphStyle(
            'Meta', parent=styles['Normal'],
            fontSize=9, alignment=TA_LEFT,
            textColor=GRAY_TEXT, fontName='Helvetica'
        ),
        'timestamp': ParagraphStyle(
            'Timestamp', parent=styles['Normal'],
            fontSize=8, alignment=TA_RIGHT,
            textColor=MUTED, fontName='Helvetica-Oblique'
        ),
        'signature_label': ParagraphStyle(
            'SigLabel', parent=styles['Normal'],
            fontSize=9, alignment=TA_CENTER,
            textColor=DARK_TEXT, fontName='Helvetica-Bold'
        ),
        'signature_sub': ParagraphStyle(
            'SigSub', parent=styles['Normal'],
            fontSize=8, alignment=TA_CENTER,
            textColor=MUTED, fontName='Helvetica'
        ),
    }


def build_header(db, title, subtitle_lines, styles):
    """Build a consistent attractive header block"""
    info = get_college_info(db)
    elements = []

    # College name + location
    elements.append(Paragraph(info['name'].upper(), styles['college']))
    elements.append(Paragraph(info['location'], styles['location']))

    # Title bar (colored strip with white text)
    title_table = Table(
        [[Paragraph(title, styles['report_title'])]],
        colWidths=[7.3 * inch]
    )
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 8))

    # Meta lines (Date, Exporter, etc.)
    meta_data = []
    for line in subtitle_lines:
        meta_data.append([Paragraph(line, styles['meta'])])

    if meta_data:
        meta_table = Table(meta_data, colWidths=[7.3 * inch])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), PRIMARY_SOFT),
            ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(meta_table)

    elements.append(Spacer(1, 12))
    return elements


def build_data_table(table_data, col_widths, styles, header_color=PRIMARY):
    """Build a well-styled data table with alternating rows"""
    if len(table_data) <= 1:
        # Only header, no data
        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        return tbl

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_commands = [
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 9),

        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('TEXTCOLOR', (0, 1), (-1, -1), DARK_TEXT),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),

        # Borders
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, PRIMARY),
        ('BOX', (0, 0), (-1, -1), 0.8, PRIMARY),
    ]

    # Alternating row colors
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_commands.append(('BACKGROUND', (0, i), (-1, i), ROW_ALT))

    tbl.setStyle(TableStyle(style_commands))
    return tbl


def build_signatures(styles, hod_name='Head of Department', faculty_name=None):
    """Build HOD (left) and Faculty (right) signature spots"""
    if faculty_name is None:
        faculty_name = get_exporter_name()

    sig_data = [[
        # Left: HOD
        Paragraph(
            f'<br/><br/><br/>__________________________<br/>'
            f'<b>{hod_name}</b><br/>'
            f'<font size="8" color="#757575">Head of Department</font>',
            ParagraphStyle('HODSig', parent=styles['signature_label'],
                           alignment=TA_CENTER, leading=14)
        ),
        # Right: Faculty
        Paragraph(
            f'<br/><br/><br/>__________________________<br/>'
            f'<b>{faculty_name}</b><br/>'
            f'<font size="8" color="#757575">Faculty (Exporter)</font>',
            ParagraphStyle('FacSig', parent=styles['signature_label'],
                           alignment=TA_CENTER, leading=14)
        ),
    ]]

    sig_table = Table(sig_data, colWidths=[3.65 * inch, 3.65 * inch])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    return sig_table


def build_footer(styles):
    """Build the footer timestamp line"""
    return Paragraph(
        f'Report generated on: {datetime.now().strftime("%d %b %Y, %I:%M %p")}  |  '
        f'Smart Attendance System',
        styles['timestamp']
    )


def build_report(db, title, subtitle_lines, table_data, col_widths,
                 filename, hod_name='Head of Department'):
    """Generic report builder - used by all report types"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title=title,
    )
    styles = build_styles()
    elements = []

    # Header
    elements.extend(build_header(db, title, subtitle_lines, styles))

    # Data table
    elements.append(build_data_table(table_data, col_widths, styles))

    elements.append(Spacer(1, 24))

    # Signatures
    elements.append(build_signatures(styles, hod_name=hod_name))

    elements.append(Spacer(1, 16))

    # Footer
    elements.append(build_footer(styles))

    doc.build(elements)
    return create_pdf_response(buffer, filename)


# ====================================================================
# REPORT FUNCTIONS
# ====================================================================

def export_attendance_report(session_id, db):
    """Export session attendance as PDF"""
    session_data = db.sessions.find_one({"session_id": session_id})
    if not session_data:
        return "Session not found"

    attendance_records = list(db.attendance.find({"session_id": session_id}).sort("time", 1))

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Time', 'IP Address']]
    for idx, record in enumerate(attendance_records, 1):
        student = db.students.find_one({"roll_no": record['student_id']})
        time_str = record['time'].strftime('%I:%M %p') if record.get('time') else 'N/A'
        table_data.append([
            str(idx),
            record['student_id'],
            student['name'] if student else 'Unknown',
            student['branch'] if student else '-',
            time_str,
            record.get('ip_address', 'N/A'),
        ])

    info = get_college_info(db)
    subtitle_lines = [
        f'<b>Session ID:</b> {session_id}  &nbsp;&nbsp;  '
        f'<b>Subject:</b> {session_data["subject"]}  &nbsp;&nbsp;  '
        f'<b>Date:</b> {session_data["start_time"].strftime("%d %b %Y")}',
        f'<b>Start Time:</b> {session_data["start_time"].strftime("%I:%M %p")}  &nbsp;&nbsp;  '
        f'<b>Duration:</b> {session_data.get("duration", "N/A")} min  &nbsp;&nbsp;  '
        f'<b>Total Present:</b> {len(attendance_records)}',
    ]

    return build_report(
        db,
        title=f'ATTENDANCE REPORT — {session_data["subject"]}',
        subtitle_lines=subtitle_lines,
        table_data=table_data,
        col_widths=[0.4 * inch, 1.0 * inch, 1.8 * inch, 0.9 * inch, 1.1 * inch, 1.6 * inch],
        filename=f'attendance_{session_id}.pdf',
    )


def export_student_report(roll_no, db):
    """Export individual student report as PDF"""
    student = db.students.find_one({"roll_no": roll_no})
    if not student:
        return "Student not found"

    attendance_records = list(db.attendance.find({"student_id": roll_no}))
    all_sessions = list(db.sessions.find({}))

    subject_stats = {}
    for s in all_sessions:
        subj = s.get("subject")
        if subj:
            subject_stats.setdefault(subj, {"total": 0, "attended": 0})
            subject_stats[subj]["total"] += 1

    for record in attendance_records:
        subj = record.get("subject")
        if subj in subject_stats:
            subject_stats[subj]["attended"] += 1

    for subj, d in subject_stats.items():
        d["percentage"] = round((d["attended"] / d["total"]) * 100, 2) if d["total"] > 0 else 0

    total_attended = len(attendance_records)
    total_sessions = len(all_sessions)
    overall = round((total_attended / total_sessions) * 100, 2) if total_sessions > 0 else 0

    table_data = [['#', 'Subject', 'Attended', 'Total', 'Percentage', 'Status']]
    for idx, (subj, d) in enumerate(subject_stats.items(), 1):
        status = 'Good' if d['percentage'] >= 85 else ('Average' if d['percentage'] >= 75 else 'Needs Improvement')
        table_data.append([
            str(idx), subj, str(d['attended']), str(d['total']),
            f"{d['percentage']}%", status
        ])
    table_data.append(['', 'OVERALL', str(total_attended), str(total_sessions), f"{overall}%", ''])

    subtitle_lines = [
        f'<b>Name:</b> {student["name"]}  &nbsp;&nbsp;  '
        f'<b>Roll No:</b> {student["roll_no"]}  &nbsp;&nbsp;  '
        f'<b>Branch:</b> {student["branch"]}',
        f'<b>Overall Attendance:</b> {overall}%  &nbsp;&nbsp;  '
        f'<b>Classes Attended:</b> {total_attended} / {total_sessions}',
    ]

    return build_report(
        db,
        title='STUDENT ATTENDANCE REPORT',
        subtitle_lines=subtitle_lines,
        table_data=table_data,
        col_widths=[0.5 * inch, 2.0 * inch, 1.0 * inch, 1.0 * inch, 1.2 * inch, 1.8 * inch],
        filename=f'student_{roll_no}_report.pdf',
    )


def export_all_students_report(db):
    """Export all students report as PDF"""
    students_list = list(db.students.find({}))
    all_sessions = list(db.sessions.find({}))

    total_sessions_dict = {}
    for s in all_sessions:
        subj = s.get('subject')
        total_sessions_dict[subj] = total_sessions_dict.get(subj, 0) + 1

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Attended', 'Total', 'Overall %', 'Performance']]
    for idx, student in enumerate(students_list, 1):
        attended_total = 0
        possible_total = 0
        for subj, total in total_sessions_dict.items():
            attended_total += db.attendance.count_documents(
                {"student_id": student['roll_no'], "subject": subj}
            )
            possible_total += total
        overall = round((attended_total / possible_total) * 100, 2) if possible_total > 0 else 0
        perf = 'Excellent' if overall >= 85 else ('Good' if overall >= 75 else 'Needs Improvement')
        table_data.append([
            str(idx), student['roll_no'], student['name'], student['branch'],
            str(attended_total), str(possible_total), f"{overall}%", perf
        ])

    subtitle_lines = [
        f'<b>Total Students:</b> {len(students_list)}  &nbsp;&nbsp;  '
        f'<b>Total Sessions:</b> {len(all_sessions)}',
    ]

    return build_report(
        db,
        title='COMPLETE STUDENT ATTENDANCE REPORT',
        subtitle_lines=subtitle_lines,
        table_data=table_data,
        col_widths=[0.4 * inch, 0.9 * inch, 1.7 * inch, 0.9 * inch, 0.8 * inch, 0.7 * inch, 0.9 * inch, 1.5 * inch],
        filename='all_students_report.pdf',
    )


def export_subject_report(subject, db):
    """Export subject-wise report as PDF"""
    sessions_list = list(db.sessions.find({"subject": subject}))
    students_list = list(db.students.find({}))

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Attended', 'Total', 'Percentage', 'Status']]
    for idx, student in enumerate(students_list, 1):
        attended = db.attendance.count_documents(
            {"student_id": student['roll_no'], "subject": subject}
        )
        percent = round((attended / len(sessions_list)) * 100, 2) if sessions_list else 0
        status = 'Good' if percent >= 85 else ('Average' if percent >= 75 else 'Low')
        table_data.append([
            str(idx), student['roll_no'], student['name'], student['branch'],
            str(attended), str(len(sessions_list)), f"{percent}%", status
        ])

    subtitle_lines = [
        f'<b>Subject:</b> {subject}  &nbsp;&nbsp;  '
        f'<b>Total Sessions:</b> {len(sessions_list)}  &nbsp;&nbsp;  '
        f'<b>Total Students:</b> {len(students_list)}',
    ]

    return build_report(
        db,
        title=f'SUBJECT REPORT — {subject}',
        subtitle_lines=subtitle_lines,
        table_data=table_data,
        col_widths=[0.4 * inch, 0.9 * inch, 1.7 * inch, 0.9 * inch, 0.8 * inch, 0.7 * inch, 1.0 * inch, 1.4 * inch],
        filename=f'{subject}_report.pdf',
    )


def export_overall_report(db):
    """Export overall report as PDF"""
    subjects = ["CNS", "RM", "M.Com", "OE-2", "SFT", "SEM"]
    subject_stats = []
    for subject in subjects:
        sessions_count = db.sessions.count_documents({"subject": subject})
        attended_count = db.attendance.count_documents({"subject": subject})
        percent = round((attended_count / sessions_count) * 100, 2) if sessions_count > 0 else 0
        subject_stats.append({
            "subject": subject, "total": sessions_count,
            "attended": attended_count, "percentage": percent
        })

    table_data = [['#', 'Subject', 'Total Sessions', 'Total Attendance', 'Percentage', 'Performance']]
    for idx, stat in enumerate(subject_stats, 1):
        perf = 'Good' if stat['percentage'] >= 85 else ('Average' if stat['percentage'] >= 75 else 'Low')
        table_data.append([
            str(idx), stat['subject'], str(stat['total']),
            str(stat['attended']), f"{stat['percentage']}%", perf
        ])

    subtitle_lines = [
        f'<b>Total Students:</b> {db.students.count_documents({})}  &nbsp;&nbsp;  '
        f'<b>Total Sessions:</b> {db.sessions.count_documents({})}  &nbsp;&nbsp;  '
        f'<b>Subjects:</b> {len(subjects)}',
    ]

    return build_report(
        db,
        title='OVERALL ATTENDANCE REPORT',
        subtitle_lines=subtitle_lines,
        table_data=table_data,
        col_widths=[0.5 * inch, 1.5 * inch, 1.3 * inch, 1.5 * inch, 1.2 * inch, 1.5 * inch],
        filename='overall_report.pdf',
    )


def export_all_attendance_report(session, db):
    """Export all attendance records as PDF"""
    if session.get('role') == 'student':
        records = list(db.attendance.find({"student_id": session['user_id']}).sort("time", -1))
    else:
        records = list(db.attendance.find({}).sort("time", -1))

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Session ID', 'Subject', 'Date & Time']]
    for idx, record in enumerate(records, 1):
        student = db.students.find_one({"roll_no": record['student_id']})
        time_str = record['time'].strftime('%d-%m-%Y %I:%M %p') if record.get('time') else 'N/A'
        table_data.append([
            str(idx),
            record['student_id'],
            student['name'] if student else 'Unknown',
            student['branch'] if student else '-',
            record['session_id'],
            record['subject'],
            time_str,
        ])

    subtitle_lines = [
        f'<b>Total Records:</b> {len(records)}  &nbsp;&nbsp;  '
        f'<b>Exported By:</b> {session.get("user_name", "N/A")} ({session.get("role", "N/A")})',
    ]

    return build_report(
        db,
        title='COMPLETE ATTENDANCE RECORDS',
        subtitle_lines=subtitle_lines,
        table_data=table_data,
        col_widths=[0.4 * inch, 0.9 * inch, 1.6 * inch, 0.8 * inch, 1.0 * inch, 0.9 * inch, 1.6 * inch],
        filename='all_attendance_records.pdf',
    )


def export_faculty_report(db):
    """Export faculty list as PDF"""
    faculties = list(db.faculty.find({}).sort("faculty_id", 1))

    table_data = [['#', 'Faculty ID', 'Name', 'Email', 'Department', 'Created Date']]
    for idx, faculty in enumerate(faculties, 1):
        created = faculty['created_at'].strftime('%d-%m-%Y') if faculty.get('created_at') else 'N/A'
        table_data.append([
            str(idx), faculty['faculty_id'], faculty['name'],
            faculty['email'], faculty['department'], created
        ])

    subtitle_lines = [f'<b>Total Faculty Members:</b> {len(faculties)}']

    return build_report(
        db,
        title='FACULTY DIRECTORY',
        subtitle_lines=subtitle_lines,
        table_data=table_data,
        col_widths=[0.4 * inch, 1.0 * inch, 1.6 * inch, 2.0 * inch, 1.1 * inch, 1.2 * inch],
        filename='faculty_list.pdf',
    )


def export_students_directory(db):
    """Export students directory as PDF"""
    students_list = list(db.students.find({}).sort("roll_no", 1))

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Email', 'Year', 'Semester']]
    for idx, student in enumerate(students_list, 1):
        table_data.append([
            str(idx),
            student['roll_no'],
            student['name'],
            student['branch'],
            student.get('email', 'N/A'),
            f"Year {student.get('year', 'N/A')}",
            f"Sem {student.get('semester', 'N/A')}",
        ])

    subtitle_lines = [f'<b>Total Students:</b> {len(students_list)}']

    return build_report(
        db,
        title='STUDENT DIRECTORY',
        subtitle_lines=subtitle_lines,
        table_data=table_data,
        col_widths=[0.4 * inch, 0.9 * inch, 1.6 * inch, 0.8 * inch, 2.0 * inch, 0.8 * inch, 0.8 * inch],
        filename='student_list.pdf',
    )