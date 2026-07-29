"""
app/utils/export.py

School data export utility.
Generates a branded multi-sheet Excel workbook containing all of a
school's academic data. Used by both Platform Admin (any school) and
SuperAdmin (own school only).

Sheets produced:
  1. Summary          — school profile + export metadata
  2. Students         — all active + archived students
  3. Scores           — every score record across all sessions/terms
  4. Staff            — all staff accounts
  5. Classes          — class list with form master assignments
  6. Subjects         — subject list with section scoping
  7. Allocations      — teacher → subject → class assignments
  8. Coupons          — coupon register (term, code, used/unused, used by)

All data is the school's own — no cross-school leakage possible since
the school_id is passed explicitly and every query filters on it.
"""

import io
from datetime import datetime

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter

# ── Brand colors ──────────────────────────────────────────────────────────────
NAVY    = '0A0E17'
BLUE    = '1A3FD4'
CYAN    = '00B4E6'
LIME    = '7ED321'
WHITE   = 'FFFFFF'
LGRAY   = 'F1F5F9'
MGRAY   = 'E2E8F0'
DGRAY   = '64748B'
BLACK   = '0F172A'


def _hdr_font(color=WHITE, size=10, bold=True):
    return Font(name='Arial', bold=bold, size=size, color=color)


def _body_font(bold=False, color=BLACK, size=10):
    return Font(name='Arial', bold=bold, size=size, color=color)


def _fill(hex_color):
    return PatternFill('solid', fgColor=hex_color)


def _border():
    side = Side(style='thin', color=MGRAY)
    return Border(left=side, right=side, top=side, bottom=side)


def _center():
    return Alignment(horizontal='center', vertical='center', wrap_text=True)


def _left():
    return Alignment(horizontal='left', vertical='center', wrap_text=True)


def _write_header_row(ws, cols, row=1, bg=NAVY, fg=WHITE):
    """Write a styled header row. cols = list of (header_text, col_width)."""
    for ci, (text, width) in enumerate(cols, start=1):
        cell = ws.cell(row=row, column=ci, value=text)
        cell.font      = _hdr_font(color=fg)
        cell.fill      = _fill(bg)
        cell.alignment = _center()
        cell.border    = _border()
        ws.column_dimensions[get_column_letter(ci)].width = width
    ws.row_dimensions[row].height = 20


def _write_data_row(ws, values, row, shade=False):
    """Write a data row with alternating shading."""
    bg = LGRAY if shade else WHITE
    for ci, val in enumerate(values, start=1):
        cell = ws.cell(row=row, column=ci, value=val)
        cell.font      = _body_font()
        cell.fill      = _fill(bg)
        cell.alignment = _left()
        cell.border    = _border()


def _freeze_and_filter(ws, row=1):
    ws.freeze_panes = f'A{row + 1}'
    ws.auto_filter.ref = ws.dimensions


def _sheet_title(ws, title, subtitle=''):
    """Branded title block at the top of each sheet."""
    ws.merge_cells('A1:H1')
    t = ws['A1']
    t.value     = title
    t.font      = Font(name='Arial', bold=True, size=13, color=WHITE)
    t.fill      = _fill(NAVY)
    t.alignment = _center()
    ws.row_dimensions[1].height = 24

    if subtitle:
        ws.merge_cells('A2:H2')
        s = ws['A2']
        s.value     = subtitle
        s.font      = Font(name='Arial', size=9, color=DGRAY, italic=True)
        s.fill      = _fill(LGRAY)
        s.alignment = _center()
        ws.row_dimensions[2].height = 16
        return 3   # data starts at row 3
    return 2       # data starts at row 2


# ══════════════════════════════════════════════════════════════════════════════
# MAIN EXPORT FUNCTION
# ══════════════════════════════════════════════════════════════════════════════
def generate_school_export(school_id):
    """
    Build and return a BytesIO object containing the Excel workbook
    for the given school_id.

    Caller is responsible for verifying the requesting user is allowed
    to export this school's data (Platform Admin or that school's SuperAdmin).
    """
    # Import here to avoid circular imports
    from app.models import (
        School, User, Student, Teacher, Class, Subject,
        SubjectAllocation, Score, AcademicSession, Term,
        Coupon, CouponActivation
    )

    school = School.query.get_or_404(school_id)
    now    = datetime.now()

    wb = openpyxl.Workbook()
    wb.remove(wb.active)   # remove default empty sheet

    # ── Sheet 1: Summary ──────────────────────────────────────────────────────
    ws = wb.create_sheet('Summary')
    ws.column_dimensions['A'].width = 28
    ws.column_dimensions['B'].width = 48

    ws.merge_cells('A1:B1')
    t = ws['A1']
    t.value     = f'GRPMS Data Export — {school.name}'
    t.font      = Font(name='Arial', bold=True, size=14, color=WHITE)
    t.fill      = _fill(NAVY)
    t.alignment = _center()
    ws.row_dimensions[1].height = 28

    rows = [
        ('School Name',       school.name),
        ('Motto',             school.motto or '—'),
        ('Principal',         school.principal_name or '—'),
        ('School Code',       school.code or '—'),
        ('Export Date',       now.strftime('%d %B %Y, %H:%M')),
        ('Exported By',       'GRPMS Platform'),
        ('',                  ''),
        ('CONTENTS',          ''),
        ('Sheet 2',           'Students — all enrolled, active and archived'),
        ('Sheet 3',           'Scores — all subject scores across all terms'),
        ('Sheet 4',           'Staff — all staff accounts'),
        ('Sheet 5',           'Classes — class list with form masters'),
        ('Sheet 6',           'Subjects — subject list with section scoping'),
        ('Sheet 7',           'Allocations — teacher/subject/class assignments'),
        ('Sheet 8',           'Coupons — coupon register'),
    ]

    for ri, (label, value) in enumerate(rows, start=2):
        ws.row_dimensions[ri].height = 18
        la = ws.cell(row=ri, column=1, value=label)
        va = ws.cell(row=ri, column=2, value=value)

        is_section = label in ('', 'CONTENTS')
        la.font = Font(name='Arial', bold=True, size=10,
                       color=BLUE if label == 'CONTENTS' else BLACK)
        va.font = _body_font()

        if label == 'CONTENTS':
            la.fill = _fill(LGRAY)
            va.fill = _fill(LGRAY)
        elif label == '':
            pass
        else:
            la.fill = _fill(LGRAY) if ri % 2 == 0 else _fill(WHITE)
            va.fill = _fill(LGRAY) if ri % 2 == 0 else _fill(WHITE)

        la.alignment = _left()
        va.alignment = _left()
        la.border    = _border()
        va.border    = _border()

    # ── Sheet 2: Students ─────────────────────────────────────────────────────
    ws = wb.create_sheet('Students')
    subtitle = f'{school.name} — All Students (Active + Archived)'
    data_row = _sheet_title(ws, 'STUDENTS', subtitle)

    cols = [
        ('Admission No.',     16),
        ('Last Name',         18),
        ('First Name',        18),
        ('Current Class',     16),
        ('Previous Class',    16),
        ('Username (Login)',   18),
        ('Status',            12),
        ('Archive Type',      14),
        ('Archive Date',      18),
    ]
    _write_header_row(ws, cols, row=data_row, bg=BLUE)
    _freeze_and_filter(ws, row=data_row)

    students = Student.query.filter_by(school_id=school_id)\
                            .order_by(Student.last_name, Student.first_name).all()

    for ri, s in enumerate(students, start=data_row + 1):
        _write_data_row(ws, [
            s.admission_number,
            s.last_name,
            s.first_name,
            s.student_class.class_name if s.student_class else '—',
            s.previous_class.class_name if s.previous_class else '—',
            s.user.username if s.user else '—',
            'Active' if s.is_active else 'Inactive',
            s.archive_type or 'none',
            s.archive_date.strftime('%d/%m/%Y') if s.archive_date else '—',
        ], row=ri, shade=(ri % 2 == 0))

    # ── Sheet 3: Scores ───────────────────────────────────────────────────────
    ws = wb.create_sheet('Scores')
    data_row = _sheet_title(ws, 'SCORES', f'{school.name} — All Score Records')

    cols = [
        ('Admission No.',  14),
        ('Student Name',   22),
        ('Class',          14),
        ('Session',        14),
        ('Term',           14),
        ('Subject',        20),
        ('Subject Code',   12),
        ('CA 1 /10',        9),
        ('CA 2 /10',        9),
        ('Ass 1 /10',       9),
        ('Ass 2 /10',       9),
        ('Exam /60',        9),
        ('Total /100',     11),
        ('Grade',           8),
        ('Remark',         12),
        ('Released',       10),
    ]
    _write_header_row(ws, cols, row=data_row, bg=BLUE)
    _freeze_and_filter(ws, row=data_row)

    # Join across sessions scoped to this school
    sessions = AcademicSession.query.filter_by(school_id=school_id).all()
    session_ids = [s.id for s in sessions]

    scores = (
        Score.query
        .filter(Score.session_id.in_(session_ids))
        .join(Student, Score.student_id == Student.id)
        .filter(Student.school_id == school_id)
        .order_by(Score.session_id, Score.term_id, Student.last_name)
        .all()
    ) if session_ids else []

    for ri, sc in enumerate(scores, start=data_row + 1):
        student = sc.student
        _write_data_row(ws, [
            student.admission_number,
            f'{student.last_name}, {student.first_name}',
            student.student_class.class_name if student.student_class else '—',
            sc.session.session_name if sc.session else '—',
            sc.term.term_name if sc.term else '—',
            sc.subject.subject_name if sc.subject else '—',
            sc.subject.subject_code if sc.subject else '—',
            sc.ca_1,
            sc.ca_2,
            sc.assign_1,
            sc.assign_2,
            sc.exam,
            sc.total_score,
            sc.grade or '—',
            sc.remark or '—',
            'Yes' if sc.is_released else 'No',
        ], row=ri, shade=(ri % 2 == 0))

    # ── Sheet 4: Staff ────────────────────────────────────────────────────────
    ws = wb.create_sheet('Staff')
    data_row = _sheet_title(ws, 'STAFF ACCOUNTS', f'{school.name}')

    cols = [
        ('Username',      18),
        ('Role',          16),
        ('Full Name',     24),
        ('Title',         10),
        ('Status',        12),
    ]
    _write_header_row(ws, cols, row=data_row, bg=BLUE)
    _freeze_and_filter(ws, row=data_row)

    staff = User.query.filter(
        User.school_id == school_id,
        User.role != 'Student'
    ).order_by(User.role, User.username).all()

    for ri, u in enumerate(staff, start=data_row + 1):
        teacher = u.teacher_profile if hasattr(u, 'teacher_profile') else None
        _write_data_row(ws, [
            u.username,
            u.role,
            teacher.full_name if teacher else '—',
            teacher.title if teacher else '—',
            'Active' if u.is_active else 'Inactive',
        ], row=ri, shade=(ri % 2 == 0))

    # ── Sheet 5: Classes ──────────────────────────────────────────────────────
    ws = wb.create_sheet('Classes')
    data_row = _sheet_title(ws, 'CLASSES', f'{school.name}')

    cols = [
        ('Class Name',       20),
        ('Section',          20),
        ('Form Master',      24),
        ('Active Students',  16),
    ]
    _write_header_row(ws, cols, row=data_row, bg=BLUE)
    _freeze_and_filter(ws, row=data_row)

    classes = Class.query.filter_by(school_id=school_id)\
                         .order_by(Class.class_name).all()

    for ri, c in enumerate(classes, start=data_row + 1):
        student_count = Student.query.filter_by(
            current_class_id=c.id, is_active=True
        ).count()
        fm = c.form_master
        _write_data_row(ws, [
            c.class_name,
            c.section or '—',
            f'{fm.title} {fm.full_name}' if fm else '—',
            student_count,
        ], row=ri, shade=(ri % 2 == 0))

    # ── Sheet 6: Subjects ─────────────────────────────────────────────────────
    ws = wb.create_sheet('Subjects')
    data_row = _sheet_title(ws, 'SUBJECTS', f'{school.name}')

    cols = [
        ('Subject Name',  28),
        ('Subject Code',  14),
        ('Section',       22),
    ]
    _write_header_row(ws, cols, row=data_row, bg=BLUE)
    _freeze_and_filter(ws, row=data_row)

    subjects = Subject.query.filter_by(school_id=school_id)\
                            .order_by(Subject.section, Subject.subject_name).all()

    for ri, s in enumerate(subjects, start=data_row + 1):
        _write_data_row(ws, [
            s.subject_name,
            s.subject_code,
            s.section or 'All Sections',
        ], row=ri, shade=(ri % 2 == 0))

    # ── Sheet 7: Allocations ──────────────────────────────────────────────────
    ws = wb.create_sheet('Allocations')
    data_row = _sheet_title(ws, 'TEACHER ALLOCATIONS', f'{school.name}')

    cols = [
        ('Teacher',         24),
        ('Subject',         24),
        ('Subject Code',    14),
        ('Class',           18),
        ('Section',         20),
    ]
    _write_header_row(ws, cols, row=data_row, bg=BLUE)
    _freeze_and_filter(ws, row=data_row)

    allocs = (
        SubjectAllocation.query
        .join(Teacher, SubjectAllocation.teacher_id == Teacher.id)
        .filter(Teacher.school_id == school_id)
        .order_by(Teacher.full_name)
        .all()
    )

    for ri, a in enumerate(allocs, start=data_row + 1):
        _write_data_row(ws, [
            f'{a.teacher.title} {a.teacher.full_name}',
            a.subject.subject_name,
            a.subject.subject_code,
            a.assigned_class.class_name,
            a.subject.section or 'All Sections',
        ], row=ri, shade=(ri % 2 == 0))

    # ── Sheet 8: Coupons ──────────────────────────────────────────────────────
    ws = wb.create_sheet('Coupons')
    data_row = _sheet_title(ws, 'COUPON REGISTER', f'{school.name}')

    cols = [
        ('Code',           14),
        ('Session',        16),
        ('Term',           16),
        ('Status',         10),
        ('Used By (Name)', 24),
        ('Adm. No.',       14),
        ('Date Used',      20),
    ]
    _write_header_row(ws, cols, row=data_row, bg=BLUE)
    _freeze_and_filter(ws, row=data_row)

    coupons = Coupon.query.filter_by(school_id=school_id)\
                          .order_by(Coupon.created_at.desc()).all()

    for ri, c in enumerate(coupons, start=data_row + 1):
        used_by = c.used_by
        _write_data_row(ws, [
            c.code,
            c.term.session.session_name if c.term and c.term.session else '—',
            c.term.term_name if c.term else '—',
            'Used' if c.is_used else 'Unused',
            f'{used_by.last_name}, {used_by.first_name}' if used_by else '—',
            used_by.admission_number if used_by else '—',
            c.used_at.strftime('%d/%m/%Y %H:%M') if c.used_at else '—',
        ], row=ri, shade=(ri % 2 == 0))

    # ── Tab colors ────────────────────────────────────────────────────────────
    tab_colors = {
        'Summary':     '0A0E17',
        'Students':    '1A3FD4',
        'Scores':      '00B4E6',
        'Staff':       '7ED321',
        'Classes':     '0d9488',
        'Subjects':    '534ab7',
        'Allocations': 'd97706',
        'Coupons':     'dc2626',
    }
    for sheet_name, color in tab_colors.items():
        if sheet_name in wb.sheetnames:
            wb[sheet_name].sheet_properties.tabColor = color

    # ── Return as BytesIO ─────────────────────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf, school.name
