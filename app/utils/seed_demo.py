"""
Demo data seeder — OPTIONAL, for local development/testing only.

Usage:
    flask seed-demo-school

Creates one demo school with a SuperAdmin, one class, one subject,
one academic session/term, and a handful of coupons — enough to
click through the system end-to-end without typing everything by hand.

This is intentionally NOT auto-run. You call it explicitly.
"""
import random
import string

from app import db
from app.models import (
    School, User, Teacher, Class, Subject, AcademicSession, Term, Coupon
)


def generate_code(length=8, charset=None):
    charset = charset or 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(charset, k=length))


def seed_demo_school():
    if School.query.filter_by(name='Demo Academy').first():
        print("Demo school already exists. Skipping.")
        return

    school = School(
        name='Demo Academy',
        motto='Learning Without Limits',
        principal_name='Mrs. Demo Principal',
    )
    db.session.add(school)
    db.session.flush()  # get school.id without full commit

    # SuperAdmin for this school
    super_admin = User(
        username='demo_superadmin',
        role='SuperAdmin',
        school_id=school.id,
    )
    super_admin.set_password('Demo@1234')
    db.session.add(super_admin)

    # One class
    demo_class = Class(school_id=school.id, class_name='JSS 1', section='Secondary')
    db.session.add(demo_class)

    # One subject
    subject = Subject(school_id=school.id, subject_name='Mathematics', subject_code='MTH')
    db.session.add(subject)

    # Academic session + term, both active
    session = AcademicSession(session_name='2025/2026', school_id=school.id, is_active=True)
    db.session.add(session)
    db.session.flush()

    term = Term(term_name='First Term', session_id=session.id, is_active=True)
    db.session.add(term)
    db.session.flush()

    # 10 vacant coupons for this term
    codes_created = 0
    while codes_created < 10:
        code = generate_code()
        if Coupon.query.filter_by(code=code).first():
            continue
        db.session.add(Coupon(code=code, school_id=school.id, term_id=term.id))
        codes_created += 1

    db.session.commit()

    print("Demo school created.")
    print(f"  SuperAdmin login -> username: demo_superadmin | password: Demo@1234")
    print(f"  School: {school.name} (id={school.id})")
    print(f"  10 unused coupons generated for {term.term_name}, {session.session_name}")
