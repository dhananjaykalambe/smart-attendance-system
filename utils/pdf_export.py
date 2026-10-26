# utils/pdf_export.py
# ====================================================================
# PDF EXPORT FUNCTIONS - CLEAN MONOCHROME PROFESSIONAL DESIGN
# ====================================================================

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.units import inch, mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from datetime import datetime
import io
from flask import send_file, session


# ====================================================================
# MONOCHROME PALETTE (BLACK / WHITE / GRAY ONLY)
# ====================================================================
BLACK = colors.black
DARK = colors.HexColor('#1a1a1a')
GRAY_DARK = colors.HexColor('#333333')
GRAY = colors.HexColor('#555555')
GRAY_MID = colors.HexColor('#777777')
GRAY_LIGHT = colors.HexColor('#999999')
GRAY_FAINT = colors.HexColor('#cccccc')
GRAY_ROW = colors.HexColor('#f2f2f2')
WHITE = colors.white


# ====================================================================
# HELPERS
# ====================================================================

def get_college_info(db):
    """Get college header info from settings"""
    settings = db.settings.find_one({}) or {}
    return {
        'name': settings.get('college_name', 'Priyadarshini Bhagwati College of Engineering'),
        'location': settings.get('college_location', 'Nagpur'),
        'year': settings.get('academic_year', '2024-25'),
        'hod': settings.get('hod_name', 'Head of Department'),
    }


def get_exporter_name():
    """Get current logged-in user's name from session"""
    return session.get('user_name', 'Faculty')


def get_exporter_role():
    """Get current logged-in user's role from session"""
    return session.get('role', 'faculty')


def create_pdf_response(buffer, filename):
    buffer.seek(0)
    return send_file(buffer, download_name=filename, as_attachment=True, mimetype='application/pdf')


def build_styles():
    """Build all paragraph styles - clean monochrome typography"""
    styles = getSampleStyleSheet()

    return {
        'college': ParagraphStyle(
            'College', parent=styles['Normal'],
            fontSize=15, alignment=TA_CENTER,
            textColor=BLACK, fontName='Helvetica-Bold',
            leading=18, spaceAfter=2
        ),
        'location': ParagraphStyle(
            'Location', parent=styles['Normal'],
            fontSize=9.5, alignment=TA_CENTER,
            textColor=GRAY, fontName='Helvetica',
            spaceAfter=4
        ),
        'report_title': ParagraphStyle(
            'ReportTitle', parent=styles['Normal'],
            fontSize=12, alignment=TA_CENTER,
            textColor=BLACK, fontName='Helvetica-Bold',
            leading=15, spaceBefore=4, spaceAfter=2
        ),
        'meta_line': ParagraphStyle(
            'MetaLine', parent=styles['Normal'],
            fontSize=9, alignment=TA_LEFT,
            textColor=GRAY_DARK, fontName='Helvetica',
            leading=13
        ),
        'footer': ParagraphStyle(
            'Footer', parent=styles['Normal'],
            fontSize=7.5, alignment=TA_CENTER,
            textColor=GRAY_MID, fontName='Helvetica-Oblique'
        ),
        'sig_label': ParagraphStyle(
            'SigLabel', parent=styles['Normal'],
            fontSize=9, alignment=TA_CENTER,
            textColor=BLACK, fontName='Helvetica-Bold',
            leading=12
        ),
        'sig_sub': ParagraphStyle(
            'SigSub', parent=styles['Normal'],
            fontSize=8, alignment=TA_CENTER,
            textColor=GRAY, fontName='Helvetica'
        ),
    }


# ====================================================================
# AUTO-SIZING COLUMN WIDTHS
# ====================================================================

def auto_column_widths(table_data, available_width, font_name='Helvetica',
                       font_size=8.5, header_size=9, padding=6):
    """
    Calculate optimal column widths based on actual text content.
    Ensures every column is wide enough for both header AND data.
    Scales proportionally to fill available_width exactly.
    """
    if not table_data or not table_data[0]:
        return []

    n_cols = len(table_data[0])
    min_widths = [0] * n_cols

    # Measure each cell's natural width
    for row_idx, row in enumerate(table_data):
        size = header_size if row_idx == 0 else font_size
        name = 'Helvetica-Bold' if row_idx == 0 else font_name
        for col_idx in range(n_cols):
            cell_text = str(row[col_idx]) if col_idx < len(row) else ''
            if not cell_text:
                cell_text = ' '
            text_w = stringWidth(cell_text, name, size)
            cell_w = text_w + (padding * 2) + 2
            if cell_w > min_widths[col_idx]:
                min_widths[col_idx] = cell_w

    # Add a small safety margin
    min_widths = [w + 2 for w in min_widths]
    total_min = sum(min_widths)

    # Distribute remaining width proportionally
    if total_min >= available_width:
        # Cannot fit — scale down proportionally
        scale = available_width / total_min
        return [w * scale for w in min_widths]

    extra = available_width - total_min
    per_col_extra = extra / n_cols
    return [w + per_col_extra for w in min_widths]


# ====================================================================
# CELL / TABLE BUILDERS
# ====================================================================

def make_cell(text, align='LEFT', bold=False, size=8.5, color=None):
    """Create a properly aligned Paragraph for a table cell"""
    if color is None:
        color = DARK
    style = ParagraphStyle(
        'Cell', fontName='Helvetica-Bold' if bold else 'Helvetica',
        fontSize=size, textColor=color, leading=size + 3,
        alignment={'LEFT': TA_LEFT, 'CENTER': TA_CENTER, 'RIGHT': TA_RIGHT}[align],
        spaceBefore=0, spaceAfter=0,
    )
    return Paragraph(str(text) if text is not None else '', style)


def build_header(db, title, meta_lines, styles, page_width):
    """Elegant monochrome header with title rule"""
    info = get_college_info(db)
    elements = []

    # College name (bold, centered)
    elements.append(Paragraph(info['name'].upper(), styles['college']))
    # Location (small gray)
    elements.append(Paragraph(info['location'], styles['location']))

    # Thin rule
    rule = Table([['']], colWidths=[page_width], rowHeights=[1])
    rule.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 1.2, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(rule)
    elements.append(Spacer(1, 6))

    # Report title (bold, centered)
    elements.append(Paragraph(title.upper(), styles['report_title']))

    # Second thin rule
    rule2 = Table([['']], colWidths=[page_width], rowHeights=[1])
    rule2.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 0.6, GRAY_DARK),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(rule2)
    elements.append(Spacer(1, 8))

    # Meta lines
    if meta_lines:
        for line in meta_lines:
            elements.append(Paragraph(line, styles['meta_line']))
        elements.append(Spacer(1, 10))

    return elements


def build_data_table(table_data, available_width, alignment_map=None):
    """
    Build a professional monochrome table.
    - Thin black header underline
    - No fill colors
    - Alternating very-light gray rows for readability
    - Proper cell alignment per column
    """
    if not table_data:
        return None

    n_cols = len(table_data[0])
    col_widths = auto_column_widths(table_data, available_width)

    if alignment_map is None:
        alignment_map = ['CENTER'] * n_cols

    # Convert every cell to Paragraph for wrapping
    para_rows = []
    for row_idx, row in enumerate(table_data):
        para_row = []
        for col_idx, cell in enumerate(row):
            align = alignment_map[col_idx] if col_idx < len(alignment_map) else 'LEFT'
            is_header = (row_idx == 0)
            para_row.append(make_cell(
                cell,
                align='CENTER' if is_header else align,
                bold=is_header,
                size=9 if is_header else 8.5,
                color=BLACK if is_header else DARK,
            ))
        para_rows.append(para_row)

    tbl = Table(para_rows, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), WHITE),
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, BLACK),
        ('LINEABOVE', (0, 0), (-1, 0), 0.6, GRAY_DARK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),

        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('TOPPADDING', (0, 1), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),

        # Thin outer border + row separators
        ('BOX', (0, 0), (-1, -1), 0.8, BLACK),
        ('LINEBELOW', (0, 1), (-1, -2), 0.4, GRAY_FAINT),
    ]

    # Subtle zebra striping (very light gray)
    for i in range(1, len(para_rows)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), GRAY_ROW))

    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def build_signatures(styles, page_width, hod_name='Head of Department'):
    """
    Role-aware signature block:
      - Student exports  -> HOD (left)  +  "Class Incharge" (right, no name)
      - Faculty exports  -> HOD (left)  +  Faculty name (right, "Faculty")
      - Admin exports    -> HOD only, centered
    """
    role = get_exporter_role()
    faculty_name = get_exporter_name()

    # ---------------- ADMIN: HOD only, centered ----------------
    if role == 'admin':
        sig_data = [[
            '',  # empty left
            Paragraph(
                f'<br/><br/><br/>'
                f'<font color="#555555">_______________________________</font><br/>'
                f'<b>{hod_name}</b><br/>'
                f'<font size="8" color="#777777">Head of Department</font>',
                styles['sig_label']
            ),
            '',  # empty right
        ]]
        third = page_width / 3
        sig_table = Table(sig_data, colWidths=[third, third, third])
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        return sig_table

    # ---------------- STUDENT: HOD + Class Incharge ----------------
    if role == 'student':
        right_label = 'Class Incharge'
        right_sub = 'Class Incharge'
    # ---------------- FACULTY: HOD + Faculty name ----------------
    else:
        right_label = faculty_name
        right_sub = 'Faculty'

    sig_data = [[
        Paragraph(
            f'<br/><br/><br/>'
            f'<font color="#555555">_______________________________</font><br/>'
            f'<b>{hod_name}</b><br/>'
            f'<font size="8" color="#777777">Head of Department</font>',
            styles['sig_label']
        ),
        Paragraph(
            f'<br/><br/><br/>'
            f'<font color="#555555">_______________________________</font><br/>'
            f'<b>{right_label}</b><br/>'
            f'<font size="8" color="#777777">{right_sub}</font>',
            styles['sig_label']
        ),
    ]]

    half = page_width / 2
    sig_table = Table(sig_data, colWidths=[half, half])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return sig_table


def build_footer(styles, page_width):
    """Bottom timestamp footer with hairline above"""
    rule = Table([['']], colWidths=[page_width], rowHeights=[1])
    rule.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, GRAY_FAINT),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    timestamp = Paragraph(
        f'Generated on {datetime.now().strftime("%d %b %Y, %I:%M %p")} '
        f'&nbsp;•&nbsp; Smart Attendance System',
        styles['footer']
    )
    return [rule, Spacer(1, 4), timestamp]


# ====================================================================
# GENERIC REPORT BUILDER
# ====================================================================

def build_report(db, title, meta_lines, table_data, alignment_map, filename,
                 landscape_mode=True, hod_name=None):
    """
    Build a complete report with:
    - Clean header (no colors)
    - Auto-sized table
    - Role-aware signatures
    - Timestamp footer
    """
    buffer = io.BytesIO()
    pagesize = landscape(A4) if landscape_mode else A4
    margin = 0.5 * inch

    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=title,
    )

    styles = build_styles()
    page_width = pagesize[0] - (2 * margin)
    info = get_college_info(db)

    if hod_name is None:
        hod_name = info.get('hod', 'Head of Department')

    elements = []

    # Header
    elements.extend(build_header(db, title, meta_lines, styles, page_width))

    # Table
    tbl = build_data_table(table_data, page_width, alignment_map)
    if tbl is not None:
        elements.append(tbl)

    elements.append(Spacer(1, 22))

    # Signatures (role-aware)
    elements.append(build_signatures(styles, page_width, hod_name=hod_name))

    elements.append(Spacer(1, 18))

    # Footer
    elements.extend(build_footer(styles, page_width))

    doc.build(elements)
    return create_pdf_response(buffer, filename)


# ====================================================================
# REPORT FUNCTIONS
# ====================================================================

def export_attendance_report(session_id, db):
    """Session attendance report"""
    session_data = db.sessions.find_one({"session_id": session_id})
    if not session_data:
        return "Session not found"

    records = list(db.attendance.find({"session_id": session_id}).sort("time", 1))

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Time', 'IP Address']]
    for idx, record in enumerate(records, 1):
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

    meta_lines = [
        f'<b>Session ID:</b> {session_id}   •   '
        f'<b>Subject:</b> {session_data["subject"]}   •   '
        f'<b>Date:</b> {session_data["start_time"].strftime("%d %b %Y")}',
        f'<b>Start Time:</b> {session_data["start_time"].strftime("%I:%M %p")}   •   '
        f'<b>Duration:</b> {session_data.get("duration", "N/A")} min   •   '
        f'<b>Total Present:</b> {len(records)}',
    ]

    alignment_map = ['CENTER', 'CENTER', 'LEFT', 'CENTER', 'CENTER', 'CENTER']

    return build_report(
        db,
        title=f'Attendance Report — {session_data["subject"]}',
        meta_lines=meta_lines,
        table_data=table_data,
        alignment_map=alignment_map,
        filename=f'attendance_{session_id}.pdf',
    )


def export_student_report(roll_no, db):
    """Individual student report"""
    student = db.students.find_one({"roll_no": roll_no})
    if not student:
        return "Student not found"

    attendance = list(db.attendance.find({"student_id": roll_no}))
    all_sessions = list(db.sessions.find({}))

    subject_stats = {}
    for s in all_sessions:
        subj = s.get("subject")
        if subj:
            subject_stats.setdefault(subj, {"total": 0, "attended": 0})
            subject_stats[subj]["total"] += 1

    for record in attendance:
        subj = record.get("subject")
        if subj in subject_stats:
            subject_stats[subj]["attended"] += 1

    for d in subject_stats.values():
        d["percentage"] = round((d["attended"] / d["total"]) * 100, 2) if d["total"] else 0

    total_attended = len(attendance)
    total_sessions = len(all_sessions)
    overall = round((total_attended / total_sessions) * 100, 2) if total_sessions else 0

    table_data = [['#', 'Subject', 'Attended', 'Total', 'Percentage', 'Status']]
    for idx, (subj, d) in enumerate(subject_stats.items(), 1):
        status = 'Good' if d['percentage'] >= 85 else ('Average' if d['percentage'] >= 75 else 'Needs Improvement')
        table_data.append([
            str(idx), subj, str(d['attended']), str(d['total']),
            f"{d['percentage']}%", status,
        ])
    # Total row
    table_data.append(['', 'OVERALL', str(total_attended), str(total_sessions), f'{overall}%', '—'])

    meta_lines = [
        f'<b>Name:</b> {student["name"]}   •   '
        f'<b>Roll No:</b> {student["roll_no"]}   •   '
        f'<b>Branch:</b> {student["branch"]}',
        f'<b>Overall Attendance:</b> {overall}%   •   '
        f'<b>Classes Attended:</b> {total_attended} / {total_sessions}',
    ]

    alignment_map = ['CENTER', 'LEFT', 'CENTER', 'CENTER', 'CENTER', 'CENTER']

    return build_report(
        db,
        title='Student Attendance Report',
        meta_lines=meta_lines,
        table_data=table_data,
        alignment_map=alignment_map,
        filename=f'student_{roll_no}_report.pdf',
        landscape_mode=False,
    )


def export_all_students_report(db):
    """All students report"""
    students_list = list(db.students.find({}).sort("roll_no", 1))
    all_sessions = list(db.sessions.find({}))

    totals = {}
    for s in all_sessions:
        subj = s.get('subject')
        totals[subj] = totals.get(subj, 0) + 1

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Attended', 'Total', 'Overall %', 'Performance']]
    for idx, student in enumerate(students_list, 1):
        att = 0
        pos = 0
        for subj, t in totals.items():
            att += db.attendance.count_documents({"student_id": student['roll_no'], "subject": subj})
            pos += t
        overall = round((att / pos) * 100, 2) if pos else 0
        perf = 'Excellent' if overall >= 85 else ('Good' if overall >= 75 else 'Needs Improvement')
        table_data.append([
            str(idx), student['roll_no'], student['name'], student['branch'],
            str(att), str(pos), f'{overall}%', perf,
        ])

    meta_lines = [
        f'<b>Total Students:</b> {len(students_list)}   •   '
        f'<b>Total Sessions:</b> {len(all_sessions)}',
    ]

    alignment_map = ['CENTER', 'CENTER', 'LEFT', 'CENTER', 'CENTER', 'CENTER', 'CENTER', 'CENTER']

    return build_report(
        db,
        title='Complete Student Attendance Report',
        meta_lines=meta_lines,
        table_data=table_data,
        alignment_map=alignment_map,
        filename='all_students_report.pdf',
    )


def export_subject_report(subject, db):
    """Subject-wise report"""
    sessions_list = list(db.sessions.find({"subject": subject}))
    students_list = list(db.students.find({}).sort("roll_no", 1))

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Attended', 'Total', 'Percentage', 'Status']]
    for idx, student in enumerate(students_list, 1):
        att = db.attendance.count_documents({"student_id": student['roll_no'], "subject": subject})
        pct = round((att / len(sessions_list)) * 100, 2) if sessions_list else 0
        status = 'Good' if pct >= 85 else ('Average' if pct >= 75 else 'Low')
        table_data.append([
            str(idx), student['roll_no'], student['name'], student['branch'],
            str(att), str(len(sessions_list)), f'{pct}%', status,
        ])

    meta_lines = [
        f'<b>Subject:</b> {subject}   •   '
        f'<b>Total Sessions:</b> {len(sessions_list)}   •   '
        f'<b>Total Students:</b> {len(students_list)}',
    ]

    alignment_map = ['CENTER', 'CENTER', 'LEFT', 'CENTER', 'CENTER', 'CENTER', 'CENTER', 'CENTER']

    return build_report(
        db,
        title=f'Subject Report — {subject}',
        meta_lines=meta_lines,
        table_data=table_data,
        alignment_map=alignment_map,
        filename=f'{subject}_report.pdf',
    )


def export_overall_report(db):
    """Overall subject report"""
    subjects = ["CNS", "RM", "M.Com", "OE-2", "SFT", "SEM"]
    stats = []
    for subj in subjects:
        sc = db.sessions.count_documents({"subject": subj})
        ac = db.attendance.count_documents({"subject": subj})
        pct = round((ac / sc) * 100, 2) if sc else 0
        stats.append({"subject": subj, "total": sc, "attended": ac, "percentage": pct})

    table_data = [['#', 'Subject', 'Total Sessions', 'Total Attendance', 'Percentage', 'Performance']]
    for idx, s in enumerate(stats, 1):
        perf = 'Good' if s['percentage'] >= 85 else ('Average' if s['percentage'] >= 75 else 'Low')
        table_data.append([
            str(idx), s['subject'], str(s['total']),
            str(s['attended']), f"{s['percentage']}%", perf,
        ])

    meta_lines = [
        f'<b>Total Students:</b> {db.students.count_documents({})}   •   '
        f'<b>Total Sessions:</b> {db.sessions.count_documents({})}   •   '
        f'<b>Subjects:</b> {len(subjects)}',
    ]

    alignment_map = ['CENTER', 'LEFT', 'CENTER', 'CENTER', 'CENTER', 'CENTER']

    return build_report(
        db,
        title='Overall Attendance Report',
        meta_lines=meta_lines,
        table_data=table_data,
        alignment_map=alignment_map,
        filename='overall_report.pdf',
        landscape_mode=False,
    )


def export_all_attendance_report(session, db):
    """All attendance records"""
    if session.get('role') == 'student':
        records = list(db.attendance.find({"student_id": session['user_id']}).sort("time", -1))
    else:
        records = list(db.attendance.find({}).sort("time", -1))

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Session ID', 'Subject', 'Date & Time']]
    for idx, record in enumerate(records, 1):
        student = db.students.find_one({"roll_no": record['student_id']})
        t = record['time'].strftime('%d-%m-%Y %I:%M %p') if record.get('time') else 'N/A'
        table_data.append([
            str(idx), record['student_id'],
            student['name'] if student else 'Unknown',
            student['branch'] if student else '-',
            record['session_id'], record['subject'], t,
        ])

    meta_lines = [
        f'<b>Total Records:</b> {len(records)}   •   '
        f'<b>Exported By:</b> {session.get("user_name", "N/A")} ({session.get("role", "N/A")})',
    ]

    alignment_map = ['CENTER', 'CENTER', 'LEFT', 'CENTER', 'CENTER', 'CENTER', 'CENTER']

    return build_report(
        db,
        title='Complete Attendance Records',
        meta_lines=meta_lines,
        table_data=table_data,
        alignment_map=alignment_map,
        filename='all_attendance_records.pdf',
    )


def export_faculty_report(db):
    """Faculty directory"""
    faculties = list(db.faculty.find({}).sort("faculty_id", 1))

    table_data = [['#', 'Faculty ID', 'Name', 'Email', 'Department', 'Created Date']]
    for idx, f in enumerate(faculties, 1):
        created = f['created_at'].strftime('%d-%m-%Y') if f.get('created_at') else 'N/A'
        table_data.append([
            str(idx), f['faculty_id'], f['name'], f['email'],
            f['department'], created,
        ])

    meta_lines = [f'<b>Total Faculty Members:</b> {len(faculties)}']

    alignment_map = ['CENTER', 'CENTER', 'LEFT', 'LEFT', 'CENTER', 'CENTER']

    return build_report(
        db,
        title='Faculty Directory',
        meta_lines=meta_lines,
        table_data=table_data,
        alignment_map=alignment_map,
        filename='faculty_list.pdf',
    )


def export_students_directory(db):
    """Students directory"""
    students_list = list(db.students.find({}).sort("roll_no", 1))

    table_data = [['#', 'Roll No', 'Name', 'Branch', 'Email', 'Year', 'Semester']]
    for idx, s in enumerate(students_list, 1):
        table_data.append([
            str(idx), s['roll_no'], s['name'], s['branch'],
            s.get('email', 'N/A'),
            f"Year {s.get('year', 'N/A')}",
            f"Sem {s.get('semester', 'N/A')}",
        ])

    meta_lines = [f'<b>Total Students:</b> {len(students_list)}']

    alignment_map = ['CENTER', 'CENTER', 'LEFT', 'CENTER', 'LEFT', 'CENTER', 'CENTER']

    return build_report(
        db,
        title='Student Directory',
        meta_lines=meta_lines,
        table_data=table_data,
        alignment_map=alignment_map,
        filename='student_list.pdf',
    )