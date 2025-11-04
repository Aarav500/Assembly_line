import os


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'change-me-admin')
    DEFAULT_QUOTA_DEV = int(os.getenv('DEFAULT_QUOTA_DEV', '5'))
    DEFAULT_QUOTA_STAGE = int(os.getenv('DEFAULT_QUOTA_STAGE', '3'))
    DEFAULT_QUOTA_PROD = int(os.getenv('DEFAULT_QUOTA_PROD', '1'))
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:////data/app.db')

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PROVISION_DELAY_SECONDS = float(os.getenv('PROVISION_DELAY_SECONDS', '1.0'))
    DEPROVISION_DELAY_SECONDS = float(os.getenv('DEPROVISION_DELAY_SECONDS', '0.5'))

