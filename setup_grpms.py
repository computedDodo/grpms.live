#!/usr/bin/env python3
"""
GRPMS V2 — Project Setup Script
================================
Run this script ONCE after extracting the ZIP file.
It verifies the folder structure, creates a virtual environment,
and prints the exact commands to get the app running locally.

Usage:
    python setup_grpms.py

Requirements: Python 3.10+ installed on your machine.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Expected project structure
# ---------------------------------------------------------------------------
EXPECTED_FILES = [
    # Root
    "run.py",
    "config.py",
    "requirements.txt",
    ".env.example",
    ".gitignore",

    # App package
    "app/__init__.py",
    "app/models.py",

    # Routes
    "app/routes/__init__.py",
    "app/routes/auth.py",
    "app/routes/platform.py",
    "app/routes/superadmin.py",
    "app/routes/admin.py",
    "app/routes/cashier.py",
    "app/routes/teacher.py",
    "app/routes/student.py",

    # Utils
    "app/utils/computations.py",
    "app/utils/decorators.py",
    "app/utils/seed_demo.py",

    # Static
    "app/static/css/g6-design-system.css",

    # Shared templates
    "app/templates/shared/base.html",
    "app/templates/shared/coming_soon.html",

    # Auth templates
    "app/templates/auth/login.html",
    "app/templates/auth/change_password.html",

    # Platform templates
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

    # SuperAdmin templates
    "app/templates/superadmin/base_superadmin.html",
    "app/templates/superadmin/dashboard.html",
    "app/templates/superadmin/settings.html",
    "app/templates/superadmin/staff.html",
    "app/templates/superadmin/staff_archive.html",
    "app/templates/superadmin/academic_setup.html",
    "app/templates/superadmin/coupon_register.html",
    "app/templates/superadmin/notifications.html",
    "app/templates/superadmin/compose_notification.html",

    # Admin templates
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

    # Cashier templates
    "app/templates/cashier/base_cashier.html",
    "app/templates/cashier/dashboard.html",
    "app/templates/cashier/coupon_list.html",
    "app/templates/cashier/coupon_print.html",
    "app/templates/cashier/coupon_tracker.html",
    "app/templates/cashier/result_release.html",
    "app/templates/cashier/notifications.html",
    "app/templates/cashier/compose_notification.html",

    # Teacher templates
    "app/templates/teacher/base_teacher.html",
    "app/templates/teacher/dashboard.html",
    "app/templates/teacher/score_entry.html",
    "app/templates/teacher/master_list.html",
    "app/templates/teacher/class_management.html",
    "app/templates/teacher/notifications.html",
    "app/templates/teacher/compose_notification.html",

    # Student templates
    "app/templates/student/base_student.html",
    "app/templates/student/dashboard.html",
    "app/templates/student/result.html",
    "app/templates/student/transcript.html",
    "app/templates/student/notifications.html",
    "app/templates/student/feedback.html",

    # Migrations
    "migrations/alembic.ini",
    "migrations/env.py",
    "migrations/script.py.mako",
    "migrations/versions/0001_initial_schema.py",
    "migrations/versions/0002_transcript_coupon.py",
]

EXPECTED_DIRS = [
    "app",
    "app/routes",
    "app/utils",
    "app/static/css",
    "app/static/uploads",
    "app/templates/shared",
    "app/templates/auth",
    "app/templates/platform",
    "app/templates/superadmin",
    "app/templates/admin",
    "app/templates/cashier",
    "app/templates/teacher",
    "app/templates/student",
    "migrations",
    "migrations/versions",
]


def separator(char="─", width=60):
    print(char * width)


def check_structure(base: Path):
    separator()
    print("  Verifying project structure...")
    separator()

    missing = []
    for rel in EXPECTED_FILES:
        p = base / rel
        if p.exists():
            print(f"  ✓  {rel}")
        else:
            print(f"  ✗  MISSING: {rel}")
            missing.append(rel)

    print()
    if missing:
        print(f"  ⚠  {len(missing)} file(s) missing — see list above.")
        print("     Extract the ZIP again and make sure all files are present.")
        return False
    else:
        print(f"  ✓  All {len(EXPECTED_FILES)} files present.")
        return True


def create_dirs(base: Path):
    for d in EXPECTED_DIRS:
        (base / d).mkdir(parents=True, exist_ok=True)
    # Ensure uploads folder has a .gitkeep
    gitkeep = base / "app/static/uploads/.gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()


def setup_env(base: Path):
    env_file    = base / ".env"
    env_example = base / ".env.example"
    if env_file.exists():
        print("  ✓  .env already exists — skipping copy.")
    elif env_example.exists():
        shutil.copy(env_example, env_file)
        print("  ✓  .env created from .env.example")
        print("  ⚠  Open .env and set a strong SECRET_KEY before running!")
    else:
        # Write a minimal .env
        env_file.write_text(
            "FLASK_ENV=development\n"
            "SECRET_KEY=change-this-to-a-long-random-string\n"
        )
        print("  ✓  Minimal .env created.")
        print("  ⚠  Open .env and set a strong SECRET_KEY before running!")


def find_python():
    for cmd in ("python3", "python"):
        if shutil.which(cmd):
            result = subprocess.run(
                [cmd, "--version"], capture_output=True, text=True
            )
            version = result.stdout.strip() or result.stderr.strip()
            major, minor = int(version.split()[1].split(".")[0]), int(version.split()[1].split(".")[1])
            if major >= 3 and minor >= 10:
                return cmd
    return None


def create_venv(base: Path, python_cmd: str):
    venv_path = base / "venv"
    if venv_path.exists():
        print("  ✓  Virtual environment already exists — skipping.")
        return True
    print(f"  Creating virtual environment with {python_cmd}...")
    result = subprocess.run(
        [python_cmd, "-m", "venv", str(venv_path)],
        cwd=str(base),
    )
    if result.returncode == 0:
        print("  ✓  Virtual environment created at ./venv")
        return True
    else:
        print("  ✗  Failed to create virtual environment.")
        return False


def main():
    base = Path(__file__).parent.resolve()

    print()
    separator("═")
    print("  GRPMS V2 — Project Setup")
    separator("═")
    print(f"  Project directory: {base}")
    print()

    # 1. Create any missing directories
    create_dirs(base)

    # 2. Verify structure
    structure_ok = check_structure(base)
    print()

    # 3. Set up .env
    separator()
    print("  Environment file...")
    separator()
    setup_env(base)
    print()

    # 4. Find Python 3.10+
    separator()
    print("  Python version check...")
    separator()
    python_cmd = find_python()
    if not python_cmd:
        print("  ✗  Python 3.10+ not found. Install it from https://python.org")
        sys.exit(1)
    result = subprocess.run([python_cmd, "--version"], capture_output=True, text=True)
    print(f"  ✓  Found: {result.stdout.strip() or result.stderr.strip()}")
    print()

    # 5. Create venv
    separator()
    print("  Virtual environment...")
    separator()
    venv_ok = create_venv(base, python_cmd)
    print()

    # 6. Print next steps
    separator("═")
    print("  Setup complete! Run these commands to start the app:")
    separator("═")

    is_windows = sys.platform == "win32"
    activate   = r"venv\Scripts\activate" if is_windows else "source venv/bin/activate"
    pip_install = "pip install -r requirements.txt"
    db_init     = "flask db upgrade"
    seed_admin  = "flask seed-platform-admin"
    seed_demo   = "flask seed-demo-school     # optional — sample data for testing"
    run_app     = "flask run                  # or: python run.py"

    print()
    print(f"  1.  {activate}")
    print(f"  2.  {pip_install}")
    print(f"  3.  {db_init}")
    print(f"  4.  {seed_admin}")
    print(f"  5.  {seed_demo}")
    print(f"  6.  {run_app}")
    print()
    separator()
    print("  Then open: http://127.0.0.1:5000")
    print()
    print("  ⚠  Before going to production:")
    print("     - Set a strong SECRET_KEY in .env")
    print("     - Set FLASK_ENV=production in .env")
    print("     - Set DATABASE_URL to a PostgreSQL connection string")
    separator("═")
    print()


if __name__ == "__main__":
    main()
