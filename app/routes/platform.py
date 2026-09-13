import random

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.models import School, User, AcademicSession, Term, Coupon, Notification
from app.utils.decorators import platform_admin_required, active_account_required

platform_bp = Blueprint('platform', __name__)


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@platform_bp.route('/dashboard')
@login_required
@platform_admin_required
def dashboard():
    total_schools   = School.query.filter_by(is_active=True).count()
    total_students  = User.query.filter_by(role='Student', is_active=True).count()
    total_staff     = User.query.filter(
        User.role.in_(['SuperAdmin', 'Admin', 'Cashier', 'FormMaster', 'Teacher']),
        User.is_active.is_(True)
    ).count()
    schools = School.query.order_by(School.created_at.desc()).all()

    # Pre-load SuperAdmin for each school in one query to avoid N+1
    # and because school.users is a dynamic relationship (query object),
    # not directly iterable in Jinja templates.
    super_admins = {
        u.school_id: u
        for u in User.query.filter_by(role='SuperAdmin', is_active=True).all()
    }

    return render_template(
        'platform/dashboard.html',
        total_schools=total_schools,
        total_students=total_students,
        total_staff=total_staff,
        schools=schools,
        super_admins=super_admins,
    )


# ---------------------------------------------------------------------------
# SCHOOL MANAGEMENT
# ---------------------------------------------------------------------------
@platform_bp.route('/schools/add', methods=['GET', 'POST'])
@login_required
@platform_admin_required
def add_school():
    if request.method == 'POST':
        name           = request.form.get('name', '').strip()
        motto          = request.form.get('motto', '').strip()
        principal_name = request.form.get('principal_name', '').strip()

        if not name:
            flash('School name is required.', 'warning')
            return redirect(url_for('platform.add_school'))

        if School.query.filter_by(name=name).first():
            flash(f'A school named "{name}" already exists.', 'warning')
            return redirect(url_for('platform.add_school'))

        school = School(
            name=name,
            motto=motto,
            principal_name=principal_name or 'Principal',
        )
        db.session.add(school)
        db.session.commit()

        flash(f'School "{name}" created. Now create its SuperAdmin account.', 'success')
        return redirect(url_for('platform.create_superadmin', school_id=school.id))

    return render_template('platform/add_school.html')


@platform_bp.route('/schools/<int:school_id>/edit', methods=['GET', 'POST'])
@login_required
@platform_admin_required
def edit_school(school_id):
    school = School.query.get_or_404(school_id)

    if request.method == 'POST':
        name           = request.form.get('name', '').strip()
        motto          = request.form.get('motto', '').strip()
        principal_name = request.form.get('principal_name', '').strip()

        if not name:
            flash('School name is required.', 'warning')
            return redirect(url_for('platform.edit_school', school_id=school.id))

        # Duplicate name check — exclude the current school from the search
        conflict = School.query.filter(School.name == name, School.id != school.id).first()
        if conflict:
            flash(f'Another school named "{name}" already exists.', 'warning')
            return redirect(url_for('platform.edit_school', school_id=school.id))

        school.name           = name
        school.motto          = motto
        school.principal_name = principal_name or school.principal_name
        db.session.commit()

        flash(f'"{school.name}" updated successfully.', 'success')
        return redirect(url_for('platform.dashboard'))

    return render_template('platform/edit_school.html', school=school)


@platform_bp.route('/schools/<int:school_id>/toggle-active', methods=['POST'])
@login_required
@platform_admin_required
def toggle_school_active(school_id):
    school = School.query.get_or_404(school_id)
    school.is_active = not school.is_active
    db.session.commit()
    state = 'reactivated' if school.is_active else 'deactivated'
    flash(f'"{school.name}" has been {state}.', 'info')
    return redirect(url_for('platform.dashboard'))


# ---------------------------------------------------------------------------
# SUPERADMIN ACCOUNT CREATION
# ---------------------------------------------------------------------------
@platform_bp.route('/schools/<int:school_id>/create-superadmin', methods=['GET', 'POST'])
@login_required
@platform_admin_required
def create_superadmin(school_id):
    school   = School.query.get_or_404(school_id)
    existing = User.query.filter_by(school_id=school.id, role='SuperAdmin').first()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are both required.', 'warning')
            return redirect(url_for('platform.create_superadmin', school_id=school.id))

        if User.query.filter_by(username=username).first():
            flash(f'Username "{username}" is already taken.', 'warning')
            return redirect(url_for('platform.create_superadmin', school_id=school.id))

        if len(password) < 8:
            flash('Password should be at least 8 characters.', 'warning')
            return redirect(url_for('platform.create_superadmin', school_id=school.id))

        new_super = User(username=username, role='SuperAdmin', school_id=school.id)
        new_super.set_password(password)
        db.session.add(new_super)
        db.session.commit()

        flash(f'SuperAdmin "{username}" created for {school.name}.', 'success')
        return redirect(url_for('platform.dashboard'))

    return render_template(
        'platform/create_superadmin.html',
        school=school,
        existing=existing,
    )


# ---------------------------------------------------------------------------
# COUPON GENERATION
# ---------------------------------------------------------------------------
def _generate_unique_code(length, charset):
    """
    Generate a random code not already in the coupons table.
    50-attempt guard prevents an infinite loop if the code space is exhausted
    (e.g. numeric + length=4 → only 10,000 possible codes).
    """
    for _ in range(50):
        code = ''.join(random.choices(charset, k=length))
        if not Coupon.query.filter_by(code=code).first():
            return code
    raise RuntimeError(
        'Could not generate a unique coupon code after 50 attempts. '
        'Try a longer length or a different character set.'
    )


CHARSET_MAP = {
    'alphanumeric': 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789',  # no 0/O/1/I ambiguity
    'numeric':      '23456789',                           # digits only, still no 0/1
    'letters':      'ABCDEFGHJKLMNPQRSTUVWXYZ',           # letters only
}


@platform_bp.route('/coupons/generate', methods=['GET', 'POST'])
@login_required
@platform_admin_required
def generate_coupons():
    schools = School.query.filter_by(is_active=True).order_by(School.name).all()

    # Pre-select a school if coming from add_school → create_superadmin → here
    selected_school_id = request.values.get('school_id', type=int)
    selected_school    = School.query.get(selected_school_id) if selected_school_id else None
    active_term        = selected_school.active_term if selected_school else None

    if request.method == 'POST':
        school_id      = request.form.get('school_id', type=int)
        quantity       = request.form.get('quantity', type=int)
        length         = request.form.get('length', 8, type=int)
        charset_choice = request.form.get('charset', 'alphanumeric')

        school = School.query.get(school_id) if school_id else None
        if not school:
            flash('Please select a valid school.', 'warning')
            return redirect(url_for('platform.generate_coupons'))

        term = school.active_term
        if not term:
            flash(
                f'"{school.name}" has no active session/term configured yet. '
                'Ask their SuperAdmin to set that up first.',
                'warning'
            )
            return redirect(url_for('platform.generate_coupons', school_id=school.id))

        if not quantity or quantity < 1:
            flash('Please enter a quantity of 1 or more.', 'warning')
            return redirect(url_for('platform.generate_coupons', school_id=school.id))

        if quantity > 5000:
            flash('Maximum 5,000 coupons per batch. Run it again to generate more.', 'warning')
            return redirect(url_for('platform.generate_coupons', school_id=school.id))

        if not (6 <= length <= 16):
            flash('Code length must be between 6 and 16 characters.', 'warning')
            return redirect(url_for('platform.generate_coupons', school_id=school.id))

        charset = CHARSET_MAP.get(charset_choice, CHARSET_MAP['alphanumeric'])

        try:
            created = 0
            for _ in range(quantity):
                code = _generate_unique_code(length, charset)
                db.session.add(Coupon(code=code, school_id=school.id, term_id=term.id))
                created += 1
            db.session.commit()
        except RuntimeError as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return redirect(url_for('platform.generate_coupons', school_id=school.id))

        flash(
            f'{created:,} coupon(s) generated for {school.name} — '
            f'{term.term_name}, {term.session.session_name}.',
            'success'
        )
        return redirect(url_for('platform.coupon_register', school_id=school.id))

    return render_template(
        'platform/generate_coupons.html',
        schools=schools,
        selected_school=selected_school,
        active_term=active_term,
        charset_options=list(CHARSET_MAP.keys()),
    )


# ---------------------------------------------------------------------------
# COUPON REGISTER  (audit trail: filter by school, term, status, code search)
# ---------------------------------------------------------------------------
@platform_bp.route('/coupons/register')
@login_required
@platform_admin_required
def coupon_register():
    schools = School.query.order_by(School.name).all()

    school_id       = request.args.get('school_id', type=int)
    term_id         = request.args.get('term_id', type=int)
    status          = request.args.get('status', 'all')
    search          = request.args.get('search', '').strip()

    selected_school   = School.query.get(school_id) if school_id else None
    terms_for_school  = []
    if selected_school:
        terms_for_school = (
            Term.query
            .join(AcademicSession)
            .filter(AcademicSession.school_id == selected_school.id)
            .order_by(AcademicSession.id.desc(), Term.id.asc())
            .all()
        )

    # Use the shared query builder from models.py
    coupons = (
        Coupon.register_query(
            school_id=school_id,
            term_id=term_id,
            status=status,
            search=search,
        )
        .limit(500)   # hard cap — prevents freezing on large registers
        .all()
    )

    # Summary bar counts (always unfiltered by status/search for accuracy)
    total_count  = Coupon.register_query(school_id=school_id, term_id=term_id).count()
    used_count   = Coupon.register_query(school_id=school_id, term_id=term_id, status='used').count()
    unused_count = total_count - used_count

    return render_template(
        'platform/coupon_register.html',
        schools=schools,
        selected_school=selected_school,
        terms_for_school=terms_for_school,
        coupons=coupons,
        total_count=total_count,
        used_count=used_count,
        unused_count=unused_count,
        filters=dict(
            school_id=school_id,
            term_id=term_id,
            status=status,
            search=search,
        ),
    )


@platform_bp.route('/coupons/register/print')
@login_required
@platform_admin_required
def coupon_register_print():
    """
    Print-optimised view of UNUSED codes only — this is what gets
    physically printed and handed to the school for distribution.
    """
    school_id = request.args.get('school_id', type=int)
    term_id   = request.args.get('term_id', type=int)

    school = School.query.get_or_404(school_id)
    term   = Term.query.get(term_id) if term_id else school.active_term

    if not term:
        flash('No term selected and this school has no active term.', 'warning')
        return redirect(url_for('platform.coupon_register', school_id=school.id))

    coupons = (
        Coupon.register_query(
            school_id=school.id,
            term_id=term.id,
            status='unused',
        )
        .all()
    )

    return render_template(
        'platform/coupon_print.html',
        school=school,
        term=term,
        coupons=coupons,
    )


# ---------------------------------------------------------------------------
# PLATFORM-WIDE BROADCAST
# Platform Admin → all SuperAdmins across all schools at once.
# Individual + role-targeted notifications for school staff in Phase 5.
# ---------------------------------------------------------------------------
@platform_bp.route('/broadcast', methods=['GET', 'POST'])
@login_required
@platform_admin_required
def broadcast():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        body    = request.form.get('body', '').strip()

        if not subject or not body:
            flash('Both a subject and message body are required.', 'warning')
            return redirect(url_for('platform.broadcast'))

        notification = Notification(
            sender_id      = current_user.id,
            school_id      = None,          # platform-wide: not scoped to one school
            recipient_type = 'role',
            recipient_role = 'SuperAdmin',  # all SuperAdmins across all schools
            recipient_id   = None,
            subject        = subject,
            body           = body,
        )
        db.session.add(notification)
        db.session.commit()

        flash('Broadcast sent to all School SuperAdmins.', 'success')
        return redirect(url_for('platform.dashboard'))

    # Inbox: messages FROM SuperAdmins TO PlatformAdmin
    inbox = (
        Notification.query
        .filter_by(recipient_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )

    return render_template('platform/broadcast.html', inbox=inbox)


@platform_bp.route('/broadcast/<int:notif_id>/read', methods=['POST'])
@login_required
@platform_admin_required
def mark_broadcast_read(notif_id):
    n = Notification.query.get_or_404(notif_id)
    if n.recipient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('platform.broadcast'))
    n.is_read = True
    db.session.commit()
    return redirect(url_for('platform.broadcast'))


# ---------------------------------------------------------------------------
# TRANSCRIPT COUPONS
# One permanent code per student — assigned once, lives forever on the
# Student row. Platform Admin is the only one who can generate these.
# ---------------------------------------------------------------------------
from app.models import Student, Class  # already imported above but explicit for clarity

@platform_bp.route('/transcript-coupons', methods=['GET', 'POST'])
@login_required
@platform_admin_required
def transcript_coupons():
    """
    Assign transcript coupon codes to students who don't have one yet.
    Platform Admin selects a school + optional class filter, then bulk-assigns
    codes to all students in that scope that are still NULL.
    Individual override is also available per student.
    """
    schools = School.query.filter_by(is_active=True).order_by(School.name).all()
    selected_school_id = request.values.get('school_id', type=int)
    selected_class_id  = request.values.get('class_id',  type=int)

    selected_school = School.query.get(selected_school_id) if selected_school_id else None

    # Classes for the selected school (for filter dropdown)
    classes_for_school = []
    if selected_school:
        classes_for_school = (
            Class.query
            .filter_by(school_id=selected_school.id)
            .order_by(Class.class_name)
            .all()
        )

    # Student list based on filters
    students = []
    if selected_school:
        q = Student.query.filter_by(school_id=selected_school.id, is_active=True)
        if selected_class_id:
            q = q.filter_by(current_class_id=selected_class_id)
        students = q.order_by(Student.last_name, Student.first_name).all()

    if request.method == 'POST':
        action   = request.form.get('action')
        school_id = request.form.get('school_id', type=int)
        class_id  = request.form.get('class_id',  type=int)
        length    = request.form.get('length', 8, type=int)

        school = School.query.get(school_id) if school_id else None
        if not school:
            flash('Please select a school.', 'warning')
            return redirect(url_for('platform.transcript_coupons'))

        if not (6 <= length <= 16):
            flash('Code length must be between 6 and 16.', 'warning')
            return redirect(url_for('platform.transcript_coupons',
                                    school_id=school_id, class_id=class_id))

        charset = CHARSET_MAP['alphanumeric']

        if action == 'bulk_assign':
            # Assign only to students who don't have a code yet
            q = Student.query.filter_by(
                school_id=school.id, is_active=True,
                transcript_coupon=None
            )
            if class_id:
                q = q.filter_by(current_class_id=class_id)
            targets = q.all()

            assigned = 0
            skipped  = 0
            for student in targets:
                try:
                    code = _generate_unique_transcript_code(length, charset)
                    student.transcript_coupon = code
                    assigned += 1
                except RuntimeError:
                    skipped += 1

            db.session.commit()

            msg = f'{assigned} transcript coupon(s) assigned.'
            if skipped:
                msg += f' {skipped} could not be generated (code space issue — try longer length).'
            flash(msg, 'success' if not skipped else 'warning')

        elif action == 'assign_single':
            student_id = request.form.get('student_id', type=int)
            student = Student.query.filter_by(
                id=student_id, school_id=school.id
            ).first_or_404()

            if student.transcript_coupon:
                flash(
                    f'{student.first_name} {student.last_name} already has a '
                    f'transcript coupon: {student.transcript_coupon}',
                    'warning'
                )
            else:
                try:
                    student.transcript_coupon = _generate_unique_transcript_code(
                        length, charset
                    )
                    db.session.commit()
                    flash(
                        f'Transcript coupon assigned to '
                        f'{student.first_name} {student.last_name}: '
                        f'{student.transcript_coupon}',
                        'success'
                    )
                except RuntimeError as e:
                    flash(str(e), 'danger')

        return redirect(url_for(
            'platform.transcript_coupons',
            school_id=school_id,
            class_id=class_id,
        ))

    # Summary counts
    assigned_count   = Student.query.filter_by(school_id=selected_school_id, is_active=True)\
                               .filter(Student.transcript_coupon.isnot(None)).count() \
                               if selected_school_id else 0
    unassigned_count = Student.query.filter_by(school_id=selected_school_id,
                                               is_active=True,
                                               transcript_coupon=None).count() \
                               if selected_school_id else 0

    return render_template(
        'platform/transcript_coupons.html',
        schools=schools,
        selected_school=selected_school,
        classes_for_school=classes_for_school,
        selected_class_id=selected_class_id,
        students=students,
        assigned_count=assigned_count,
        unassigned_count=unassigned_count,
        charset_options=list(CHARSET_MAP.keys()),
    )


def _generate_unique_transcript_code(length, charset):
    """
    Generate a code unique across ALL student.transcript_coupon values.
    Transcript codes live on the Student row, not the Coupon table,
    so we query Student instead of Coupon here.
    """
    for _ in range(50):
        code = ''.join(random.choices(charset, k=length))
        if not Student.query.filter_by(transcript_coupon=code).first():
            return code
    raise RuntimeError(
        'Could not generate a unique transcript coupon after 50 attempts. '
        'Try a longer code length.'
    )


@platform_bp.route('/schools/<int:school_id>/export')
@login_required
@platform_admin_required
def export_school_data(school_id):
    from app.utils.export import generate_school_export
    from flask import Response
    from datetime import datetime
    buf, school_name = generate_school_export(school_id)
    filename = f"GRPMS_Export_{school_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@platform_bp.route('/schools/<int:school_id>/reset-superadmin', methods=['POST'])
@login_required
@platform_admin_required
def reset_superadmin_password(school_id):
    school = School.query.get_or_404(school_id)
    super_admin = User.query.filter_by(
        school_id=school.id, role='SuperAdmin'
    ).first()

    if not super_admin:
        flash(f'No SuperAdmin found for {school.name}.', 'danger')
        return redirect(url_for('platform.dashboard'))

    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 8:
        flash('Password must be at least 8 characters.', 'warning')
        return redirect(url_for('platform.dashboard'))

    super_admin.set_password(new_password)
    db.session.commit()
    flash(
        f'Password reset for SuperAdmin @{super_admin.username} '
        f'at {school.name}.', 'success'
    )
    return redirect(url_for('platform.dashboard'))

