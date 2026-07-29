from datetime import datetime

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash
)
from flask_login import login_required, current_user

from app import db
from app.models import (
    User, Student, Class, AcademicSession,
    Term, Score, Coupon, CouponActivation, Notification
)
from app.utils.decorators import cashier_required

cashier_bp = Blueprint('cashier', __name__)


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


def _unread_count():
    """Notification badge count for the cashier."""
    sid = _school_id()
    return Notification.query.filter(
        db.or_(
            Notification.recipient_id == current_user.id,
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'role',
                Notification.recipient_role == 'Cashier',
            ),
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'broadcast',
            ),
        ),
        Notification.is_read.is_(False),
    ).count()


# ---------------------------------------------------------------------------
# 7.1  DASHBOARD
# ---------------------------------------------------------------------------
@cashier_bp.route('/dashboard')
@login_required
@cashier_required
def dashboard():
    sid            = _school_id()
    active_session = _active_session()
    active_term    = _active_term()

    # Coupon summary for the active term
    coupon_total  = 0
    coupon_used   = 0
    coupon_unused = 0
    if active_term:
        coupon_total  = Coupon.query.filter_by(
            school_id=sid, term_id=active_term.id
        ).count()
        coupon_used   = Coupon.query.filter_by(
            school_id=sid, term_id=active_term.id, is_used=True
        ).count()
        coupon_unused = coupon_total - coupon_used

    # Result release summary: how many students have at least one released score
    total_students = Student.query.filter_by(
        school_id=sid, is_active=True
    ).count()

    released_students = 0
    if active_term and active_session:
        # Count distinct students with at least one released score this term
        released_students = (
            db.session.query(Score.student_id)
            .filter(
                Score.session_id == active_session.id,
                Score.term_id    == active_term.id,
                Score.is_released.is_(True),
            )
            .distinct()
            .count()
        )

    classes = Class.query.filter_by(school_id=sid).all()

    return render_template(
        'cashier/dashboard.html',
        active_session=active_session,
        active_term=active_term,
        coupon_total=coupon_total,
        coupon_used=coupon_used,
        coupon_unused=coupon_unused,
        total_students=total_students,
        released_students=released_students,
        classes=classes,
        unread=_unread_count(),
    )


# ---------------------------------------------------------------------------
# 7.2  COUPON LIST (read-only, filtered, printable)
# Cashier sees only their school's coupons for the active term.
# They cannot generate codes — that's Platform Admin only.
# ---------------------------------------------------------------------------
@cashier_bp.route('/coupons')
@login_required
@cashier_required
def coupon_list():
    sid          = _school_id()
    active_term  = _active_term()

    # Allow browsing past terms too (not just active)
    term_id = request.args.get('term_id', type=int)
    status  = request.args.get('status', 'all')
    search  = request.args.get('search', '').strip()

    # Build terms dropdown — all terms for this school
    all_terms = (
        Term.query
        .join(AcademicSession)
        .filter(AcademicSession.school_id == sid)
        .order_by(AcademicSession.id.desc(), Term.id.asc())
        .all()
    )

    # Default to active term if none selected
    if not term_id and active_term:
        term_id = active_term.id

    coupons = Coupon.register_query(
        school_id=sid,
        term_id=term_id,
        status=status,
        search=search,
    ).limit(500).all()

    total_count  = Coupon.register_query(school_id=sid, term_id=term_id).count()
    used_count   = Coupon.register_query(school_id=sid, term_id=term_id, status='used').count()
    unused_count = total_count - used_count

    return render_template(
        'cashier/coupon_list.html',
        coupons=coupons,
        all_terms=all_terms,
        active_term=active_term,
        total_count=total_count,
        used_count=used_count,
        unused_count=unused_count,
        filters=dict(term_id=term_id, status=status, search=search),
    )


@cashier_bp.route('/coupons/print')
@login_required
@cashier_required
def coupon_print():
    """Print-optimised page of UNUSED codes — for physical distribution."""
    sid         = _school_id()
    active_term = _active_term()
    term_id     = request.args.get('term_id', type=int)

    if not term_id and active_term:
        term_id = active_term.id

    term = Term.query.get(term_id) if term_id else None
    if not term:
        flash('No term selected.', 'warning')
        return redirect(url_for('cashier.coupon_list'))

    # Security: confirm term belongs to this school
    if term.session.school_id != sid:
        flash('Access denied.', 'danger')
        return redirect(url_for('cashier.coupon_list'))

    coupons = Coupon.register_query(
        school_id=sid, term_id=term.id, status='unused'
    ).all()

    school = current_user.school
    return render_template(
        'cashier/coupon_print.html',
        school=school,
        term=term,
        coupons=coupons,
    )


# ---------------------------------------------------------------------------
# 7.3  RESULT RELEASE CONTROL
# Cashier can hold or publish results per class or per individual student.
# The same is_released flag gates the student portal view.
# ---------------------------------------------------------------------------
@cashier_bp.route('/results', methods=['GET', 'POST'])
@login_required
@cashier_required
def result_release():
    sid            = _school_id()
    active_session = _active_session()
    active_term    = _active_term()
    classes        = Class.query.filter_by(school_id=sid).all()

    # Allow selecting a specific session/term for historical release management
    sessions = AcademicSession.query.filter_by(school_id=sid).order_by(
        AcademicSession.id.desc()
    ).all()

    sel_session_id = request.args.get('session_id', type=int)
    sel_term_id    = request.args.get('term_id',    type=int)
    sel_class_id   = request.args.get('class_id',   type=int)

    # Default to active session/term
    if not sel_session_id and active_session:
        sel_session_id = active_session.id
    if not sel_term_id and active_term:
        sel_term_id = active_term.id

    # Terms for the selected session
    terms_for_session = []
    if sel_session_id:
        sess = AcademicSession.query.filter_by(
            id=sel_session_id, school_id=sid
        ).first()
        if sess:
            terms_for_session = sess.terms  # lazy=True list, safe to iterate

    students_data = []
    if sel_session_id and sel_term_id and sel_class_id:
        students = Student.query.filter_by(
            current_class_id=sel_class_id, is_active=True
        ).order_by(Student.last_name, Student.first_name).all()

        for student in students:
            # Use first score as proxy for release status
            score = Score.query.filter_by(
                student_id=student.id,
                session_id=sel_session_id,
                term_id=sel_term_id,
            ).first()
            students_data.append({
                'student':    student,
                'has_scores': bool(score),
                'is_released': score.is_released if score else False,
            })

    return render_template(
        'cashier/result_release.html',
        sessions=sessions,
        classes=classes,
        terms_for_session=terms_for_session,
        students_data=students_data,
        sel_session_id=sel_session_id,
        sel_term_id=sel_term_id,
        sel_class_id=sel_class_id,
        active_session=active_session,
        active_term=active_term,
    )


@cashier_bp.route('/results/toggle', methods=['POST'])
@login_required
@cashier_required
def toggle_release():
    sid        = _school_id()
    action     = request.form.get('action')
    session_id = request.form.get('session_id', type=int)
    term_id    = request.form.get('term_id',    type=int)
    class_id   = request.form.get('class_id',   type=int)

    # Verify session belongs to this school before touching any scores
    sess = AcademicSession.query.filter_by(id=session_id, school_id=sid).first()
    if not sess:
        flash('Invalid session.', 'danger')
        return redirect(url_for('cashier.result_release'))

    if action in ('release_all', 'hold_all'):
        new_status = action == 'release_all'

        # Fetch student IDs in this class to scope the score update
        student_ids = [
            s.id for s in Student.query.filter_by(
                current_class_id=class_id, is_active=True
            ).all()
        ]

        if student_ids:
            Score.query.filter(
                Score.session_id == session_id,
                Score.term_id    == term_id,
                Score.student_id.in_(student_ids),
            ).update({'is_released': new_status}, synchronize_session=False)
            db.session.commit()

        label = 'published' if new_status else 'withheld'
        flash(f'Results {label} for the entire class.', 'success')

    elif action == 'toggle_single':
        student_id     = request.form.get('student_id', type=int)
        current_status = request.form.get('current_status') == 'True'

        # Verify student belongs to this school
        student = Student.query.filter_by(
            id=student_id, school_id=sid
        ).first_or_404()

        Score.query.filter_by(
            student_id=student.id,
            session_id=session_id,
            term_id=term_id,
        ).update({'is_released': not current_status}, synchronize_session=False)
        db.session.commit()

        label = 'published' if not current_status else 'withheld'
        flash(
            f'Results {label} for '
            f'{student.first_name} {student.last_name}.',
            'success'
        )

    return redirect(url_for(
        'cashier.result_release',
        session_id=session_id,
        term_id=term_id,
        class_id=class_id,
    ))


# ---------------------------------------------------------------------------
# 7.4  COUPON USAGE STATUS TRACKER
# Detailed per-student view showing who has and hasn't activated a coupon
# for the active term — useful for chasing fee defaulters.
# ---------------------------------------------------------------------------
@cashier_bp.route('/coupon-tracker')
@login_required
@cashier_required
def coupon_tracker():
    sid        = _school_id()
    active_term = _active_term()
    active_session = _active_session()

    sel_class_id = request.args.get('class_id', type=int)
    classes      = Class.query.filter_by(school_id=sid).all()

    tracker_data = []
    if sel_class_id and active_term:
        students = Student.query.filter_by(
            current_class_id=sel_class_id,
            school_id=sid,
            is_active=True,
        ).order_by(Student.last_name, Student.first_name).all()

        for student in students:
            activation = CouponActivation.query.filter_by(
                student_id=student.id,
                term_id=active_term.id,
            ).first()

            coupon = activation.coupon if activation else None
            tracker_data.append({
                'student':      student,
                'has_activated': bool(activation),
                'activated_at': activation.activated_at if activation else None,
                'coupon_code':  coupon.code if coupon else None,
            })

    return render_template(
        'cashier/coupon_tracker.html',
        classes=classes,
        sel_class_id=sel_class_id,
        tracker_data=tracker_data,
        active_term=active_term,
        active_session=active_session,
    )


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------
@cashier_bp.route('/notifications')
@login_required
@cashier_required
def notifications():
    sid = _school_id()
    messages = Notification.query.filter(
        db.or_(
            Notification.recipient_id == current_user.id,
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'role',
                Notification.recipient_role == 'Cashier',
            ),
            db.and_(
                Notification.school_id == sid,
                Notification.recipient_type == 'broadcast',
            ),
        )
    ).order_by(Notification.created_at.desc()).limit(100).all()

    return render_template('cashier/notifications.html', messages=messages)


@cashier_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@cashier_required
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
            return redirect(url_for('cashier.notifications'))
    n.is_read = True
    db.session.commit()
    return redirect(url_for('cashier.notifications'))


@cashier_bp.route('/notifications/compose', methods=['GET', 'POST'])
@login_required
@cashier_required
def compose_notification():
    sid = _school_id()

    if request.method == 'POST':
        recipient_type = request.form.get('recipient_type', '')
        subject        = request.form.get('subject', '').strip()
        body           = request.form.get('body', '').strip()

        if not subject or not body:
            flash('Subject and message are required.', 'warning')
            return redirect(url_for('cashier.compose_notification'))

        if recipient_type == 'superadmin':
            super_admin = User.query.filter_by(
                school_id=sid, role='SuperAdmin'
            ).first()
            if not super_admin:
                flash('No SuperAdmin found for this school.', 'danger')
                return redirect(url_for('cashier.compose_notification'))
            n = Notification(
                sender_id=current_user.id, school_id=sid,
                recipient_type='user', recipient_id=super_admin.id,
                subject=subject, body=body,
            )
        else:
            flash('Select a valid recipient.', 'warning')
            return redirect(url_for('cashier.compose_notification'))

        db.session.add(n)
        db.session.commit()
        flash('Message sent to SuperAdmin.', 'success')
        return redirect(url_for('cashier.notifications'))

    return render_template('cashier/compose_notification.html')
