"""enforce unique school.code (normalized)

Revision ID: 0004_enforce_school_code_uniqueness
Revises: 2ef9e254bb24
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '0004_enforce_school_code_uniqueness'
down_revision = '2ef9e254bb24'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # 1) Read existing non-empty codes
    rows = bind.execute(text("SELECT id, code FROM schools WHERE code IS NOT NULL AND code <> ''")).fetchall()

    # 2) Normalize in Python (same rules as application): uppercase, keep A-Z only, max 6 chars
    import re
    def normalize(v):
        if v is None:
            return None
        s = re.sub(r'[^A-Za-z]', '', str(v).strip().upper())[:6]
        return s or None

    # Build mapping of normalized_code -> [ids]
    norm_map = {}
    updates = []  # (id, new_code) for rows that need updating
    for r in rows:
        sid = r[0]
        code = r[1]
        nid = normalize(code)
        if nid != code:
            updates.append((sid, nid))
        if nid:
            norm_map.setdefault(nid, []).append(sid)

    # 3) If any normalized code maps to multiple rows, fail safely and list conflicts
    conflicts = {k: v for k, v in norm_map.items() if len(v) > 1}
    if conflicts:
        # Make the migration fail loudly so operators can resolve duplicates manually
        raise RuntimeError(
            f"Cannot add unique constraint: duplicate normalized school codes detected: {conflicts}. "
            "Resolve these conflicts before applying the migration."
        )

    # 4) Apply normalization updates (if any)
    for sid, newcode in updates:
        bind.execute(
            text("UPDATE schools SET code = :code WHERE id = :id"),
            {"code": newcode, "id": sid}
        )

    # 5) Create the unique constraint on the code column (allows NULLs)
    with op.batch_alter_table('schools', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_schools_code', ['code'])


def downgrade():
    with op.batch_alter_table('schools', schema=None) as batch_op:
        batch_op.drop_constraint('uq_schools_code', type_='unique')
