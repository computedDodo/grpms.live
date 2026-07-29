"""add transcript_coupon to students

Revision ID: 0002_transcript_coupon
Revises: 0001_initial
Create Date: 2026-07-02

transcript_coupon is a permanent per-student code assigned once by the
Platform Admin. It gates transcript downloads (not views) for both
admin and student portals. NULL = not yet assigned.
"""
from alembic import op
import sqlalchemy as sa

revision      = '0002_transcript_coupon'
down_revision = '0001_initial'
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column(
        'students',
        sa.Column('transcript_coupon', sa.String(20), nullable=True)
    )
    # Unique constraint — no two students can share a transcript coupon code
    op.create_unique_constraint(
        'uq_student_transcript_coupon',
        'students',
        ['transcript_coupon']
    )
    # Index for fast lookup when a code is entered by admin or student
    op.create_index(
        'ix_student_transcript_coupon',
        'students',
        ['transcript_coupon']
    )


def downgrade():
    op.drop_index('ix_student_transcript_coupon', table_name='students')
    op.drop_constraint('uq_student_transcript_coupon', 'students', type_='unique')
    op.drop_column('students', 'transcript_coupon')
