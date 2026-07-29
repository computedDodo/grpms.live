from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify)
from flask_login import login_required, current_user
from app.models import Notification, User, Teacher, Student
from app import db

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')


def _get_inbox(user):
    """All notifications visible to this user."""
    return (Notification.query
            .filter(
                db.or_(
                    Notification.recipient_id == user.id,
                    db.and_(
                        Notification.recipient_type == 'role',
                        Notification.role_target == user.role,
                        Notification.school_id == user.school_id
                    ),
                    db.and_(
                        Notification.recipient_type == 'broadcast',
                        Notification.school_id == user.school_id
                    ),
                )
            )
            .order_by(Notification.created_at.desc())
            .all())


@notifications_bp.route('/')
@login_required
def inbox():
    messages = _get_inbox(current_user)
    return render_template('notifications/inbox.html', messages=messages)


@notifications_bp.route('/<int:notif_id>')
@login_required
def view(notif_id):
    n = Notification.query.get_or_404(notif_id)
    if not n.is_read and (
        n.recipient_id == current_user.id or
        n.recipient_type in ('broadcast', 'role')
    ):
        n.is_read = True
        db.session.commit()
    return render_template('notifications/view.html', notification=n)


@notifications_bp.route('/send', methods=['GET', 'POST'])
@login_required
def send():
    if request.method == 'POST':
        recipient_type = request.form.get('recipient_type', 'user')
        role_target    = request.form.get('role_target') or None
        recipient_id   = request.form.get('recipient_id', type=int) or None
        subject        = request.form.get('subject', '').strip()
        body           = request.form.get('body', '').strip()
        tag            = request.form.get('tag', 'notification')

        if not subject or not body:
            flash('Subject and message are required.', 'warning')
            return redirect(url_for('notifications.send'))

        # Determine school_id for scoping
        school_id = current_user.school_id  # None for PlatformAdmin = platform-wide

        n = Notification(
            sender_id=current_user.id,
            school_id=school_id,
            recipient_type=recipient_type,
            role_target=role_target,
            recipient_id=recipient_id,
            subject=subject,
            body=body,
            tag=tag,
        )
        db.session.add(n)
        db.session.commit()
        flash('Message sent.', 'success')
        return redirect(url_for('notifications.inbox'))

    # Build recipient options based on sender's role
    recipient_options = _get_recipient_options(current_user)
    return render_template('notifications/send.html',
                           recipient_options=recipient_options)


def _get_recipient_options(user):
    """
    Returns dict of available recipient types for this user's role.
    Used to build the compose form.
    """
    opts = {}
    role = user.role
    sid  = user.school_id

    if role == 'PlatformAdmin':
        # Can broadcast to all schools or target a specific SuperAdmin
        super_admins = User.query.filter_by(role='SuperAdmin', is_active=True).all()
        opts['specific_users'] = super_admins
        opts['can_broadcast']  = True
        opts['can_role_target'] = False

    elif role in ('SuperAdmin', 'Admin'):
        # Broadcast to whole school, target by role, or specific person
        all_school_users = User.query.filter(
            User.school_id == sid, User.is_active == True,
            User.id != user.id
        ).all()
        opts['specific_users']  = all_school_users
        opts['can_broadcast']   = True
        opts['can_role_target'] = True
        opts['roles'] = ['Admin', 'Cashier', 'FormMaster', 'Teacher', 'Student']

    elif role in ('Teacher', 'FormMaster', 'Cashier'):
        # Can message school admin or assigned students
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        admins  = User.query.filter(
            User.school_id == sid,
            User.role.in_(['SuperAdmin', 'Admin']),
            User.is_active == True
        ).all()
        students = []
        if teacher and role in ('Teacher', 'FormMaster'):
            from app.models import SubjectAllocation
            alloc_class_ids = list({a.class_id for a in teacher.allocations})
            students = Student.query.filter(
                Student.current_class_id.in_(alloc_class_ids),
                Student.is_active == True
            ).all() if alloc_class_ids else []

        opts['specific_users']  = admins + [s.user for s in students if s.user]
        opts['can_broadcast']   = False
        opts['can_role_target'] = False

    elif role == 'Student':
        student = Student.query.filter_by(user_id=user.id).first()
        targets = []
        if student and student.current_class_id:
            cls = student.student_class
            if cls and cls.form_master:
                targets.append(cls.form_master.user)
        admins = User.query.filter(
            User.school_id == sid,
            User.role.in_(['SuperAdmin', 'Admin']),
            User.is_active == True
        ).all()
        opts['specific_users']  = list({u.id: u for u in (targets + admins)}.values())
        opts['can_broadcast']   = False
        opts['can_role_target'] = False

    return opts


@notifications_bp.route('/mark-read/<int:notif_id>', methods=['POST'])
@login_required
def mark_read(notif_id):
    n = Notification.query.get_or_404(notif_id)
    n.is_read = True
    db.session.commit()
    return redirect(url_for('notifications.inbox'))


@notifications_bp.route('/unread-count')
@login_required
def unread_count():
    messages = _get_inbox(current_user)
    count    = sum(1 for m in messages if not m.is_read)
    return jsonify({'count': count})
