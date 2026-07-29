"""
Run this from inside the grpms_v2/ folder:
    python verify_structure.py

It checks that every expected file exists and reports anything missing or unexpected.
"""
import os

EXPECTED = [
    "config.py", "run.py", "requirements.txt", ".env.example", ".gitignore",
    "migrations/alembic.ini", "migrations/env.py", "migrations/script.py.mako",
    "migrations/versions/0001_initial_schema.py",
    "migrations/versions/0002_transcript_coupon.py",
    "app/__init__.py", "app/models.py",
    "app/routes/__init__.py", "app/routes/auth.py", "app/routes/platform.py",
    "app/routes/superadmin.py", "app/routes/admin.py", "app/routes/cashier.py",
    "app/routes/teacher.py", "app/routes/student.py",
    "app/utils/computations.py", "app/utils/decorators.py", "app/utils/seed_demo.py",
    "app/static/css/g6-design-system.css",
    "app/static/uploads/.gitkeep",
    "app/templates/shared/base.html",
    "app/templates/shared/coming_soon.html",
    "app/templates/auth/login.html",
    "app/templates/auth/change_password.html",
    "app/templates/platform/base_platform.html",
    "app/templates/platform/dashboard.html",
    "app/templates/platform/add_school.html",
    "app/templates/platform/edit_school.html",
    "app/templates/platform/create_superadmin.html",
    "app/templates/platform/generate_coupons.html",
    "app/templates/platform/coupon_register.html",
    "app/templates/platform/coupon_print.html",
    "app/templates/platform/broadcast.html",
    "app/templates/platform/transcript_coupons.html",
    "app/templates/superadmin/base_superadmin.html",
    "app/templates/superadmin/dashboard.html",
    "app/templates/superadmin/settings.html",
    "app/templates/superadmin/staff.html",
    "app/templates/superadmin/staff_archive.html",
    "app/templates/superadmin/academic_setup.html",
    "app/templates/superadmin/coupon_register.html",
    "app/templates/superadmin/notifications.html",
    "app/templates/superadmin/compose_notification.html",
    "app/templates/admin/base_admin.html",
    "app/templates/admin/dashboard.html",
    "app/templates/admin/classes.html",
    "app/templates/admin/edit_class.html",
    "app/templates/admin/subjects.html",
    "app/templates/admin/students.html",
    "app/templates/admin/edit_student.html",
    "app/templates/admin/allocations.html",
    "app/templates/admin/form_masters.html",
    "app/templates/admin/archive_vault.html",
    "app/templates/admin/report_card.html",
    "app/templates/admin/transcript.html",
    "app/templates/admin/broad_sheet.html",
    "app/templates/admin/notifications.html",
    "app/templates/admin/compose_notification.html",
    "app/templates/cashier/base_cashier.html",
    "app/templates/cashier/dashboard.html",
    "app/templates/cashier/coupon_list.html",
    "app/templates/cashier/coupon_print.html",
    "app/templates/cashier/result_release.html",
    "app/templates/cashier/coupon_tracker.html",
    "app/templates/cashier/notifications.html",
    "app/templates/cashier/compose_notification.html",
    "app/templates/teacher/base_teacher.html",
    "app/templates/teacher/dashboard.html",
    "app/templates/teacher/score_entry.html",
    "app/templates/teacher/master_list.html",
    "app/templates/teacher/class_management.html",
    "app/templates/teacher/notifications.html",
    "app/templates/teacher/compose_notification.html",
    "app/templates/student/base_student.html",
    "app/templates/student/dashboard.html",
    "app/templates/student/result.html",
    "app/templates/student/transcript.html",
    "app/templates/student/notifications.html",
    "app/templates/student/feedback.html",
]

base = os.path.dirname(os.path.abspath(__file__))
missing = []
ok_count = 0

for path in EXPECTED:
    full = os.path.join(base, path)
    if os.path.exists(full):
        ok_count += 1
    else:
        missing.append(path)

print(f"\nGRPMS V2 — Structure Verification")
print(f"{'='*44}")
print(f"  Expected : {len(EXPECTED)} files")
print(f"  Found    : {ok_count} files")
print(f"  Missing  : {len(missing)} files")

if missing:
    print(f"\nMISSING FILES:")
    for f in missing:
        print(f"  ✗ {f}")
else:
    print(f"\n  ✓ All files present. Structure is correct.")
    print(f"\nNext steps:")
    print(f"  1. cp .env.example .env   (then edit SECRET_KEY)")
    print(f"  2. pip install -r requirements.txt")
    print(f"  3. flask db upgrade")
    print(f"  4. flask seed-platform-admin")
    print(f"  5. flask seed-demo-school   (optional)")
    print(f"  6. flask run")
