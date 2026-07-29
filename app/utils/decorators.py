"""
Access control decorators.

Two layers of protection on almost every route in this app:
  1. Role check         -- is this user allowed to even be on this page?
  2. School-scope check  -- if the route touches a specific record
                            (a Student, Class, Score, etc.), does that
                            record actually belong to the current user's
                            school?

IMPORTANT DESIGN DECISION:
PlatformAdmin does NOT automatically pass school-level role checks
(SuperAdmin/Admin/Cashier/Teacher/FormMaster). PlatformAdmin's job is
school management, coupon generation, and cross-school broadcast --
not day-to-day school operations. Keeping this boundary hard makes the
school-isolation guarantee easy to reason about and easy to audit later:
nobody can ever touch a school's operational data except that school's
own staff. If you (the developer) ever need emergency access to a
school's internal screens for support, that should be a deliberate,
logged, separate feature -- not a silent bypass baked into every decorator.
"""
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user, logout_user


def _deny(message='Access denied: you do not have permission to view that page.'):
    flash(message, 'danger')
    return redirect(url_for('auth.dashboard_router'))


def roles_required(*allowed_roles):
    """
    Restrict a route to one or more exact roles. No implicit elevation.
    Usage: @roles_required('Admin', 'SuperAdmin')
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if not current_user.is_active:
                logout_user()
                flash('Your account has been deactivated. Contact your administrator.', 'warning')
                return redirect(url_for('auth.login'))
            if current_user.role not in allowed_roles:
                return _deny(f'Access denied: requires {" or ".join(allowed_roles)} role.')
            return f(*args, **kwargs)
        return wrapped
    return decorator


def active_account_required(f):
    """
    For routes that are role-agnostic (every authenticated role may use
    them: logout, dashboard_router, change_password) and therefore don't
    go through roles_required(). Without this, a deactivated account with
    a still-valid session cookie could keep hitting these routes even
    though every ROLE-SPECIFIC route would correctly reject them.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        if current_user.is_authenticated and not current_user.is_active:
            logout_user()
            flash('Your account has been deactivated. Contact your administrator.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Role decorators.
# SuperAdmin is the school OWNER and may step into their own school's
# Admin/Cashier/Teacher screens for oversight -- this mirrors the V1
# pattern where Admin could access the Teacher portal for testing.
# PlatformAdmin is deliberately excluded from all of these.
# ---------------------------------------------------------------------------
platform_admin_required = roles_required('PlatformAdmin')
super_admin_required    = roles_required('SuperAdmin')
admin_required          = roles_required('Admin', 'SuperAdmin')
cashier_required        = roles_required('Cashier', 'SuperAdmin')
teacher_required        = roles_required('Teacher', 'FormMaster', 'SuperAdmin')
form_master_required    = roles_required('FormMaster', 'SuperAdmin')
student_required        = roles_required('Student')

# Any authenticated school-level staff member (used for shared screens
# like the notifications inbox, which every school role can access)
school_staff_required = roles_required(
    'Admin', 'Cashier', 'FormMaster', 'Teacher', 'SuperAdmin'
)


def get_scoped_school_id():
    """
    Returns the school_id the current user is allowed to operate within.
    PlatformAdmin gets None (not restricted -- must pick a school explicitly
    in routes that need one, e.g. generating coupons for a chosen school).
    Everyone else gets their own school_id, full stop.
    """
    if current_user.role == 'PlatformAdmin':
        return None
    return current_user.school_id


def verify_school_ownership(obj, school_id_attr='school_id'):
    """
    Defense-in-depth check for any route that fetches a record by ID from
    the URL (e.g. /admin/students/<id>). The role decorators above only
    check ROLE -- they say nothing about whether THIS specific record
    belongs to the current user's school. Call this explicitly after
    every get_or_404()-style lookup of a school-scoped object.

    Aborts with 404 (not 403) so we never leak the existence of another
    school's records through the error response itself.
    """
    if current_user.role == 'PlatformAdmin':
        return  # platform admin operates across schools by design
    obj_school_id = getattr(obj, school_id_attr, None)
    if obj_school_id != current_user.school_id:
        abort(404)


def same_school_required(get_school_id):
    """
    Decorator factory for routes that take a school_id directly in the
    URL (e.g. /platform/schools/<school_id>/coupons). Confirms the
    current user belongs to that school -- PlatformAdmin is exempt since
    it's the only role meant to navigate between schools.

    Usage:
        @same_school_required(lambda **kw: kw['school_id'])
        def my_view(school_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if current_user.role == 'PlatformAdmin':
                return f(*args, **kwargs)
            target_school_id = get_school_id(**kwargs)
            if current_user.school_id != target_school_id:
                return _deny("You do not have access to this school's data.")
            return f(*args, **kwargs)
        return wrapped
    return decorator
