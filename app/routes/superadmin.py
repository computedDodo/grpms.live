import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    School, User, Teacher, AcademicSession, Term,
    Coupon, Notification
)
from app.utils.decorators import super_admin_required, verify_school_ownership

superadmin_bp = Blueprint('superadmin', __name__)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _allowed_image(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower()
        in current_app.config['ALLOWED_IMAGE_EXTENSIONS']
    )


def _save_upload(file, prefix):
    """Save an uploaded image to the uploads folder, return the relative path."""
    filename  = secure_filename(file.filename)
    save_name = f"{prefix}_{filename}"
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], save_name)
    file.save(full_path)
    return f"uploads/{save_name}"


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@superadmin_bp.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    print("DEBUG:", current_user.username, current_user.role, current_user.school_id, current_user.school)
    school = current_user.school
    ...
    school = current_user.school
    verify_school_ownership(school, 'id')

    total_staff = User.query.filter(
        User.school_id == school.id,
        User.role.in_(['Admin', 'Cashier', 'FormMaster', 'Teacher']),
        User.is_active.is_(True),
    ).count()
    total_students = User.query.filter_by(
        school_id=school.id, role='Student', is_active=True
    ).count()

    active_session = school.active_session
    active_term    = school.active_term

    unread_count = Notification.query.filter(
        (Notification.recipient_id == current_user.id) |
        (
            (Notification.school_id == school.id) &
            (Notification.recipient_type == 'role') &
            (Notification.recipient_role == 'SuperAdmin')
        ),
        Notification.is_read.is_(False),
    ).count()

    return render_template(
        'superadmin/dashboard.html',
        school=school,
        total_staff=total_staff,
        total_students=total_students,
        active_session=active_session,
        active_term=active_term,
        unread_count=unread_count,
    )


# ---------------------------------------------------------------------------
# SCHOOL SETTINGS  (branding, logo, signature, stamp)
# ---------------------------------------------------------------------------
@superadmin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@super_admin_required
def school_settings():
    school = current_user.school
    verify_school_ownership(school, 'id')

    if request.method == 'POST':
        school.name           = request.form.get('name', '').strip() or school.name
        school.motto          = request.form.get('motto', '').strip()
        school.principal_name = request.form.get('principal_name', '').strip() or school.principal_name
        # School code for admission number prefix
        raw_code = request.form.get('code', '').strip().upper()
        if raw_code:
            import re
            clean_code = re.sub(r'[^A-Z]', '', raw_code)[:6]
            if clean_code:
                school.code = clean_code

        for field in ['logo', 'signature', 'stamp']:
            f = request.files.get(field)
            if f and f.filename and _allowed_image(f.filename):
                path = _save_upload(f, f"{field}_{school.id}")
                setattr(school, f'{field}_path', path)

        db.session.commit()
        flash('School settings updated successfully.', 'success')
        return redirect(url_for('superadmin.school_settings'))

    return render_template('superadmin/settings.html', school=school)


# ---------------------------------------------------------------------------
# STAFF MANAGEMENT
# ---------------------------------------------------------------------------
@superadmin_bp.route('/staff', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_staff():
    school = current_user.school

    if request.method == 'POST':
        username  = request.form.get('username', '').strip()
        password  = request.form.get('password', '')
        role      = request.form.get('role', '')
        title     = request.form.get('title', '').strip()
        full_name = request.form.get('full_name', '').strip()

        valid_roles = ['Admin', 'Cashier', 'FormMaster', 'Teacher']
        if role not in valid_roles:
            flash('Please select a valid staff role.', 'warning')
            return redirect(url_for('superadmin.manage_staff'))

        if not username:
            flash('Username is required.', 'warning')
            return redirect(url_for('superadmin.manage_staff'))

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'warning')
            return redirect(url_for('superadmin.manage_staff'))

        if User.query.filter_by(username=username).first():
            flash(f'Username "{username}" is already taken.', 'warning')
            return redirect(url_for('superadmin.manage_staff'))

        new_user = User(username=username, role=role, school_id=school.id)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()  # get new_user.id before commit

        # Teacher and FormMaster get a Teacher profile row
        if role in ['Teacher', 'FormMaster']:
            if not full_name:
                flash('Full name is required for teaching staff.', 'warning')
                db.session.rollback()
                return redirect(url_for('superadmin.manage_staff'))
            teacher = Teacher(
                user_id=new_user.id,
                school_id=school.id,
                title=title,
                full_name=full_name,
            )
            db.session.add(teacher)

        db.session.commit()
        flash(f'{role} account "{username}" created successfully.', 'success')
        return redirect(url_for('superadmin.manage_staff'))

    # GET — filter/search
    search      = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')

    query = User.query.filter(
        User.school_id == school.id,
        User.role.in_(['Admin', 'Cashier', 'FormMaster', 'Teacher']),
        User.is_active.is_(True),
    )
    if search:
        query = query.filter(User.username.ilike(f'%{search}%'))
    if role_filter:
        query = query.filter_by(role=role_filter)

    staff = query.order_by(User.role, User.username).all()
    return render_template('superadmin/staff.html', school=school, staff=staff)


@superadmin_bp.route('/staff/<int:user_id>/reset-password', methods=['POST'])
@login_required
@super_admin_required
def reset_staff_password(user_id):
    user = User.query.get_or_404(user_id)
    verify_school_ownership(user)

    new_password = request.form.get('new_password', '12345678')
    if len(new_password) < 6:
        new_password = '12345678'

    user.set_password(new_password)
    db.session.commit()
    flash(
        f"Password for @{user.username} reset to "
        f"{'the provided password' if new_password != '12345678' else '\"12345678\"'}. "
        f"Ask them to change it on next login.",
        'info'
    )
    return redirect(url_for('superadmin.manage_staff'))


@superadmin_bp.route('/staff/<int:user_id>/archive', methods=['POST'])
@login_required
@super_admin_required
def archive_staff(user_id):
    user = User.query.get_or_404(user_id)
    verify_school_ownership(user)

    if user.role == 'SuperAdmin':
        flash('You cannot archive another SuperAdmin.', 'danger')
        return redirect(url_for('superadmin.manage_staff'))

    user.is_active = False
    if user.teacher_profile:
        user.teacher_profile.is_active = False

    db.session.commit()
    flash(f'Staff account "@{user.username}" archived. They can no longer log in.', 'info')
    return redirect(url_for('superadmin.manage_staff'))


@superadmin_bp.route('/staff/<int:user_id>/restore', methods=['POST'])
@login_required
@super_admin_required
def restore_staff(user_id):
    # Search archived staff (is_active=False) within this school
    user = User.query.filter_by(id=user_id, school_id=current_user.school_id).first_or_404()

    user.is_active = True
    if user.teacher_profile:
        user.teacher_profile.is_active = True

    db.session.commit()
    flash(f'Staff account "@{user.username}" restored. They can now log in again.', 'success')
    return redirect(url_for('superadmin.staff_archive'))


@superadmin_bp.route('/staff/archive')
@login_required
@super_admin_required
def staff_archive():
    school = current_user.school
    archived = User.query.filter(
        User.school_id == school.id,
        User.role.in_(['Admin', 'Cashier', 'FormMaster', 'Teacher']),
        User.is_active.is_(False),
    ).order_by(User.username).all()

    return render_template('superadmin/staff_archive.html', school=school, archived=archived)


# ---------------------------------------------------------------------------
# ACADEMIC SETUP  (sessions + terms)
# ---------------------------------------------------------------------------
@superadmin_bp.route('/academic-setup', methods=['GET', 'POST'])
@login_required
@super_admin_required
def academic_setup():
    school = current_user.school

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_session':
            session_name = request.form.get('session_name', '').strip()
            if not session_name:
                flash('Session name is required.', 'warning')
            elif AcademicSession.query.filter_by(
                session_name=session_name, school_id=school.id
            ).first():
                flash(f'Session "{session_name}" already exists.', 'warning')
            else:
                db.session.add(AcademicSession(
                    session_name=session_name, school_id=school.id
                ))
                db.session.commit()
                flash(f'Session "{session_name}" created.', 'success')

        elif action == 'add_term':
            term_name  = request.form.get('term_name', '')
            session_id = request.form.get('session_id', type=int)
            session    = AcademicSession.query.filter_by(
                id=session_id, school_id=school.id
            ).first_or_404()
            # prevent duplicate terms within same session
            if Term.query.filter_by(
                term_name=term_name, session_id=session.id
            ).first():
                flash(f'"{term_name}" already exists for that session.', 'warning')
            else:
                db.session.add(Term(term_name=term_name, session_id=session.id))
                db.session.commit()
                flash(f'{term_name} added to {session.session_name}.', 'success')

        elif action == 'set_active_session':
            session_id = request.form.get('active_session', type=int)
            if session_id:
                # deactivate all sessions for this school only
                AcademicSession.query.filter_by(school_id=school.id).update(
                    {AcademicSession.is_active: False}
                )
                selected = AcademicSession.query.filter_by(
                    id=session_id, school_id=school.id
                ).first_or_404()
                selected.is_active = True
                db.session.commit()
                flash(f'"{selected.session_name}" is now the active session.', 'success')

        elif action == 'set_active_term':
            term_id = request.form.get('active_term', type=int)
            if term_id:
                # Deactivate all terms belonging to this school's sessions
                school_session_ids = [
                    s.id for s in
                    AcademicSession.query.filter_by(school_id=school.id).all()
                ]
                Term.query.filter(
                    Term.session_id.in_(school_session_ids)
                ).update({Term.is_active: False}, synchronize_session=False)

                selected_term = Term.query.get_or_404(term_id)
                # Verify term belongs to this school
                if selected_term.session.school_id != school.id:
                    flash('Access denied.', 'danger')
                    return redirect(url_for('superadmin.academic_setup'))

                selected_term.is_active = True
                db.session.commit()
                flash(f'"{selected_term.term_name}" is now the active term.', 'success')

        return redirect(url_for('superadmin.academic_setup'))

    sessions = (
        AcademicSession.query
        .filter_by(school_id=school.id)
        .order_by(AcademicSession.id.desc())
        .all()
    )
    return render_template(
        'superadmin/academic_setup.html',
        school=school,
        sessions=sessions,
    )


# ---------------------------------------------------------------------------
# COUPON REGISTER  (read-only mirror for SuperAdmin)
# ---------------------------------------------------------------------------
@superadmin_bp.route('/coupons')
@login_required
@super_admin_required
def coupon_register():
    school = current_user.school

    term_id = request.args.get('term_id', type=int)
    status  = request.args.get('status', 'all')
    search  = request.args.get('search', '').strip()

    school_session_ids = [
        s.id for s in AcademicSession.query.filter_by(school_id=school.id).all()
    ]
    terms = Term.query.filter(
        Term.session_id.in_(school_session_ids)
    ).order_by(Term.id.desc()).all()

    coupons = (
        Coupon.register_query(
            school_id=school.id,
            term_id=term_id,
            status=status,
            search=search,
        )
        .limit(500)
        .all()
    )

    total_count  = Coupon.register_query(school_id=school.id, term_id=term_id).count()
    used_count   = Coupon.register_query(school_id=school.id, term_id=term_id, status='used').count()
    unused_count = total_count - used_count

    return render_template(
        'superadmin/coupon_register.html',
        school=school,
        terms=terms,
        coupons=coupons,
        total_count=total_count,
        used_count=used_count,
        unused_count=unused_count,
        filters=dict(term_id=term_id, status=status, search=search),
    )


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------
@superadmin_bp.route('/notifications')
@login_required
@super_admin_required
def notifications():
    school = current_user.school

    # Messages addressed directly to this user OR broadcast to all SuperAdmins
    messages = Notification.query.filter(
        db.or_(
            Notification.recipient_id == current_user.id,
            db.and_(
                Notification.school_id.is_(None),   # platform-wide broadcast
                Notification.recipient_type == 'role',
                Notification.recipient_role == 'SuperAdmin',
            ),
            db.and_(
                Notification.school_id == school.id, # school-wide broadcast
                Notification.recipient_type == 'broadcast',
            ),
        )
    ).order_by(Notification.created_at.desc()).limit(100).all()

    return render_template(
        'superadmin/notifications.html',
        school=school,
        messages=messages,
    )


@superadmin_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@super_admin_required
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
            return redirect(url_for('superadmin.notifications'))
    n.is_read = True
    db.session.commit()
    return redirect(url_for('superadmin.notifications'))


@superadmin_bp.route('/notifications/compose', methods=['GET', 'POST'])
@login_required
@super_admin_required
def compose_notification():
    school = current_user.school

    if request.method == 'POST':
        recipient_type = request.form.get('recipient_type', '')  # 'platform', 'broadcast', 'role', 'user'
        subject        = request.form.get('subject', '').strip()
        body           = request.form.get('body', '').strip()

        if not subject or not body:
            flash('Subject and message are required.', 'warning')
            return redirect(url_for('superadmin.compose_notification'))

        if recipient_type == 'platform':
            # Message to Platform Admin
            platform_admin = User.query.filter_by(role='PlatformAdmin').first()
            if not platform_admin:
                flash('No Platform Admin found in the system.', 'danger')
                return redirect(url_for('superadmin.compose_notification'))
            n = Notification(
                sender_id=current_user.id,
                school_id=school.id,
                recipient_type='user',
                recipient_id=platform_admin.id,
                subject=subject,
                body=body,
            )

        elif recipient_type == 'broadcast':
            # Broadcast to everyone in this school
            n = Notification(
                sender_id=current_user.id,
                school_id=school.id,
                recipient_type='broadcast',
                recipient_role=None,
                recipient_id=None,
                subject=subject,
                body=body,
            )

        elif recipient_type in ['Admin', 'Cashier', 'FormMaster', 'Teacher', 'Student']:
            # Send to all users of a given role within this school
            n = Notification(
                sender_id=current_user.id,
                school_id=school.id,
                recipient_type='role',
                recipient_role=recipient_type,
                recipient_id=None,
                subject=subject,
                body=body,
            )

        else:
            flash('Please select a valid recipient.', 'warning')
            return redirect(url_for('superadmin.compose_notification'))

        db.session.add(n)
        db.session.commit()
        flash('Message sent successfully.', 'success')
        return redirect(url_for('superadmin.notifications'))

    # Pre-load staff for "specific person" option (added in Phase 8/9 UX)
    return render_template('superadmin/compose_notification.html', school=school)


@superadmin_bp.route('/export')
@login_required
@super_admin_required
def export_school_data():
    from app.utils.export import generate_school_export
    from flask import Response
    from datetime import datetime
    buf, school_name = generate_school_export(current_user.school_id)
    filename = f"GRPMS_Export_{school_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'})
