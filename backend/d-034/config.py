import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///instance/app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTH_TOKEN = os.getenv('AUTH_TOKEN', 'changeme')
    TRIGGER_WINDOW_MINUTES = int(os.getenv('TRIGGER_WINDOW_MINUTES', '10'))

