try:
    from psycopg2cffi import compat
    compat.register()
except ImportError:
    pass
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

from config import get_config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object(config_class or get_config())

    # --- extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # --- blueprints ---
    from app.routes.auth import auth_bp
    from app.routes.platform import platform_bp
    from app.routes.superadmin import superadmin_bp
    from app.routes.admin import admin_bp
    from app.routes.cashier import cashier_bp
    from app.routes.teacher import teacher_bp
    from app.routes.student import student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(platform_bp, url_prefix='/platform')
    app.register_blueprint(superadmin_bp, url_prefix='/superadmin')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(cashier_bp, url_prefix='/cashier')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(student_bp, url_prefix='/student')

    # make upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # --- shared template context ---
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        school_settings = None
        if current_user.is_authenticated and current_user.role != 'PlatformAdmin':
            # 'school' is the backref defined on User.school_id -> School
            school_settings = current_user.school
        return dict(
            current_user_role=getattr(current_user, 'role', None),
            school_settings=school_settings,
        )

    return app
