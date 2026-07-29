import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """Base configuration shared by all environments."""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        # Only acceptable in local dev. Production MUST set SECRET_KEY in .env
        SECRET_KEY = 'dev-only-insecure-key-replace-in-env'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload constraints
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max upload (logos, signatures, stamps)
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}

    # Coupon defaults
    COUPON_DEFAULT_LENGTH = 8
    COUPON_CHARSET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # excludes ambiguous chars (0,O,1,I)


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'grpms_dev.sqlite')


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "DATABASE_URL must be set in production. "
            "Refusing to start with a default/insecure database."
        )


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}


def get_config():
    env = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)
