"""add school_code and subject_section

Revision ID: 0003_school_code_subject_section
Revises: 0002_transcript_coupon
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision      = '0003_school_code_subject_section'
down_revision = '0002_transcript_coupon'
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column('schools',
        sa.Column('code', sa.String(6), nullable=True))

    op.add_column('subjects',
        sa.Column('section', sa.String(30), nullable=False,
                  server_default='All Sections'))


def downgrade():
    op.drop_column('subjects', 'section')
    op.drop_column('schools', 'code')
