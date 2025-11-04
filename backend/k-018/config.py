import os


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///audit.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    STORAGE_DIR = os.getenv('STORAGE_DIR', os.path.join(os.getcwd(), 'storage'))

    # SMTP configuration (optional)
    SMTP_HOST = os.getenv('SMTP_HOST')
    SMTP_PORT = os.getenv('SMTP_PORT', '587')
    SMTP_USER = os.getenv('SMTP_USER')
    SMTP_PASS = os.getenv('SMTP_PASS')
    SMTP_FROM = os.getenv('SMTP_FROM')

