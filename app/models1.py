from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# SCHOOL  (platform-level — one row per institution)
# ---------------------------------------------------------------------------
class School(db.Model):
    __tablename__ = 'schools'
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(255), nullable=False)
    motto          = db.Column(db.String(255), default='')
    principal_name = db.Column(db.String(100), default='Principal')
    logo_path      = db.Column(db.String(255), nullable=True)
    signature_path = db.Column(db.String(255), nullable=True)
    stamp_path     = db.Column(db.String(255), nullable=True)
    is_active      = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    code           = db.Column(db.String(6), nullable=True)
    # relationships
    users    = db.relationship('User',            backref='school', lazy='dynamic')
    sessions = db.relationship('AcademicSession', backref='school', lazy='dynamic')
    classes  = db.relationship('Class',           backref='school', lazy='dynamic')
    subjects = db.relationship('Subject',         backref='school', lazy='dynamic')
    coupons  = db.relationship('Coupon',          backref='school', lazy='dynamic')

    def __repr__(self):
        return f'<School {self.name}>'

    @property
    def active_session(self):
        return self.sessions.filter_by(is_active=True).first()

    @property
    def active_term(self):
        session = self.active_session
        if not session:
            return None
        return Term.query.filter_by(session_id=session.id, is_active=True).first()


# ---------------------------------------------------------------------------
# USER  (login account for every role)
# ---------------------------------------------------------------------------
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    ROLES = ('PlatformAdmin', 'SuperAdmin', 'Admin',
             'Cashier', 'FormMaster', 'Teacher', 'Student')

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), nullable=False)
    # NULL only for PlatformAdmin
    school_id     = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # profiles
    student_profile = db.relationship('Student', backref='user', uselist=False, lazy=True)
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False, lazy=True)

    # notifications sent by this user
    sent_notifications = db.relationship(
        'Notification', foreign_keys='Notification.sender_id',
        backref='sender', lazy='dynamic'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_platform_admin(self):
        return self.role == 'PlatformAdmin'

    @property
    def display_name(self):
        if self.teacher_profile:
            return f'{self.teacher_profile.title} {self.teacher_profile.full_name}'.strip()
        if self.student_profile:
            return f'{self.student_profile.first_name} {self.student_profile.last_name}'
        return self.username

    def __repr__(self):
        return f'<User {self.username} [{self.role}]>'


# ---------------------------------------------------------------------------
# STUDENT
# ---------------------------------------------------------------------------
class Student(db.Model):
    __tablename__ = 'students'
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    school_id        = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    admission_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    first_name       = db.Column(db.String(64), nullable=False)
    last_name        = db.Column(db.String(64), nullable=False)

    # class tracking
    current_class_id  = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)
    previous_class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)

    # archive / alumni
    is_active    = db.Column(db.Boolean, default=True)
    archive_type = db.Column(db.String(20), default='none')  # none | archived | alumni
    archive_date = db.Column(db.DateTime, nullable=True)

    # transcript coupon — assigned once by Platform Admin, permanent lifetime access key.
    # NULL means not yet assigned. Once set: admin can view transcript freely but
    # downloading requires entering this code. Students also need it to access transcripts.
    # Never expires, never regenerates, never transferred to another student.
    transcript_coupon = db.Column(db.String(20), unique=True, nullable=True, index=True)

    scores             = db.relationship('Score',             backref='student', lazy='dynamic')
    coupon_activations = db.relationship('CouponActivation',  backref='student', lazy='dynamic')

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def has_activated_coupon(self, term_id):
        """Return True if student has already activated a coupon for this term."""
        return CouponActivation.query.filter_by(
            student_id=self.id, term_id=term_id
        ).first() is not None

    def __repr__(self):
        return f'<Student {self.admission_number}>'


# ---------------------------------------------------------------------------
# TEACHER  (profile for Teacher and FormMaster roles only — subject/class
# assignments live here. Admin/Cashier/SuperAdmin do NOT get a Teacher row;
# their identity lives entirely on the User model.)
# ---------------------------------------------------------------------------
class Teacher(db.Model):
    __tablename__ = 'teachers'
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    title     = db.Column(db.String(20), default='')
    full_name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    allocations  = db.relationship('SubjectAllocation', backref='teacher', lazy='dynamic')
    form_classes = db.relationship('Class', backref='form_master',
                                   foreign_keys='Class.form_master_id', lazy='dynamic')

    def __repr__(self):
        return f'<Teacher {self.full_name}>'


# ---------------------------------------------------------------------------
# ACADEMIC SESSION
# ---------------------------------------------------------------------------
class AcademicSession(db.Model):
    __tablename__ = 'academic_sessions'
    id           = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(20), nullable=False)   # e.g. 2025/2026
    school_id    = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    is_active    = db.Column(db.Boolean, default=False)

    terms = db.relationship('Term', backref='session', lazy=True,
                            cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('session_name', 'school_id', name='uq_session_school'),
    )

    def __repr__(self):
        return f'<Session {self.session_name}>'


# ---------------------------------------------------------------------------
# TERM
# ---------------------------------------------------------------------------
class Term(db.Model):
    __tablename__ = 'terms'
    id         = db.Column(db.Integer, primary_key=True)
    term_name  = db.Column(db.String(20), nullable=False)   # First Term | Second Term | Third Term
    session_id = db.Column(db.Integer, db.ForeignKey('academic_sessions.id'), nullable=False)
    is_active  = db.Column(db.Boolean, default=False)

    coupons = db.relationship('Coupon', backref='term', lazy='dynamic')
    scores  = db.relationship('Score',  backref='term', lazy='dynamic')

    def __repr__(self):
        return f'<Term {self.term_name}>'


# ---------------------------------------------------------------------------
# CLASS
# ---------------------------------------------------------------------------
class Class(db.Model):
    __tablename__ = 'classes'
    id        = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    class_name = db.Column(db.String(64), nullable=False)
    section    = db.Column(db.String(64), default='')   # Nursery | Primary | Secondary

    form_master_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)

    # automated report-card remarks by grade band
    remark_a = db.Column(db.String(255), default='Excellent performance. Keep it up!')
    remark_b = db.Column(db.String(255), default='Very good result. A commendable effort.')
    remark_c = db.Column(db.String(255), default='Good effort, but there is room for improvement.')
    remark_d = db.Column(db.String(255), default='A fair result. You must work harder next term.')
    remark_f = db.Column(db.String(255), default='Poor performance. Serious improvement is needed.')

    # current students in this class
    students    = db.relationship('Student',
                                  foreign_keys='Student.current_class_id',
                                  backref='student_class', lazy='dynamic')
    allocations = db.relationship('SubjectAllocation', backref='assigned_class', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('class_name', 'school_id', name='uq_class_school'),
    )

    def __repr__(self):
        return f'<Class {self.class_name}>'


# ---------------------------------------------------------------------------
# SUBJECT
# ---------------------------------------------------------------------------
class Subject(db.Model):
    __tablename__ = 'subjects'

    SECTIONS = (
        'All Sections',
        'Nursery',
        'Primary',
        'Junior Secondary',
        'Senior Secondary',
    )

    id           = db.Column(db.Integer, primary_key=True)
    school_id    = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    subject_name = db.Column(db.String(64), nullable=False)
    subject_code = db.Column(db.String(10), nullable=False)
    section      = db.Column(db.String(30), default='All Sections', nullable=False)

    allocations = db.relationship('SubjectAllocation', backref='subject', lazy='dynamic')
    scores      = db.relationship('Score',             backref='subject', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('subject_code', 'school_id', name='uq_subject_code_school'),
    )

    def __repr__(self):
        return f'<Subject {self.subject_code}>'


# ---------------------------------------------------------------------------
# SUBJECT ALLOCATION  (teacher → subject → class)
# ---------------------------------------------------------------------------
class SubjectAllocation(db.Model):
    __tablename__ = 'subject_allocations'
    id         = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id   = db.Column(db.Integer, db.ForeignKey('classes.id'),  nullable=False)

    __table_args__ = (
        db.UniqueConstraint('subject_id', 'class_id', name='uq_subject_class'),
    )


# ---------------------------------------------------------------------------
# SCORE
# ---------------------------------------------------------------------------
class Score(db.Model):
    __tablename__ = 'scores'
    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    term_id    = db.Column(db.Integer, db.ForeignKey('terms.id'),    nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('academic_sessions.id'), nullable=False)

    # mark breakdown
    ca_1     = db.Column(db.Float, default=0.0)
    ca_2     = db.Column(db.Float, default=0.0)
    assign_1 = db.Column(db.Float, default=0.0)
    assign_2 = db.Column(db.Float, default=0.0)
    exam     = db.Column(db.Float, default=0.0)

    # computed
    total_score = db.Column(db.Float, default=0.0)
    grade       = db.Column(db.String(2))
    remark      = db.Column(db.String(50))

    is_released  = db.Column(db.Boolean, default=False)
    date_entered = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('AcademicSession', backref='scores', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'subject_id', 'term_id', 'session_id',
                            name='uq_score_record'),
    )


# ---------------------------------------------------------------------------
# COUPON
# ---------------------------------------------------------------------------
class Coupon(db.Model):
    __tablename__ = 'coupons'
    id        = db.Column(db.Integer, primary_key=True)
    code      = db.Column(db.String(30), unique=True, nullable=False, index=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    term_id   = db.Column(db.Integer, db.ForeignKey('terms.id'),   nullable=False)

    # set when redeemed
    is_used    = db.Column(db.Boolean, default=False)
    used_by_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    used_at    = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationships
    used_by    = db.relationship('Student', backref='used_coupons', lazy=True)
    activation = db.relationship('CouponActivation', backref='coupon',
                                 uselist=False, lazy=True)

    def __repr__(self):
        return f'<Coupon {self.code} used={self.is_used}>'

    def is_valid_for_redemption(self, school_id, current_term_id):
        """
        A coupon is redeemable only if:
          - it belongs to the school attempting to use it
          - it belongs to the CURRENTLY active term for that school
          - it has not already been used
        No 'expired' flag needed — once the term changes, old unused
        coupons simply stop matching the active term and become dead.
        """
        return (
            self.school_id == school_id
            and self.term_id == current_term_id
            and not self.is_used
        )

    @staticmethod
    def register_query(school_id=None, term_id=None, status='all', search=''):
        """
        Shared query builder for the Coupon Register, used by both the
        Platform Admin (all schools) and SuperAdmin (own school, read-only).

        status: 'all' | 'used' | 'unused'
        search: partial code match, case-insensitive
        """
        query = Coupon.query
        if school_id is not None:
            query = query.filter(Coupon.school_id == school_id)
        if term_id is not None:
            query = query.filter(Coupon.term_id == term_id)
        if status == 'used':
            query = query.filter(Coupon.is_used.is_(True))
        elif status == 'unused':
            query = query.filter(Coupon.is_used.is_(False))
        if search:
            query = query.filter(Coupon.code.ilike(f'%{search.strip()}%'))
        return query.order_by(Coupon.created_at.desc())


# ---------------------------------------------------------------------------
# COUPON ACTIVATION  (the lock record — written at redemption time)
# ---------------------------------------------------------------------------
class CouponActivation(db.Model):
    __tablename__ = 'coupon_activations'
    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    term_id    = db.Column(db.Integer, db.ForeignKey('terms.id'),    nullable=False)
    coupon_id  = db.Column(db.Integer, db.ForeignKey('coupons.id'),  nullable=False)
    activated_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        # one activation per student per term
        db.UniqueConstraint('student_id', 'term_id', name='uq_activation_student_term'),
    )


# ---------------------------------------------------------------------------
# NOTIFICATION
# ---------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = 'notifications'

    # recipient_type values:
    #   'broadcast'  — all users in a school (or platform-wide if school_id is None)
    #   'role'       — all users of a given role in a school
    #   'user'       — a specific user
    RECIPIENT_TYPES = ('broadcast', 'role', 'user')

    id             = db.Column(db.Integer, primary_key=True)
    sender_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    school_id      = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)

    recipient_type = db.Column(db.String(20), nullable=False)   # broadcast | role | user
    recipient_role = db.Column(db.String(20), nullable=True)    # e.g. 'Teacher', if type=role
    recipient_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # if type=user

    subject    = db.Column(db.String(200), nullable=False)
    body       = db.Column(db.Text, nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recipient = db.relationship('User', foreign_keys=[recipient_id],
                                backref='received_notifications', lazy=True)
    school    = db.relationship('School', backref='notifications', lazy=True)

    def __repr__(self):
        return f'<Notification "{self.subject}" from user {self.sender_id}>'
