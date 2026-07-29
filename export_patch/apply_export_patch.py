"""
apply_export_patch.py
Run this from inside ~/grpms_v2:
    python3 apply_export_patch.py

What it does:
  1. Copies app/utils/export.py into your project
  2. Appends the export route to platform.py
  3. Appends the export route to superadmin.py
  4. Adds Export button to platform/dashboard.html
  5. Adds Export card to superadmin/dashboard.html
  6. Verifies openpyxl is installed
"""
import os
import sys
import shutil
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))

def check(condition, msg):
    if condition:
        print(f"  ✓ {msg}")
    else:
        print(f"  ✗ FAILED: {msg}")
        sys.exit(1)

# ── 0. Check openpyxl ────────────────────────────────────────────────────────
print("\n[0] Checking openpyxl...")
try:
    import openpyxl
    print(f"  ✓ openpyxl {openpyxl.__version__} available")
except ImportError:
    print("  Installing openpyxl...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'openpyxl',
                    '--break-system-packages', '-q'], check=True)
    print("  ✓ openpyxl installed")

# ── 1. Copy export.py ────────────────────────────────────────────────────────
print("\n[1] Copying export.py...")
src = os.path.join(BASE, 'app', 'utils', 'export.py')
dst = os.path.join(BASE, '..', 'grpms_v2', 'app', 'utils', 'export.py')
# If running from inside grpms_v2 already:
dst2 = os.path.join(BASE, 'app', 'utils', 'export.py')
target = dst2 if os.path.isdir(os.path.join(BASE, 'app')) else dst

shutil.copy(src, target)
check(os.path.exists(target), f"export.py copied to {target}")

# ── 2. Append route to platform.py ──────────────────────────────────────────
print("\n[2] Adding export route to platform.py...")
platform_path = os.path.join(BASE, 'app', 'routes', 'platform.py')
content = open(platform_path).read()

platform_route = '''

# ---------------------------------------------------------------------------
# SCHOOL DATA EXPORT  (Platform Admin — any school)
# ---------------------------------------------------------------------------
@platform_bp.route('/schools/<int:school_id>/export')
@login_required
@platform_admin_required
def export_school_data(school_id):
    """Download complete Excel export of any school's data."""
    from app.utils.export import generate_school_export
    from flask import Response
    from datetime import datetime

    buf, school_name = generate_school_export(school_id)
    filename = (
        f"GRPMS_Export_{school_name.replace(' ', '_')}"
        f"_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    )
    return Response(
        buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
'''

if 'export_school_data' in content:
    print("  ✓ Route already exists — skipping")
else:
    with open(platform_path, 'a') as f:
        f.write(platform_route)
    check('export_school_data' in open(platform_path).read(),
          "Export route added to platform.py")

# ── 3. Append route to superadmin.py ────────────────────────────────────────
print("\n[3] Adding export route to superadmin.py...")
super_path = os.path.join(BASE, 'app', 'routes', 'superadmin.py')
content = open(super_path).read()

super_route = '''

# ---------------------------------------------------------------------------
# SCHOOL DATA EXPORT  (SuperAdmin — own school only)
# ---------------------------------------------------------------------------
@superadmin_bp.route('/export')
@login_required
@super_admin_required
def export_school_data():
    """Download complete Excel export of this school's own data."""
    from app.utils.export import generate_school_export
    from flask import Response
    from datetime import datetime

    buf, school_name = generate_school_export(current_user.school_id)
    filename = (
        f"GRPMS_Export_{school_name.replace(' ', '_')}"
        f"_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    )
    return Response(
        buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
'''

if 'export_school_data' in content:
    print("  ✓ Route already exists — skipping")
else:
    with open(super_path, 'a') as f:
        f.write(super_route)
    check('export_school_data' in open(super_path).read(),
          "Export route added to superadmin.py")

# ── 4. Add Export button to platform/dashboard.html ─────────────────────────
print("\n[4] Adding Export button to platform dashboard...")
pdash = os.path.join(BASE, 'app', 'templates', 'platform', 'dashboard.html')
content = open(pdash).read()

export_btn = '''              <a href="{{ url_for('platform.export_school_data', school_id=school.id) }}"
                 class="g6-btn g6-btn-outline"
                 style="font-size:0.78rem; padding:0.4rem 0.8rem; color:#5db800;"
                 title="Download full school data as Excel">
                <i class="fas fa-file-excel"></i> Export
              </a>'''

if 'export_school_data' in content:
    print("  ✓ Button already exists — skipping")
else:
    # Insert after the Edit button
    old = '''              <a href="{{ url_for('platform.edit_school', school_id=school.id) }}"
                 class="g6-btn g6-btn-outline" style="font-size:0.78rem; padding:0.4rem 0.8rem;">
                <i class="fas fa-edit"></i> Edit
              </a>'''
    new = old + '\n' + export_btn

    if old in content:
        content = content.replace(old, new)
        with open(pdash, 'w') as f:
            f.write(content)
        check('export_school_data' in open(pdash).read(),
              "Export button added to platform dashboard")
    else:
        print("  ! Edit button pattern not found — adding button manually")
        print("    Open platform/dashboard.html and add this after the Edit button:")
        print(export_btn)

# ── 5. Add Export card to superadmin/dashboard.html ─────────────────────────
print("\n[5] Adding Export card to SuperAdmin dashboard...")
sdash = os.path.join(BASE, 'app', 'templates', 'superadmin', 'dashboard.html')
content = open(sdash).read()

export_card = '''
  <a href="{{ url_for('superadmin.export_school_data') }}"
     class="g6-card"
     style="text-decoration:none; display:flex; align-items:center;
            gap:0.75rem; padding:1rem; margin-top:0.75rem;">
    <div style="width:40px; height:40px; border-radius:var(--radius-sm);
                background:rgba(126,211,33,0.12); color:#5db800;
                display:flex; align-items:center; justify-content:center;
                font-size:1.1rem; flex-shrink:0;">
      <i class="fas fa-file-excel"></i>
    </div>
    <div>
      <div style="font-weight:700; font-size:0.88rem; color:var(--slate-900);">
        Export School Data
      </div>
      <div class="g6-text-sm g6-muted">
        Download full Excel backup of all students, scores &amp; records
      </div>
    </div>
  </a>
'''

if 'export_school_data' in content:
    print("  ✓ Card already exists — skipping")
else:
    # Append before closing {% endblock %}
    content = content.replace('{% endblock %}', export_card + '\n{% endblock %}', 1)
    with open(sdash, 'w') as f:
        f.write(content)
    check('export_school_data' in open(sdash).read(),
          "Export card added to SuperAdmin dashboard")

# ── Done ─────────────────────────────────────────────────────────────────────
print("\n" + "="*52)
print("  EXPORT PATCH COMPLETE")
print("="*52)
print("""
Next steps:
  1. flask run
  2. Login as Platform Admin → Schools → click 'Export' next to any school
     → Excel file downloads with 8 sheets of data
  3. Login as SuperAdmin → Dashboard → 'Export School Data' card
     → Same Excel, scoped to own school only
  4. Open the .xlsx in any spreadsheet app to verify
""")
