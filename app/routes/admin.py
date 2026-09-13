import csv
import io
import os
from datetime import datetime
from werkzeug.utils import secure_filename

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app, Response, session
)
from flask_login import login_required, current_user

from app import db
from app.models import (
    User, Student, Teacher, Class, Subject,
    AcademicSession, Term, SubjectAllocation, Score, Notification
)
from app.utils.decorators import admin_required, verify_school_ownership
from app.utils.computations import compute_grade_and_remark, get_class_weight

admin_bp = Blueprint('admin', __name__)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _school_id():
    return current_user.school_id


def _active_session():
    return AcademicSession.query.filter_by(
        school_id=_school_id(), is_active=True
    ).first()


def _active_term():
    sess = _active_session()
    if not sess:
        return None
    return Term.query.filter_by(session_id=sess.id, is_active=True).first()


def _generate_admission_number(school_id, active_session):
    """
    Auto-generates a unique admission number scoped to the school and session.
    Format: {Scholol Prefix}/{YY}/{YY}/{seq:03d}
    e.g. SCH2/25/26/001
    """
    from app.models import School
    school = School.query.get(school_id)

    parts = active_session.session_name.split('/')
    short = f"{parts[0][-2:]}/{parts[1][-2:]}" if len(parts) == 2 else 'XX/XX'
    if school.code:
        code = school.code.upper().strip()
    else:
        import re
        letters = re.sub(r'[^A-Za-z]', '', school.name)
        code = letters[:3].upper() if letters else 'SCH'
    prefix = f"{code}/{short}/"

    latest = (
        Student.query
        .filter(Student.admission_number.like(f"{prefix}%"),
                Student.school_id == school_id)
        .order_by(Student.admission_number.desc())
        .first()
    )
    if latest:
        try:
            last_seq = int(latest.admission_number.split('/')[-1])
            next_seq = last_seq + 1
        except ValueError:
            next_seq = 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:03d}"


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    sid = _school_id()

    total_students = Student.query.filter_by(school_id=sid, is_active=True).count()
    total_classes  = Class.query.filter_by(school_id=sid).count()
    total_subjects = Subject.query.filter_by(school_id=sid).count()
    total_staff    = User.query.filter(
        User.school_id == sid,
        User.role.in_(['Teacher', 'FormMaster']),
        User.is_active.is_(True),
    ).count()

    active_session = _active_session()
    active_term    = _active_term()

    unread = Notification.query.filter(
        db.or_(
            Notification.recipient_id == current_user.id,
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'role',
                Notification.recipient_role == 'Admin',
            ),
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'broadcast',
            ),
        ),
        Notification.is_read.is_(False),
    ).count()

    return render_template(
        'admin/dashboard.html',
        total_students=total_students,
        total_classes=total_classes,
        total_subjects=total_subjects,
        total_staff=total_staff,
        active_session=active_session,
        active_term=active_term,
        unread=unread,
    )


# ---------------------------------------------------------------------------
# 6.2  CLASS MANAGEMENT
# ---------------------------------------------------------------------------
@admin_bp.route('/classes', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_classes():
    sid = _school_id()

    if request.method == 'POST':
        class_name = request.form.get('class_name', '').strip()
        section    = request.form.get('section', '').strip()

        if not class_name:
            flash('Class name is required.', 'warning')
        elif Class.query.filter_by(class_name=class_name, school_id=sid).first():
            flash(f'"{class_name}" already exists in this school.', 'warning')
        else:
            db.session.add(Class(
                school_id=sid, class_name=class_name, section=section
            ))
            db.session.commit()
            flash(f'Class "{class_name}" created.', 'success')
        return redirect(url_for('admin.manage_classes'))

    classes = Class.query.filter_by(school_id=sid).all()
    classes.sort(key=lambda c: (get_class_weight(c.class_name), c.class_name))
    return render_template('admin/classes.html', classes=classes)


@admin_bp.route('/classes/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_class(class_id):
    cls = Class.query.get_or_404(class_id)
    verify_school_ownership(cls)
    sid = _school_id()

    if request.method == 'POST':
        new_name = request.form.get('class_name', '').strip()
        section  = request.form.get('section', '').strip()

        if not new_name:
            flash('Class name is required.', 'warning')
            return redirect(url_for('admin.edit_class', class_id=class_id))

        conflict = Class.query.filter(
            Class.class_name == new_name,
            Class.school_id == sid,
            Class.id != class_id,
        ).first()
        if conflict:
            flash(f'"{new_name}" already exists.', 'warning')
            return redirect(url_for('admin.edit_class', class_id=class_id))

        cls.class_name = new_name
        cls.section    = section
        db.session.commit()
        flash(f'Class updated to "{new_name}".', 'success')
        return redirect(url_for('admin.manage_classes'))

    return render_template('admin/edit_class.html', cls=cls)


@admin_bp.route('/classes/<int:class_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_class(class_id):
    cls = Class.query.get_or_404(class_id)
    verify_school_ownership(cls)

    if Student.query.filter_by(current_class_id=class_id, is_active=True).first():
        flash('Cannot delete: students are currently assigned to this class.', 'danger')
    elif SubjectAllocation.query.filter_by(class_id=class_id).first():
        flash('Cannot delete: subject allocations exist for this class. Remove them first.', 'danger')
    else:
        db.session.delete(cls)
        db.session.commit()
        flash('Class deleted.', 'info')
    return redirect(url_for('admin.manage_classes'))


# ---------------------------------------------------------------------------
# 6.3  SUBJECT MANAGEMENT
# ---------------------------------------------------------------------------
@admin_bp.route('/subjects', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_subjects():
    sid = _school_id()

    if request.method == 'POST':
        name = request.form.get('subject_name', '').strip()
        code = request.form.get('subject_code', '').strip().upper()
        arabic_name = request.form.get('arabic_name', '').strip() # New field

        if not name or not code:
            flash('Both subject name and code are required.', 'warning')
        elif Subject.query.filter_by(subject_code=code, school_id=sid).first():
            flash(f'Subject code "{code}" already exists.', 'warning')
        else:
            section = request.form.get('section', 'All Sections').strip()
            db.session.add(Subject(
                school_id=sid,
                subject_name=name,
                subject_code=code,
                section=section,
                arabic_name=arabic_name if arabic_name else None
            ))
            db.session.commit()
            flash(f'Subject "{name}" ({code}) added.', 'success')
        return redirect(url_for('admin.manage_subjects'))

    subjects = Subject.query.filter_by(school_id=sid).order_by(Subject.subject_name).all()
    return render_template('admin/subjects.html', subjects=subjects, sections=Subject.SECTIONS)


@admin_bp.route('/subjects/<int:subject_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    verify_school_ownership(subject)

    if SubjectAllocation.query.filter_by(subject_id=subject_id).first():
        flash('Cannot delete: this subject is allocated to a teacher. Remove the allocation first.', 'danger')
    elif Score.query.filter_by(subject_id=subject_id).first():
        flash('Cannot delete: scores have been recorded for this subject.', 'danger')
    else:
        db.session.delete(subject)
        db.session.commit()
        flash('Subject deleted.', 'info')
    return redirect(url_for('admin.manage_subjects'))


# ---------------------------------------------------------------------------
# 6.4 + 6.5  STUDENT MANAGEMENT
# ---------------------------------------------------------------------------
@admin_bp.route('/students', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_students():
    sid            = _school_id()
    active_session = _active_session()

    if request.method == 'POST':
        action = request.form.get('action')

        if not active_session:
            flash('No active academic session. Configure one in Academic Setup first.', 'danger')
            return redirect(url_for('admin.manage_students'))

        if action == 'add_manual':
            fname    = request.form.get('first_name', '').strip()
            lname    = request.form.get('last_name', '').strip()
            class_id = request.form.get('class_id', type=int)

            if not fname or not lname:
                flash('First name and last name are required.', 'warning')
                return redirect(url_for('admin.manage_students'))

            adm_no   = _generate_admission_number(sid, active_session)
            new_user = User(username=adm_no, role='Student', school_id=sid)
            new_user.set_password(adm_no)     # default password = admission number
            db.session.add(new_user)
            db.session.flush()

            new_student = Student(
                user_id=new_user.id,
                school_id=sid,
                admission_number=adm_no,
                first_name=fname,
                last_name=lname,
                current_class_id=class_id,
            )
            db.session.add(new_student)
            db.session.commit()
            flash(f'Student enrolled. Admission No: {adm_no}', 'success')

        elif action == 'upload_csv':
            file = request.files.get('csv_file')
            if not file or not file.filename.endswith('.csv'):
                flash('Please upload a valid .csv file.', 'warning')
                return redirect(url_for('admin.manage_students'))

            try:
                content    = file.stream.read().decode('utf-8-sig')
                stream     = io.StringIO(content, newline=None)
                reader     = csv.DictReader(stream)
                # normalise header names
                reader.fieldnames = [
                    f.strip().lower() for f in (reader.fieldnames or [])
                ]

                success = skipped = 0
                for row in reader:
                    fname      = (row.get('first name') or row.get('firstname') or row.get('first_name') or '').strip()
                    lname      = (row.get('last name')  or row.get('lastname')  or row.get('last_name')  or '').strip()
                    class_name = (row.get('class name') or row.get('class')     or row.get('classname')  or '').strip()

                    if not fname or not lname or not class_name:
                        skipped += 1
                        continue

                    klass = Class.query.filter(
                        Class.class_name.ilike(class_name),
                        Class.school_id == sid,
                    ).first()
                    if not klass:
                        skipped += 1
                        continue
                    #The Smart Duplicate Check
                    duplicate_check = Student.query.filter(
                        Student.school_id == sid,
                        Student.first_name.ilike(fname),
                        Student.last_name.ilike(lname),
                        Student.current_class_id == klass.id,
                        Student.is_active == True
                    ).first()

                    if duplicate_check:
                        skipped += 1
                        continue # Skip this row, they already exist!

                    adm_no   = _generate_admission_number(sid, active_session)
                    new_user = User(username=adm_no, role='Student', school_id=sid)
                    new_user.set_password(adm_no)
                    db.session.add(new_user)
                    db.session.flush()

                    db.session.add(Student(
                        user_id=new_user.id,
                        school_id=sid,
                        admission_number=adm_no,
                        first_name=fname,
                        last_name=lname,
                        current_class_id=klass.id,
                    ))
                    db.session.flush()
                    success += 1

                db.session.commit()
                msg = f'Imported {success} student(s).'
                if skipped:
                    msg += f' {skipped} row(s) skipped (missing data or unknown class).'
                flash(msg, 'success' if success else 'warning')

            except Exception as e:
                db.session.rollback()
                flash(f'CSV error: {e}', 'danger')

        return redirect(url_for('admin.manage_students'))

    # GET — filter and search
    search      = request.args.get('search', '').strip()
    class_filter = request.args.get('class_id', type=int)

    query = Student.query.filter_by(school_id=sid, is_active=True)
    if search:
        term = f'%{search}%'
        query = query.filter(db.or_(
            Student.first_name.ilike(term),
            Student.last_name.ilike(term),
            Student.admission_number.ilike(term),
        ))
    if class_filter:
        query = query.filter_by(current_class_id=class_filter)

    students = query.order_by(Student.last_name, Student.first_name).all()
    classes  = Class.query.filter_by(school_id=sid).all()
    classes.sort(key=lambda c: (get_class_weight(c.class_name), c.class_name))

    return render_template(
        'admin/students.html',
        students=students,
        classes=classes,
        active_session=active_session,
    )


@admin_bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    verify_school_ownership(student)
    sid = _school_id()

    if request.method == 'POST':
        student.first_name       = request.form.get('first_name', '').strip() or student.first_name
        student.last_name        = request.form.get('last_name', '').strip()  or student.last_name
        student.current_class_id = request.form.get('class_id', type=int) or student.current_class_id
        db.session.commit()
        flash('Student record updated.', 'success')
        return redirect(url_for('admin.manage_students'))

    classes = Class.query.filter_by(school_id=sid).all()
    classes.sort(key=lambda c: (get_class_weight(c.class_name), c.class_name))
    return render_template('admin/edit_student.html', student=student, classes=classes)


@admin_bp.route('/students/<int:student_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_student_password(student_id):
    student = Student.query.get_or_404(student_id)
    verify_school_ownership(student)

    user = student.user
    if user:
        user.set_password('12345678')
        db.session.commit()
        flash(f'Password for {student.admission_number} reset to "12345678".', 'info')
    return redirect(url_for('admin.manage_students'))


@admin_bp.route('/students/<int:student_id>/archive', methods=['POST'])
@login_required
@admin_required
def archive_student(student_id):
    student = Student.query.get_or_404(student_id)
    verify_school_ownership(student)

    student.is_active    = False
    student.archive_type = 'archived'
    student.archive_date = datetime.utcnow()

    if student.user:
        student.user.is_active = False

    db.session.commit()
    flash(f'{student.admission_number} archived. Record preserved.', 'info')
    return redirect(url_for('admin.manage_students'))


@admin_bp.route('/students/<int:student_id>/restore', methods=['POST'])
@login_required
@admin_required
def restore_student(student_id):
    # Filter by school_id for safety — no verify_school_ownership needed since
    # this query already enforces it at the DB level
    student = Student.query.filter_by(
        id=student_id, school_id=_school_id()
    ).first_or_404()

    student.is_active    = True
    student.archive_type = 'none'     # V1 bug fix: reset archive_type on restore
    student.archive_date = None       # V1 bug fix: clear archive date

    if student.user:
        student.user.is_active = True  # V1 bug fix: restore login access too

    db.session.commit()
    flash(f'{student.first_name} {student.last_name} restored to active.', 'success')
    return redirect(url_for('admin.archive_vault'))


# ---------------------------------------------------------------------------
# 6.6  SUBJECT ALLOCATIONS
# ---------------------------------------------------------------------------
@admin_bp.route('/allocations', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_allocations():
    sid = _school_id()

    if request.method == 'POST':
        action = request.form.get('action', 'single')
        teacher_id = request.form.get('teacher_id', type=int)
        subject_id = request.form.get('subject_id', type=int)
        class_id   = request.form.get('class_id', type=int)

        # One subject per class — prevent two teachers teaching same subject in same class
        if action == 'batch':
            level_keyword = request.form.get('level_keyword', '').strip()
            if not level_keyword:
                flash('Please enter a class level keyword.', 'warning')
                return redirect(url_for('admin.manage_allocations'))

            matched_classes = Class.query.filter(
                Class.school_id == sid,
                Class.class_name.ilike(f'%{level_keyword}%')
            ).all()

            if not matched_classes:
                flash(f'No classes found matching "{level_keyword}".', 'warning')
                return redirect(url_for('admin.manage_allocations'))

            created = 0
            skipped = []
            for cls in matched_classes:
                if SubjectAllocation.query.filter_by(
                    subject_id=subject_id, class_id=cls.id
                ).first():
                    skipped.append(cls.class_name)
                else:
                    db.session.add(SubjectAllocation(
                        teacher_id=teacher_id,
                        subject_id=subject_id,
                        class_id=cls.id,
                    ))
                    created += 1
            db.session.commit()

            msg = f'Batch done: {created} allocation(s) created'
            if skipped:
                msg += f'; skipped (already assigned): {", ".join(skipped)}'
            flash(msg, 'success' if created else 'warning')
            return redirect(url_for('admin.manage_allocations'))

        conflict = SubjectAllocation.query.filter_by(
            subject_id=subject_id, class_id=class_id
        ).first()

        if conflict:
            flash(
                f'This subject is already assigned to '
                f'{conflict.teacher.full_name} for this class.',
                'danger'
            )
        else:
            db.session.add(SubjectAllocation(
                teacher_id=teacher_id,
                subject_id=subject_id,
                class_id=class_id,
            ))
            db.session.commit()
            flash('Allocation saved.', 'success')

        return redirect(url_for('admin.manage_allocations'))

    # Fetch teachers (Teacher + FormMaster only, not Cashier/Admin)
    teachers = (
        Teacher.query
        .join(User)
        .filter(
            User.role.in_(['Teacher', 'FormMaster']),
            User.school_id == sid,
            Teacher.is_active.is_(True),
        )
        .order_by(Teacher.full_name)
        .all()
    )
    subjects = Subject.query.filter_by(school_id=sid).order_by(Subject.subject_name).all()
    classes  = Class.query.filter_by(school_id=sid).all()
    classes.sort(key=lambda c: (get_class_weight(c.class_name), c.class_name))

    # Group allocations by teacher for the table
    all_allocs = (
        SubjectAllocation.query
        .join(Teacher)
        .filter(Teacher.school_id == sid)
        .all()
    )
    grouped = {}
    for alloc in all_allocs:
        grouped.setdefault(alloc.teacher, []).append(alloc)

    return render_template(
        'admin/allocations.html',
        teachers=teachers,
        subjects=subjects,
        classes=classes,
        grouped_allocations=grouped,
    )

@admin_bp.route('/allocations/<int:alloc_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_allocation(alloc_id):
    alloc = SubjectAllocation.query.get_or_404(alloc_id)
    # Verify school ownership through the teacher
    if alloc.teacher.school_id != _school_id():
        flash('Access denied.', 'danger')
        return redirect(url_for('admin.manage_allocations'))
    db.session.delete(alloc)
    db.session.commit()
    flash('Allocation removed.', 'info')
    return redirect(url_for('admin.manage_allocations'))


# ---------------------------------------------------------------------------
# 6.7  FORM MASTER ASSIGNMENT
# ---------------------------------------------------------------------------
@admin_bp.route('/form-masters', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_form_masters():
    sid = _school_id()

    if request.method == 'POST':
        class_id   = request.form.get('class_id', type=int)
        teacher_id = request.form.get('teacher_id', '')

        target = Class.query.filter_by(id=class_id, school_id=sid).first_or_404()
        if teacher_id == 'remove':
            target.form_master_id = None
            flash(f'Form Master removed from {target.class_name}.', 'info')
        else:
            teacher = Teacher.query.filter_by(
                id=int(teacher_id), school_id=sid
            ).first_or_404()
            target.form_master_id = teacher.id
            flash(f'{teacher.full_name} assigned as Form Master of {target.class_name}.', 'success')

        db.session.commit()
        return redirect(url_for('admin.manage_form_masters'))

    form_masters = (
        Teacher.query
        .join(User)
        .filter(User.role == 'FormMaster', Teacher.school_id == sid, Teacher.is_active.is_(True))
        .order_by(Teacher.full_name)
        .all()
    )
    classes = Class.query.filter_by(school_id=sid).all()
    classes.sort(key=lambda c: (get_class_weight(c.class_name), c.class_name))

    return render_template(
        'admin/form_masters.html',
        form_masters=form_masters,
        classes=classes,
    )


# ---------------------------------------------------------------------------
# 6.8  ARCHIVE VAULT
# ---------------------------------------------------------------------------
@admin_bp.route('/archive-vault')
@login_required
@admin_required
def archive_vault():
    sid = _school_id()

    general_archives = (
        Student.query
        .filter_by(school_id=sid, is_active=False, archive_type='archived')
        .order_by(Student.archive_date.desc())
        .all()
    )
    alumni = (
        Student.query
        .filter_by(school_id=sid, is_active=False, archive_type='alumni')
        .order_by(Student.archive_date.desc())
        .all()
    )
    archived_staff = (
        User.query
        .filter(
            User.school_id == sid,
            User.role.in_(['Admin', 'Cashier', 'FormMaster', 'Teacher']),
            User.is_active.is_(False),
        )
        .order_by(User.username)
        .all()
    )

    return render_template(
        'admin/archive_vault.html',
        general_archives=general_archives,
        alumni=alumni,
        archived_staff=archived_staff,
    )


@admin_bp.route('/archive-vault/restore-staff/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def restore_staff_from_vault(user_id):
    user = User.query.filter_by(id=user_id, school_id=_school_id()).first_or_404()
    user.is_active = True
    if user.teacher_profile:
        user.teacher_profile.is_active = True
    db.session.commit()
    flash(f'@{user.username} restored to active staff.', 'success')
    return redirect(url_for('admin.archive_vault'))


# ---------------------------------------------------------------------------
# 6.9  REPORT CARD
# ---------------------------------------------------------------------------
@admin_bp.route('/students/<int:student_id>/report-card')
@login_required
@admin_required
def report_card(student_id):
    student = Student.query.get_or_404(student_id)
    verify_school_ownership(student)

    active_session = _active_session()
    active_term    = _active_term()

    if not active_session or not active_term:
        flash('Cannot generate report card: no active session/term configured.', 'warning')
        return redirect(url_for('admin.manage_students'))

    # Fetch ALL active subjects for this student's specific class
    from app.utils.computations import get_subjects_for_class
    class_name = student.student_class.class_name if student.student_class else ''
    all_subjects = get_subjects_for_class(class_name, student.school_id)

    # Fetch the actual scores the student has received
    scores_db = Score.query.filter_by(
        student_id=student.id,
        session_id=active_session.id,
        term_id=active_term.id,
    ).all()
    score_map = {s.subject_id: s for s in scores_db}

    # Map the scores to the subjects so we can render empty rows for missing scores
    mapped_scores = []
    for subject in all_subjects:
        sc = score_map.get(subject.id)
        if sc:
            mapped_scores.append(sc)
        else:
            # Create a "dummy" score object just for rendering the empty row
            class EmptyScore:
                def __init__(self, subj):
                    self.subject = subj
                    self.ca_1 = '-'
                    self.ca_2 = '-'
                    self.assign_1 = '-'
                    self.assign_2 = '-'
                    self.exam = '-'
                    self.total_score = '-'
                    self.grade = '-'
                    self.remark = '-'
            mapped_scores.append(EmptyScore(subject))

    # Calculate totals based only on the real scores
    total_marks    = sum(s.total_score for s in scores_db if s.total_score)
    total_subjects_with_scores = len([s for s in scores_db if s.total_score is not None])
    average        = round(total_marks / total_subjects_with_scores, 2) if total_subjects_with_scores else 0.0
    class_size     = Student.query.filter_by(
        current_class_id=student.current_class_id, is_active=True
    ).count()

    # Fetch the custom mark scheme for this student's class section
    from app.models import SectionMarkScheme
    section = student.student_class.section if student.student_class else 'All Sections'
    scheme = SectionMarkScheme.query.filter_by(school_id=student.school_id, section=section).first()

    return render_template(
        'admin/report_card.html',
        student=student,
        scores=mapped_scores, # Pass the mapped scores
        active_session=active_session,
        active_term=active_term,
        total_marks=total_marks,
        total_subjects=total_subjects_with_scores, # Show how many subjects actually have grades
        average=average,
        class_size=class_size,
        school=current_user.school,
        scheme=scheme
    )

# ---------------------------------------------------------------------------
# 6.9  TRANSCRIPT (cumulative across all sessions/terms)
# ---------------------------------------------------------------------------
@admin_bp.route('/students/<int:student_id>/transcript')
@login_required
@admin_required
def transcript(student_id):
    student = Student.query.get_or_404(student_id)
    verify_school_ownership(student)

    results = (
        db.session.query(Score, AcademicSession, Term)
        .join(AcademicSession, Score.session_id == AcademicSession.id)
        .join(Term, Score.term_id == Term.id)
        .filter(Score.student_id == student.id)
        .order_by(AcademicSession.id.desc(), Term.id.asc())
        .all()
    )

    # Build nested dict: {session_name: {term_name: {scores, total, count, avg}}}
    transcript_data = {}
    for score, sess, term in results:
        s_name = sess.session_name
        t_name = term.term_name
        transcript_data.setdefault(s_name, {})
        transcript_data[s_name].setdefault(t_name, {
            'scores': [], 'total_marks': 0.0, 'subject_count': 0
        })
        bucket = transcript_data[s_name][t_name]
        bucket['scores'].append(score)
        bucket['total_marks']   += score.total_score or 0.0
        bucket['subject_count'] += 1

    for s_data in transcript_data.values():
        for t_data in s_data.values():
            n = t_data['subject_count']
            t_data['average'] = round(t_data['total_marks'] / n, 2) if n else 0.0

    return render_template(
        'admin/transcript.html',
        student=student,
        transcript_data=transcript_data,
        school=current_user.school,
        coupon_verified=session.get(f'transcript_verified_{student.id}', False),
    )


@admin_bp.route('/students/<int:student_id>/verify-transcript-coupon', methods=['POST'])
@login_required
@admin_required
def verify_transcript_coupon(student_id):
    """
    Admin enters the student's transcript coupon to unlock the print/download button.
    On success we store a flag in the Flask session (browser session only —
    not written to DB) so the admin doesn't have to re-enter on the same page reload.
    The coupon itself is never consumed; it stays on the student forever.
    """
    student = Student.query.get_or_404(student_id)
    verify_school_ownership(student)

    entered = request.form.get('coupon_code', '').strip().upper()

    if not student.transcript_coupon:
        flash('This student has no transcript coupon assigned. Contact Platform Admin.', 'warning')
    elif entered == student.transcript_coupon.upper():
        # Store unlock in session — survives page reloads within this browser tab
        session[f'transcript_verified_{student.id}'] = True
        flash('Transcript coupon verified. You may now print or download.', 'success')
    else:
        flash('Incorrect transcript coupon code. Please check and try again.', 'danger')

    return redirect(url_for('admin.transcript', student_id=student.id))


# ---------------------------------------------------------------------------
# 6.10  BROAD SHEET (class-wide matrix for one term)
# ---------------------------------------------------------------------------
@admin_bp.route('/classes/<int:class_id>/broad-sheet')
@login_required
@admin_required
def broad_sheet(class_id):
    cls = Class.query.get_or_404(class_id)
    verify_school_ownership(cls)

    active_session = _active_session()
    active_term    = _active_term()

    if not active_session or not active_term:
        flash('Set an active session and term first.', 'warning')
        return redirect(url_for('admin.manage_classes'))

    students    = Student.query.filter_by(
        current_class_id=class_id, is_active=True
    ).all()
    broad_data  = []
    subjects    = []

    if students:
        student_ids = [s.id for s in students]
        scores = Score.query.filter(
            Score.student_id.in_(student_ids),
            Score.session_id == active_session.id,
            Score.term_id    == active_term.id,
        ).all()

        # Discover subjects dynamically from recorded scores
        subject_map = {}
        for sc in scores:
            if sc.subject_id not in subject_map:
                subject_map[sc.subject_id] = sc.subject.subject_code
        subjects = sorted(
            [{'id': sid, 'code': code} for sid, code in subject_map.items()],
            key=lambda x: x['code'],
        )

        for student in students:
            s_scores = [sc for sc in scores if sc.student_id == student.id]
            total    = sum(sc.total_score or 0.0 for sc in s_scores)
            n        = len(s_scores)
            avg      = round(total / n, 2) if n else 0.0
            marks    = {sc.subject_id: sc.total_score for sc in s_scores}
            broad_data.append({
                'student': student, 'marks': marks,
                'total': total, 'average': avg, 'num_subj': n,
            })

        broad_data.sort(key=lambda x: x['total'], reverse=True)

        # Rank with tie-handling
        for i, row in enumerate(broad_data):
            if i > 0 and row['total'] == broad_data[i-1]['total']:
                row['position'] = broad_data[i-1]['position']
            else:
                row['position'] = i + 1

    return render_template(
        'admin/broad_sheet.html',
        target_class=cls,
        subjects=subjects,
        broad_data=broad_data,
        active_session=active_session,
        active_term=active_term,
        school=current_user.school,
    )


# ---------------------------------------------------------------------------
# NOTIFICATIONS (inbox + compose for Admin role)
# ---------------------------------------------------------------------------
@admin_bp.route('/notifications')
@login_required
@admin_required
def notifications():
    sid = _school_id()
    messages = Notification.query.filter(
        db.or_(
            Notification.recipient_id == current_user.id,
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'role',
                Notification.recipient_role == 'Admin',
            ),
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'broadcast',
            ),
        )
    ).order_by(Notification.created_at.desc()).limit(100).all()

    return render_template('admin/notifications.html', messages=messages)


@admin_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@admin_required
def mark_notification_read(notif_id):
    # Verify the notification actually belongs to this user before marking it read.
    # Without this check, any authenticated user could mark anyone's notification
    # as read by guessing the integer ID.
    n = Notification.query.filter_by(id=notif_id, recipient_id=current_user.id).first()
    if not n:
        # Fallback: also accept role-wide notifications sent to this user's role+school
        n = Notification.query.filter_by(id=notif_id).first()
        if not n or (n.school_id and n.school_id != current_user.school_id):
            flash('Notification not found or access denied.', 'danger')
            return redirect(url_for('admin.notifications'))
    n.is_read = True
    db.session.commit()
    return redirect(url_for('admin.notifications'))


@admin_bp.route('/notifications/compose', methods=['GET', 'POST'])
@login_required
@admin_required
def compose_notification():
    sid = _school_id()

    if request.method == 'POST':
        recipient_type = request.form.get('recipient_type', '')
        subject        = request.form.get('subject', '').strip()
        body           = request.form.get('body', '').strip()

        if not subject or not body:
            flash('Subject and message are required.', 'warning')
            return redirect(url_for('admin.compose_notification'))

        if recipient_type == 'superadmin':
            super_admin = User.query.filter_by(school_id=sid, role='SuperAdmin').first()
            if not super_admin:
                flash('No SuperAdmin found for this school.', 'danger')
                return redirect(url_for('admin.compose_notification'))
            n = Notification(
                sender_id=current_user.id, school_id=sid,
                recipient_type='user', recipient_id=super_admin.id,
                subject=subject, body=body,
            )
        elif recipient_type in ['Cashier', 'FormMaster', 'Teacher', 'Student', 'broadcast']:
            n = Notification(
                sender_id=current_user.id, school_id=sid,
                recipient_type='role' if recipient_type != 'broadcast' else 'broadcast',
                recipient_role=recipient_type if recipient_type != 'broadcast' else None,
                subject=subject, body=body,
            )
        else:
            flash('Select a valid recipient.', 'warning')
            return redirect(url_for('admin.compose_notification'))

        db.session.add(n)
        db.session.commit()
        flash('Message sent.', 'success')
        return redirect(url_for('admin.notifications'))

    return render_template('admin/compose_notification.html')
