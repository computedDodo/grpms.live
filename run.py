try:
    from psycopg2cffi import compat
    compat.register()
except ImportError:
    pass  # not on ARM/Termux — use normal psycopg2

from app import create_app, db
from app.models import (
    User, School, Student, Teacher, AcademicSession, Term,
    Class, Subject, SubjectAllocation, Score,
    Coupon, CouponActivation, Notification
)

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'School': School,
        'Student': Student,
        'Teacher': Teacher,
        'AcademicSession': AcademicSession,
        'Term': Term,
        'Class': Class,
        'Subject': Subject,
        'SubjectAllocation': SubjectAllocation,
        'Score': Score,
        'Coupon': Coupon,
        'CouponActivation': CouponActivation,
        'Notification': Notification,
    }


@app.cli.command('seed-platform-admin')
def seed_platform_admin():
    """
    Create the very first PlatformAdmin account (you).
    Run once: flask seed-platform-admin
    Prompts for username and password so credentials never live in source code.
    """
    import getpass

    existing = User.query.filter_by(role='PlatformAdmin').first()
    if existing:
        print(f"A PlatformAdmin already exists: '{existing.username}'. Aborting.")
        return

    username = input("Choose a PlatformAdmin username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    if User.query.filter_by(username=username).first():
        print("That username is already taken.")
        return

    password = getpass.getpass("Choose a password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords did not match. Aborting.")
        return
    if len(password) < 8:
        print("Password should be at least 8 characters.")
        return

    admin = User(username=username, role='PlatformAdmin', school_id=None)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"PlatformAdmin '{username}' created successfully.")


@app.cli.command('seed-demo-school')
def seed_demo_school_cmd():
    """
    Create one demo school with sample data for local testing.
    Run: flask seed-demo-school
    Safe to run once — skips if 'Demo Academy' already exists.
    """
    from app.utils.seed_demo import seed_demo_school
    seed_demo_school()


if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', True), host='0.0.0.0', port=5000)
