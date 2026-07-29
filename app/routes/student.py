from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session
)
from flask_login import login_required, current_user
from datetime import datetime

from app import db
from app.models import (
    Student, AcademicSession, Term, Score,
    Coupon, CouponActivation, Notification, User, Teacher
)
from app.utils.decorators import student_required

student_bp = Blueprint('student', __name__)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _get_student():
    """Fetch the Student profile linked to the current logged-in user."""
    return Student.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).first()


def _active_term_for_school(school_id):
    active_session = AcademicSession.query.filter_by(
        school_id=school_id, is_active=True
    ).first()
    if not active_session:
        return None, None
    active_term = Term.query.filter_by(
        session_id=active_session.id, is_active=True
    ).first()
    return active_session, active_term


def _has_activated_coupon(student_id, term_id):
    """Check if a student has already activated a coupon for this term."""
    return CouponActivation.query.filter_by(
        student_id=student_id,
        term_id=term_id,
    ).first() is not None


def _unread_count(student_id):
    student = Student.query.get(student_id)
    if not student:
        return 0
    return Notification.query.filter(
        db.or_(
            Notification.recipient_id == current_user.id,
            db.and_(
                Notification.school_id == student.school_id,
                Notification.recipient_type == 'role',
                Notification.recipient_role == 'Student',
            ),
            db.and_(
                Notification.school_id == student.school_id,
                Notification.recipient_type == 'broadcast',
            ),
        ),
        Notification.is_read.is_(False),
    ).count()


# ---------------------------------------------------------------------------
# 9.1  DASHBOARD
# ---------------------------------------------------------------------------
@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    student = _get_student()
    if not student:
        flash('No student profile found for your account. Contact Admin.', 'danger')
        return redirect(url_for('auth.logout'))

    active_session, active_term = _active_term_for_school(student.school_id)

    # All sessions for this school (for historical result selection)
    all_sessions = AcademicSession.query.filter_by(
        school_id=student.school_id
    ).order_by(AcademicSession.id.desc()).all()

    # Coupon activation status for active term
    active_coupon_status = None
    if active_term:
        active_coupon_status = _has_activated_coupon(student.id, active_term.id)

    return render_template(
        'student/dashboard.html',
        student=student,
        active_session=active_session,
        active_term=active_term,
        all_sessions=all_sessions,
        active_coupon_status=active_coupon_status,
        unread=_unread_count(student.id),
    )


# ---------------------------------------------------------------------------
# 9.2  COUPON ACTIVATION GATE
# Student enters their term coupon to unlock result access for that term.
# ---------------------------------------------------------------------------
@student_bp.route('/activate-coupon', methods=['POST'])
@login_required
@student_required
def activate_coupon():
    student = _get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    _, active_term = _active_term_for_school(student.school_id)
    if not active_term:
        flash('No active term is currently set. Contact your Admin.', 'warning')
        return redirect(url_for('student.dashboard'))

    # Check if already activated — block double activation
    if _has_activated_coupon(student.id, active_term.id):
        flash('You have already activated your coupon for this term.', 'info')
        return redirect(url_for('student.view_result', term_id=active_term.id))

    entered_code = request.form.get('coupon_code', '').strip().upper()
    if not entered_code:
        flash('Please enter a coupon code.', 'warning')
        return redirect(url_for('student.dashboard'))

    # Look up the code — must belong to this school, this term, and be unused
    coupon = Coupon.query.filter_by(
        code=entered_code,
        school_id=student.school_id,
        is_used=False,
    ).first()

    if not coupon:
        flash(
            'Invalid or already-used coupon code. '
            'Check your code and try again, or contact your school.',
            'danger'
        )
        return redirect(url_for('student.dashboard'))

    # Validate it belongs to the current active term
    if not coupon.is_valid_for_redemption(student.school_id, active_term.id):
        flash(
            'This coupon code is not valid for the current term. '
            'Make sure you are using this term\'s code.',
            'danger'
        )
        return redirect(url_for('student.dashboard'))

    # Lock the coupon to this student
    coupon.is_used    = True
    coupon.used_by_id = student.id
    coupon.used_at    = datetime.utcnow()

    # Create the permanent activation record
    activation = CouponActivation(
        student_id=student.id,
        term_id=active_term.id,
        coupon_id=coupon.id,
    )
    db.session.add(activation)
    db.session.commit()

    flash(
        f'Coupon activated successfully! '
        f'Your results for {active_term.term_name} are now unlocked.',
        'success'
    )
    return redirect(url_for('student.view_result', term_id=active_term.id))


# ---------------------------------------------------------------------------
# 9.3  VIEW RESULT (report card)
# Gated behind: coupon activation + result release (is_released)
# ---------------------------------------------------------------------------
@student_bp.route('/result/<int:term_id>')
@login_required
@student_required
def view_result(term_id):
    student = _get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    term = Term.query.get_or_404(term_id)
    session_obj = AcademicSession.query.get_or_404(term.session_id)

    # Security: confirm this term belongs to the student's school
    if session_obj.school_id != student.school_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('student.dashboard'))

    # Gate 1: Coupon must be activated for this term
    if not _has_activated_coupon(student.id, term.id):
        flash(
            'You need to activate your coupon code before viewing '
            'results for this term.',
            'warning'
        )
        return redirect(url_for('student.dashboard'))

    # Gate 2: Cashier must have released results
    score_check = Score.query.filter_by(
        student_id=student.id,
        term_id=term.id,
        session_id=session_obj.id,
    ).first()

    if not score_check:
        flash('No scores have been recorded for you in this term yet.', 'info')
        return redirect(url_for('student.dashboard'))

    if not score_check.is_released:
        flash(
            'Your results have not been released yet. '
            'Contact your school for more information.',
            'warning'
        )
        return redirect(url_for('student.dashboard'))

    # All gates passed — fetch full results
    scores = Score.query.filter_by(
        student_id=student.id,
        term_id=term.id,
        session_id=session_obj.id,
    ).all()

    total_marks    = sum((s.total_score or 0.0) for s in scores)
    total_subjects = len(scores)
    average        = round((total_marks / total_subjects), 2) if total_subjects > 0 else 0.0
    class_size     = Student.query.filter_by(
        current_class_id=student.current_class_id,
        school_id=student.school_id,
        is_active=True,
    ).count()

    return render_template(
        'student/result.html',
        student=student,
        scores=scores,
        term=term,
        session_obj=session_obj,
        total_marks=total_marks,
        total_subjects=total_subjects,
        average=average,
        class_size=class_size,
        school=current_user.school,
    )


# ---------------------------------------------------------------------------
# TRANSCRIPT — gated behind transcript_coupon
# ---------------------------------------------------------------------------
@student_bp.route('/transcript')
@login_required
@student_required
def transcript():
    student = _get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    transcript_data = {}
    coupon_verified = session.get(f'student_transcript_verified_{student.id}', False)

    if coupon_verified:
        # Build full transcript only after coupon is verified
        results = db.session.query(Score, AcademicSession, Term)\
            .join(AcademicSession, Score.session_id == AcademicSession.id)\
            .join(Term, Score.term_id == Term.id)\
            .filter(
                Score.student_id == student.id,
                AcademicSession.school_id == student.school_id,
            )\
            .order_by(AcademicSession.id.desc(), Term.id.asc())\
            .all()

        for score, session_obj, term_obj in results:
            s_name = session_obj.session_name
            t_name = term_obj.term_name
            transcript_data.setdefault(s_name, {})
            transcript_data[s_name].setdefault(t_name, {
                'scores': [], 'total_marks': 0.0, 'subject_count': 0
            })
            bucket = transcript_data[s_name][t_name]
            bucket['scores'].append(score)
            bucket['total_marks'] += (score.total_score or 0.0)
            bucket['subject_count'] += 1

        for s_data in transcript_data.values():
            for t_data in s_data.values():
                n = t_data['subject_count']
                t_data['average'] = round(t_data['total_marks'] / n, 2) if n > 0 else 0.0

    return render_template(
        'student/transcript.html',
        student=student,
        transcript_data=transcript_data,
        coupon_verified=coupon_verified,
        school=current_user.school,
    )


@student_bp.route('/transcript/verify', methods=['POST'])
@login_required
@student_required
def verify_transcript_coupon():
    student = _get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    if not student.transcript_coupon:
        flash(
            'No transcript coupon has been assigned to your account yet. '
            'Contact your school.',
            'warning'
        )
        return redirect(url_for('student.transcript'))

    entered = request.form.get('coupon_code', '').strip().upper()

    if entered == student.transcript_coupon.upper():
        session[f'student_transcript_verified_{student.id}'] = True
        flash('Transcript unlocked. You may now view and print it.', 'success')
    else:
        flash('Incorrect transcript coupon. Check your code and try again.', 'danger')

    return redirect(url_for('student.transcript'))


# ---------------------------------------------------------------------------
# 9.4  NOTIFICATIONS INBOX
# ---------------------------------------------------------------------------
@student_bp.route('/notifications')
@login_required
@student_required
def notifications():
    student = _get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    messages = Notification.query.filter(
        db.or_(
            Notification.recipient_id == current_user.id,
            db.and_(
                Notification.school_id == student.school_id,
                Notification.recipient_type == 'role',
                Notification.recipient_role == 'Student',
            ),
            db.and_(
                Notification.school_id == student.school_id,
                Notification.recipient_type == 'broadcast',
            ),
        )
    ).order_by(Notification.created_at.desc()).limit(100).all()

    return render_template('student/notifications.html', messages=messages)


@student_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@student_required
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
            return redirect(url_for('student.notifications'))
    n.is_read = True
    db.session.commit()
    return redirect(url_for('student.notifications'))


# ---------------------------------------------------------------------------
# 9.5  FEEDBACK / COMPLAINT
# Student can send to their teacher or school admin
# ---------------------------------------------------------------------------
@student_bp.route('/feedback', methods=['GET', 'POST'])
@login_required
@student_required
def feedback():
    student = _get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    sid = student.school_id

    # Build recipient options:
    # 1. School Admin(s)
    admins = User.query.filter_by(school_id=sid, role='Admin', is_active=True).all()
    # 2. Teachers assigned to the student's class via SubjectAllocation
    from app.models import SubjectAllocation
    teacher_ids = db.session.query(SubjectAllocation.teacher_id)\
        .filter_by(class_id=student.current_class_id)\
        .distinct().all()
    teachers = Teacher.query.filter(
        Teacher.id.in_([t[0] for t in teacher_ids]),
        Teacher.is_active == True,
    ).all()
    # 3. FormMaster of student's class
    from app.models import Class
    student_class = Class.query.get(student.current_class_id)
    form_master = None
    if student_class and student_class.form_master_id:
        form_master = Teacher.query.get(student_class.form_master_id)

    if request.method == 'POST':
        recipient_user_id = request.form.get('recipient_id', type=int)
        subject           = request.form.get('subject', '').strip()
        body              = request.form.get('body', '').strip()

        if not recipient_user_id or not subject or not body:
            flash('Please fill in all fields.', 'warning')
            return redirect(url_for('student.feedback'))

        # Verify recipient belongs to this school
        recipient = User.query.filter_by(
            id=recipient_user_id, school_id=sid, is_active=True
        ).first()
        if not recipient:
            flash('Invalid recipient.', 'danger')
            return redirect(url_for('student.feedback'))

        n = Notification(
            sender_id=current_user.id,
            school_id=sid,
            recipient_type='user',
            recipient_id=recipient.id,
            subject=subject,
            body=body,
        )
        db.session.add(n)
        db.session.commit()
        flash('Your message has been sent.', 'success')
        return redirect(url_for('student.notifications'))

    return render_template(
        'student/feedback.html',
        student=student,
        admins=admins,
        teachers=teachers,
        form_master=form_master,
    )
