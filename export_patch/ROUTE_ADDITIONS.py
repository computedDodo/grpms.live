# ════════════════════════════════════════════════════════════════════════════
# ADD TO: app/routes/platform.py
# Append these two routes at the bottom of the file
# ════════════════════════════════════════════════════════════════════════════

@platform_bp.route('/schools/<int:school_id>/export')
@login_required
@platform_admin_required
def export_school_data(school_id):
    """
    Platform Admin downloads a complete Excel export of any school's data.
    All 8 sheets: Summary, Students, Scores, Staff, Classes, Subjects,
    Allocations, Coupons.
    """
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


# ════════════════════════════════════════════════════════════════════════════
# ADD TO: app/routes/superadmin.py
# Append this route at the bottom of the file
# ════════════════════════════════════════════════════════════════════════════

@superadmin_bp.route('/export')
@login_required
@super_admin_required
def export_school_data():
    """
    SuperAdmin downloads a complete Excel export of their own school's data.
    Scoped strictly to current_user.school_id — cannot export other schools.
    """
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
