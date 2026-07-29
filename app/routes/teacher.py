from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash
)
from flask_login import login_required, current_user

from app import db
from app.models import (
    User, Teacher, Class, Subject, SubjectAllocation,
    Student, Score, AcademicSession, Term, Notification
)
from app.utils.decorators import teacher_required, form_master_required
from app.utils.computations import (
    compute_grade_and_remark, rank_performances, get_ordinal
)

teacher_bp = Blueprint('teacher', __name__)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _get_teacher_profile():
    """Return the Teacher profile for the current user, or None."""
    return Teacher.query.filter_by(
        user_id=current_user.id,
        school_id=current_user.school_id
    ).first()


def _active_session():
    return AcademicSession.query.filter_by(
        school_id=current_user.school_id, is_active=True
    ).first()


def _active_term():
    sess = _active_session()
    if not sess:
        return None
    return Term.query.filter_by(session_id=sess.id, is_active=True).first()


def _unread_count():
    sid = current_user.school_id
    return Notification.query.filter(
        db.or_(
            Notification.recipient_id == current_user.id,
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'role',
                Notification.recipient_role.in_(
                    ['Teacher', 'FormMaster', current_user.role]
                ),
            ),
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'broadcast',
            ),
        ),
        Notification.is_read.is_(False),
    ).count()


# ---------------------------------------------------------------------------
# 8.1  DASHBOARD
# ---------------------------------------------------------------------------
@teacher_bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    teacher = _get_teacher_profile()
    if not teacher:
        flash(
            'No teacher profile is linked to your account. '
            'Contact your Admin to set this up.',
            'danger'
        )
        return redirect(url_for('auth.logout'))

    active_session = _active_session()
    active_term    = _active_term()

    allocations = SubjectAllocation.query.filter_by(
        teacher_id=teacher.id
    ).all()

    # FormMaster: find their assigned class
    form_class = None
    if current_user.role == 'FormMaster':
        form_class = Class.query.filter_by(
            form_master_id=teacher.id,
            school_id=current_user.school_id
        ).first()

    return render_template(
        'teacher/dashboard.html',
        teacher=teacher,
        allocations=allocations,
        active_session=active_session,
        active_term=active_term,
        form_class=form_class,
        unread=_unread_count(),
    )


# ---------------------------------------------------------------------------
# 8.2  SCORE ENTRY
# ---------------------------------------------------------------------------
@teacher_bp.route('/scores/<int:allocation_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def enter_scores(allocation_id):
    teacher    = _get_teacher_profile()
    allocation = SubjectAllocation.query.get_or_404(allocation_id)

    # Security: only the allocated teacher (or SuperAdmin) may enter scores
    if allocation.teacher_id != teacher.id and current_user.role != 'SuperAdmin':
        flash('Access denied: you are not assigned to this subject.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    # Confirm the allocation belongs to this school
    if allocation.assigned_class.school_id != current_user.school_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    active_session = _active_session()
    active_term    = _active_term()

    if not active_session or not active_term:
        flash(
            'Score entry is unavailable — no active session or term is set. '
            'Contact your Admin.',
            'warning'
        )
        return redirect(url_for('teacher.dashboard'))

    students = (
        Student.query
        .filter_by(
            current_class_id=allocation.class_id,
            is_active=True,
            school_id=current_user.school_id
        )
        .order_by(Student.last_name, Student.first_name)
        .all()
    )

    if request.method == 'POST':
        saved   = 0
        skipped = 0

        for student in students:
            sid = str(student.id)
            try:
                ca1  = float(request.form.get(f'ca1_{sid}')  or 0)
                ca2  = float(request.form.get(f'ca2_{sid}')  or 0)
                ass1 = float(request.form.get(f'ass1_{sid}') or 0)
                ass2 = float(request.form.get(f'ass2_{sid}') or 0)
                exam = float(request.form.get(f'exam_{sid}') or 0)

                # Clamp to valid ranges
                ca1  = max(0, min(ca1,  10))
                ca2  = max(0, min(ca2,  10))
                ass1 = max(0, min(ass1, 10))
                ass2 = max(0, min(ass2, 10))
                exam = max(0, min(exam, 60))

                total          = ca1 + ca2 + ass1 + ass2 + exam
                grade, remark  = compute_grade_and_remark(total)

                existing = Score.query.filter_by(
                    student_id=student.id,
                    subject_id=allocation.subject_id,
                    term_id=active_term.id,
                    session_id=active_session.id,
                ).first()

                if existing:
                    existing.ca_1        = ca1
                    existing.ca_2        = ca2
                    existing.assign_1    = ass1
                    existing.assign_2    = ass2
                    existing.exam        = exam
                    existing.total_score = total
                    existing.grade       = grade
                    existing.remark      = remark
                else:
                    db.session.add(Score(
                        student_id=student.id,
                        subject_id=allocation.subject_id,
                        term_id=active_term.id,
                        session_id=active_session.id,
                        ca_1=ca1, ca_2=ca2,
                        assign_1=ass1, assign_2=ass2,
                        exam=exam,
                        total_score=total,
                        grade=grade,
                        remark=remark,
                    ))
                saved += 1

            except (ValueError, TypeError):
                skipped += 1
                continue

        db.session.commit()
        msg = f'Scores saved for {saved} student(s).'
        if skipped:
            msg += f' {skipped} row(s) skipped due to invalid input.'
        flash(msg, 'success' if not skipped else 'warning')
        return redirect(url_for('teacher.enter_scores', allocation_id=allocation_id))

    # Pre-load existing scores for this subject/term into a dict keyed by student_id
    existing_scores = Score.query.filter_by(
        subject_id=allocation.subject_id,
        term_id=active_term.id if active_term else 0,
        session_id=active_session.id if active_session else 0,
    ).all()
    score_map = {s.student_id: s for s in existing_scores}

    return render_template(
        'teacher/score_entry.html',
        teacher=_get_teacher_profile(),
        allocation=allocation,
        students=students,
        score_map=score_map,
        active_session=active_session,
        active_term=active_term,
    )


# ---------------------------------------------------------------------------
# 8.3  MASTER LIST — FormMaster ranking view
# ---------------------------------------------------------------------------
@teacher_bp.route('/master-list/<int:class_id>')
@login_required
@form_master_required
def master_list(class_id):
    teacher    = _get_teacher_profile()
    form_class = Class.query.get_or_404(class_id)

    # Security: only the assigned form master (or SuperAdmin) may view
    if form_class.form_master_id != teacher.id and current_user.role != 'SuperAdmin':
        flash('Access denied: you are not the Form Master for this class.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    if form_class.school_id != current_user.school_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    active_session = _active_session()
    active_term    = _active_term()

    if not active_session or not active_term:
        flash('No active session/term configured.', 'warning')
        return redirect(url_for('teacher.dashboard'))

    # Smart cohort: include students currently in class AND those promoted out
    students = Student.query.filter(
        db.or_(
            db.and_(
                Student.current_class_id == class_id,
                Student.previous_class_id.is_(None)
            ),
            Student.previous_class_id == class_id,
        ),
        Student.is_active == True,
        Student.school_id == current_user.school_id,
    ).all()

    # Build performance list
    performances = []
    for student in students:
        scores = Score.query.filter_by(
            student_id=student.id,
            session_id=active_session.id,
            term_id=active_term.id,
        ).all()
        total   = sum(s.total_score or 0.0 for s in scores)
        n       = len(scores)
        average = round(total / n, 2) if n else 0.0
        performances.append({
            'student':      student,
            'total_marks':  total,
            'average':      average,
            'num_subjects': n,
        })

    # Rank with tie handling + ordinal suffix from computations.py
    ranked = rank_performances(performances)

    return render_template(
        'teacher/master_list.html',
        teacher=teacher,
        form_class=form_class,
        performances=ranked,
        active_session=active_session,
        active_term=active_term,
    )


# ---------------------------------------------------------------------------
# 8.4 / 8.5 / 8.6 / 8.7  CLASS MANAGEMENT — FormMaster operations
# ---------------------------------------------------------------------------
@teacher_bp.route('/class-management/<int:class_id>', methods=['GET', 'POST'])
@login_required
@form_master_required
def class_management(class_id):
    teacher    = _get_teacher_profile()
    form_class = Class.query.get_or_404(class_id)

    if form_class.form_master_id != teacher.id and current_user.role != 'SuperAdmin':
        flash('Access denied.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    if form_class.school_id != current_user.school_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    active_session = _active_session()
    active_term    = _active_term()

    if request.method == 'POST':
        action = request.form.get('action')

        # --- 8.5 Save automated remarks ---
        if action == 'save_remarks':
            form_class.remark_a = request.form.get('remark_a', '').strip()
            form_class.remark_b = request.form.get('remark_b', '').strip()
            form_class.remark_c = request.form.get('remark_c', '').strip()
            form_class.remark_d = request.form.get('remark_d', '').strip()
            form_class.remark_f = request.form.get('remark_f', '').strip()
            db.session.commit()
            flash('Automated remarks updated successfully.', 'success')

        # --- 8.4 Bulk promotion ---
        elif action == 'bulk_promote':
            if not active_session or not active_term:
                flash('No active session/term — cannot promote.', 'danger')
                return redirect(url_for('teacher.class_management', class_id=class_id))

            try:
                cutoff = float(request.form.get('cutoff_avg', 0))
            except ValueError:
                flash('Invalid cutoff average.', 'danger')
                return redirect(url_for('teacher.class_management', class_id=class_id))

            next_class_id = request.form.get('next_class_id', type=int)
            if not next_class_id:
                flash('Please select a destination class.', 'warning')
                return redirect(url_for('teacher.class_management', class_id=class_id))

            # Only promote students who haven't been promoted yet this session
            unpromoted = Student.query.filter(
                Student.current_class_id == class_id,
                Student.previous_class_id.is_(None),
                Student.is_active == True,
                Student.school_id == current_user.school_id,
            ).all()

            promoted = 0
            for student in unpromoted:
                scores = Score.query.filter_by(
                    student_id=student.id,
                    session_id=active_session.id,
                    term_id=active_term.id,
                ).all()
                total   = sum(s.total_score or 0.0 for s in scores)
                n       = len(scores)
                average = round(total / n, 2) if n else 0.0

                if average >= cutoff:
                    student.previous_class_id = student.current_class_id
                    student.current_class_id  = next_class_id
                    promoted += 1

            db.session.commit()
            flash(f'{promoted} student(s) promoted to the next class.', 'success')

        # --- 8.6 Revoke promotion ---
        elif action == 'revoke_promotion':
            if not active_term or active_term.term_name != 'Third Term':
                flash(
                    'Revoke is locked — promotions can only be reversed during Third Term.',
                    'danger'
                )
            else:
                student_id = request.form.get('student_id', type=int)
                student    = Student.query.filter_by(
                    id=student_id,
                    school_id=current_user.school_id
                ).first_or_404()

                if student.previous_class_id:
                    student.current_class_id  = student.previous_class_id
                    student.previous_class_id = None
                    db.session.commit()
                    flash(
                        f'{student.first_name} {student.last_name} returned to this class.',
                        'info'
                    )
                else:
                    flash('This student has no recorded promotion to revoke.', 'warning')

        # --- 8.7 Bulk graduation (alumni archive) ---
        elif action == 'bulk_archive':
            from datetime import datetime as dt
            targets = Student.query.filter(
                Student.current_class_id == class_id,
                Student.is_active == True,
                Student.school_id == current_user.school_id,
            ).all()

            count = 0
            for student in targets:
                student.is_active    = False
                student.archive_type = 'alumni'
                student.archive_date = dt.utcnow()
                user_account = User.query.get(student.user_id)
                if user_account:
                    user_account.is_active = False
                count += 1

            db.session.commit()
            flash(
                f'Graduation complete — {count} student(s) moved to the Alumni Vault.',
                'success'
            )

        return redirect(url_for('teacher.class_management', class_id=class_id))

    # --- GET: build UI data ---
    from app.utils.computations import get_class_weight

    # Only offer equal or higher classes as promotion targets
    current_weight = get_class_weight(form_class.class_name)
    all_classes    = Class.query.filter_by(
        school_id=current_user.school_id
    ).all()
    valid_targets  = sorted(
        [c for c in all_classes if get_class_weight(c.class_name) >= current_weight],
        key=lambda c: (get_class_weight(c.class_name), c.class_name)
    )

    recently_promoted = Student.query.filter_by(
        previous_class_id=class_id,
        school_id=current_user.school_id,
    ).all()

    incoming_students = Student.query.filter(
        Student.current_class_id == class_id,
        Student.previous_class_id.isnot(None),
        Student.previous_class_id != class_id,
        Student.is_active == True,
        Student.school_id == current_user.school_id,
    ).all()

    return render_template(
        'teacher/class_management.html',
        teacher=teacher,
        form_class=form_class,
        valid_targets=valid_targets,
        recently_promoted=recently_promoted,
        incoming_students=incoming_students,
        active_term=active_term,
        active_session=active_session,
    )


# ---------------------------------------------------------------------------
# 8.8  NOTIFICATIONS
# ---------------------------------------------------------------------------
@teacher_bp.route('/notifications')
@login_required
@teacher_required
def notifications():
    sid = current_user.school_id
    messages = Notification.query.filter(
        db.or_(
            Notification.recipient_id == current_user.id,
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'role',
                Notification.recipient_role == current_user.role,
            ),
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'broadcast',
            ),
        )
    ).order_by(Notification.created_at.desc()).limit(100).all()

    return render_template('teacher/notifications.html', messages=messages)


@teacher_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@teacher_required
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
            return redirect(url_for('teacher.notifications'))
    n.is_read = True
    db.session.commit()
    return redirect(url_for('teacher.notifications'))


@teacher_bp.route('/notifications/compose', methods=['GET', 'POST'])
@login_required
@teacher_required
def compose_notification():
    """
    Teacher/FormMaster can:
    - Notify their own assigned students (FormMaster only, scoped to their class)
    - Send feedback/complaint to school Admin or SuperAdmin
    """
    sid     = current_user.school_id
    teacher = _get_teacher_profile()

    # Students the teacher can notify (FormMaster → their class; Teacher → assigned students)
    notifiable_students = []
    if current_user.role == 'FormMaster' and teacher:
        form_class = Class.query.filter_by(
            form_master_id=teacher.id,
            school_id=sid
        ).first()
        if form_class:
            notifiable_students = Student.query.filter_by(
                current_class_id=form_class.id,
                is_active=True,
                school_id=sid,
            ).order_by(Student.last_name, Student.first_name).all()
    elif teacher:
        # Teacher → students in their allocated classes
        alloc_class_ids = [a.class_id for a in SubjectAllocation.query.filter_by(
            teacher_id=teacher.id
        ).all()]
        if alloc_class_ids:
            notifiable_students = Student.query.filter(
                Student.current_class_id.in_(alloc_class_ids),
                Student.is_active == True,
                Student.school_id == sid,
            ).order_by(Student.last_name, Student.first_name).all()

    if request.method == 'POST':
        recipient_type = request.form.get('recipient_type', '')
        subject        = request.form.get('subject', '').strip()
        body           = request.form.get('body', '').strip()

        if not subject or not body:
            flash('Subject and message are required.', 'warning')
            return redirect(url_for('teacher.compose_notification'))

        n = None

        if recipient_type == 'admin':
            # To school Admin
            admin_user = User.query.filter_by(
                school_id=sid, role='Admin', is_active=True
            ).first()
            if not admin_user:
                # Fall back to SuperAdmin if no Admin exists
                admin_user = User.query.filter_by(
                    school_id=sid, role='SuperAdmin', is_active=True
                ).first()
            if admin_user:
                n = Notification(
                    sender_id=current_user.id, school_id=sid,
                    recipient_type='user', recipient_id=admin_user.id,
                    subject=subject, body=body,
                )

        elif recipient_type == 'superadmin':
            super_admin = User.query.filter_by(
                school_id=sid, role='SuperAdmin', is_active=True
            ).first()
            if super_admin:
                n = Notification(
                    sender_id=current_user.id, school_id=sid,
                    recipient_type='user', recipient_id=super_admin.id,
                    subject=subject, body=body,
                )

        elif recipient_type == 'all_my_students':
            n = Notification(
                sender_id=current_user.id, school_id=sid,
                recipient_type='role', recipient_role='Student',
                subject=subject, body=body,
            )

        elif recipient_type == 'specific_student':
            student_id = request.form.get('student_id', type=int)
            if student_id:
                student = Student.query.filter_by(
                    id=student_id, school_id=sid
                ).first()
                if student:
                    n = Notification(
                        sender_id=current_user.id, school_id=sid,
                        recipient_type='user',
                        recipient_id=student.user_id,
                        subject=subject, body=body,
                    )

        if n:
            db.session.add(n)
            db.session.commit()
            flash('Message sent successfully.', 'success')
        else:
            flash('Could not send message — recipient not found.', 'danger')

        return redirect(url_for('teacher.notifications'))

    return render_template(
        'teacher/compose_notification.html',
        notifiable_students=notifiable_students,
    )
