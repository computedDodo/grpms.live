"""initial schema - GRPMS V2 multi-school

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-30

"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # -----------------------------------------------------------------
    # schools  (no dependencies)
    # -----------------------------------------------------------------
    op.create_table(
        'schools',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('motto', sa.String(255), server_default=''),
        sa.Column('principal_name', sa.String(100), server_default='Principal'),
        sa.Column('logo_path', sa.String(255), nullable=True),
        sa.Column('signature_path', sa.String(255), nullable=True),
        sa.Column('stamp_path', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # -----------------------------------------------------------------
    # users  (depends on schools)
    # -----------------------------------------------------------------
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id'), nullable=True),
        sa.Column('is_active', sa.Boolean, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_unique_constraint('uq_users_username', 'users', ['username'])
    op.create_index('ix_users_username', 'users', ['username'])

    # -----------------------------------------------------------------
    # academic_sessions  (depends on schools)
    # -----------------------------------------------------------------
    op.create_table(
        'academic_sessions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('session_name', sa.String(20), nullable=False),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('is_active', sa.Boolean, server_default=sa.false()),
        sa.UniqueConstraint('session_name', 'school_id', name='uq_session_school'),
    )

    # -----------------------------------------------------------------
    # terms  (depends on academic_sessions)
    # -----------------------------------------------------------------
    op.create_table(
        'terms',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('term_name', sa.String(20), nullable=False),
        sa.Column('session_id', sa.Integer, sa.ForeignKey('academic_sessions.id'), nullable=False),
        sa.Column('is_active', sa.Boolean, server_default=sa.false()),
    )

    # -----------------------------------------------------------------
    # teachers  (depends on users, schools)
    # -----------------------------------------------------------------
    op.create_table(
        'teachers',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('title', sa.String(20), server_default=''),
        sa.Column('full_name', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean, server_default=sa.true()),
        sa.UniqueConstraint('user_id', name='uq_teacher_user'),
    )

    # -----------------------------------------------------------------
    # classes  (depends on schools, teachers[form_master])
    # -----------------------------------------------------------------
    op.create_table(
        'classes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('class_name', sa.String(64), nullable=False),
        sa.Column('section', sa.String(64), server_default=''),
        sa.Column('form_master_id', sa.Integer, sa.ForeignKey('teachers.id'), nullable=True),
        sa.Column('remark_a', sa.String(255), server_default='Excellent performance. Keep it up!'),
        sa.Column('remark_b', sa.String(255), server_default='Very good result. A commendable effort.'),
        sa.Column('remark_c', sa.String(255), server_default='Good effort, but there is room for improvement.'),
        sa.Column('remark_d', sa.String(255), server_default='A fair result. You must work harder next term.'),
        sa.Column('remark_f', sa.String(255), server_default='Poor performance. Serious improvement is needed.'),
        sa.UniqueConstraint('class_name', 'school_id', name='uq_class_school'),
    )

    # -----------------------------------------------------------------
    # students  (depends on users, schools, classes)
    # -----------------------------------------------------------------
    op.create_table(
        'students',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('admission_number', sa.String(30), nullable=False),
        sa.Column('first_name', sa.String(64), nullable=False),
        sa.Column('last_name', sa.String(64), nullable=False),
        sa.Column('current_class_id', sa.Integer, sa.ForeignKey('classes.id'), nullable=True),
        sa.Column('previous_class_id', sa.Integer, sa.ForeignKey('classes.id'), nullable=True),
        sa.Column('is_active', sa.Boolean, server_default=sa.true()),
        sa.Column('archive_type', sa.String(20), server_default='none'),
        sa.Column('archive_date', sa.DateTime, nullable=True),
    )
    op.create_unique_constraint('uq_students_admission_number', 'students', ['admission_number'])
    op.create_index('ix_students_admission_number', 'students', ['admission_number'])

    # -----------------------------------------------------------------
    # subjects  (depends on schools)
    # -----------------------------------------------------------------
    op.create_table(
        'subjects',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('subject_name', sa.String(64), nullable=False),
        sa.Column('subject_code', sa.String(10), nullable=False),
        sa.UniqueConstraint('subject_code', 'school_id', name='uq_subject_code_school'),
    )

    # -----------------------------------------------------------------
    # subject_allocations  (depends on teachers, subjects, classes)
    # -----------------------------------------------------------------
    op.create_table(
        'subject_allocations',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('teacher_id', sa.Integer, sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('subject_id', sa.Integer, sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('class_id', sa.Integer, sa.ForeignKey('classes.id'), nullable=False),
        sa.UniqueConstraint('subject_id', 'class_id', name='uq_subject_class'),
    )

    # -----------------------------------------------------------------
    # scores  (depends on students, subjects, terms, academic_sessions)
    # -----------------------------------------------------------------
    op.create_table(
        'scores',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('student_id', sa.Integer, sa.ForeignKey('students.id'), nullable=False),
        sa.Column('subject_id', sa.Integer, sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('term_id', sa.Integer, sa.ForeignKey('terms.id'), nullable=False),
        sa.Column('session_id', sa.Integer, sa.ForeignKey('academic_sessions.id'), nullable=False),
        sa.Column('ca_1', sa.Float, server_default='0.0'),
        sa.Column('ca_2', sa.Float, server_default='0.0'),
        sa.Column('assign_1', sa.Float, server_default='0.0'),
        sa.Column('assign_2', sa.Float, server_default='0.0'),
        sa.Column('exam', sa.Float, server_default='0.0'),
        sa.Column('total_score', sa.Float, server_default='0.0'),
        sa.Column('grade', sa.String(2), nullable=True),
        sa.Column('remark', sa.String(50), nullable=True),
        sa.Column('is_released', sa.Boolean, server_default=sa.false()),
        sa.Column('date_entered', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('student_id', 'subject_id', 'term_id', 'session_id', name='uq_score_record'),
    )

    # -----------------------------------------------------------------
    # coupons  (depends on schools, terms; used_by -> students added after)
    # -----------------------------------------------------------------
    op.create_table(
        'coupons',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('code', sa.String(30), nullable=False),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('term_id', sa.Integer, sa.ForeignKey('terms.id'), nullable=False),
        sa.Column('is_used', sa.Boolean, server_default=sa.false()),
        sa.Column('used_by_id', sa.Integer, sa.ForeignKey('students.id'), nullable=True),
        sa.Column('used_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('code', name='uq_coupons_code'),
    )
    op.create_index('ix_coupons_code', 'coupons', ['code'])

    # -----------------------------------------------------------------
    # coupon_activations  (depends on students, terms, coupons)
    # -----------------------------------------------------------------
    op.create_table(
        'coupon_activations',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('student_id', sa.Integer, sa.ForeignKey('students.id'), nullable=False),
        sa.Column('term_id', sa.Integer, sa.ForeignKey('terms.id'), nullable=False),
        sa.Column('coupon_id', sa.Integer, sa.ForeignKey('coupons.id'), nullable=False),
        sa.Column('activated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('student_id', 'term_id', name='uq_activation_student_term'),
    )

    # -----------------------------------------------------------------
    # notifications  (depends on users, schools)
    # -----------------------------------------------------------------
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('sender_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('school_id', sa.Integer, sa.ForeignKey('schools.id'), nullable=True),
        sa.Column('recipient_type', sa.String(20), nullable=False),
        sa.Column('recipient_role', sa.String(20), nullable=True),
        sa.Column('recipient_id', sa.Integer, sa.ForeignKey('users.id'), nullable=True),
        sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('is_read', sa.Boolean, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('notifications')
    op.drop_table('coupon_activations')
    op.drop_index('ix_coupons_code', table_name='coupons')
    op.drop_table('coupons')
    op.drop_table('scores')
    op.drop_table('subject_allocations')
    op.drop_table('subjects')
    op.drop_index('ix_students_admission_number', table_name='students')
    op.drop_table('students')
    op.drop_table('classes')
    op.drop_table('teachers')
    op.drop_table('terms')
    op.drop_table('academic_sessions')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')
    op.drop_table('schools')
