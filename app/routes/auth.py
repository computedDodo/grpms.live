from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app.models import User
from app import db
from app.utils.decorators import active_account_required

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/', methods=['GET'])
def index():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard_router'))
    # Show landing page for unauthenticated visitors
    return render_template('landing.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard_router'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('This account has been deactivated. Contact your administrator.', 'warning')
                return redirect(url_for('auth.login'))

            login_user(user)
            flash(f'Welcome back, {user.display_name}!', 'success')
            return redirect(url_for('auth.dashboard_router'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
@active_account_required
def logout():
    logout_user()
    flash('You have been securely logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/dashboard_router')
@login_required
@active_account_required
def dashboard_router():
    """
    Single entry point after login -- routes every role to its own
    dashboard. This is the ONLY place role -> blueprint mapping lives,
    so adding a role later means touching one function, not every link
    in the app.
    """
    role_routes = {
        'PlatformAdmin': 'platform.dashboard',
        'SuperAdmin':    'superadmin.dashboard',
        'Admin':         'admin.dashboard',
        'Cashier':       'cashier.dashboard',
        'FormMaster':    'teacher.dashboard',
        'Teacher':       'teacher.dashboard',
        'Student':       'student.dashboard',
    }

    target = role_routes.get(current_user.role)
    if not target:
        flash('Your account role is not recognized. Contact the Platform Admin.', 'danger')
        return redirect(url_for('auth.login'))

    return redirect(url_for(target))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
@active_account_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('Incorrect current password. Please try again.', 'danger')
            return redirect(url_for('auth.change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match.', 'warning')
            return redirect(url_for('auth.change_password'))

        if len(new_password) < 6:
            flash('New password should be at least 6 characters.', 'warning')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(new_password)
        db.session.commit()

        flash('Your password has been successfully updated.', 'success')
        return redirect(url_for('auth.dashboard_router'))

    return render_template('auth/change_password.html')
