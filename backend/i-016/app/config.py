import os

class Config:
    def __init__(self):
        # Default to instance/app.db inside project directory
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        instance_dir = os.path.join(base_dir, 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        default_db_path = 'sqlite:///' + os.path.join(instance_dir, 'app.db')
        self.SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', default_db_path)
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me')
        self.STORAGE_DIR = os.environ.get('STORAGE_DIR', os.path.join(base_dir, 'storage'))
        # Max upload size 200 MB by default
        self.MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 200 * 1024 * 1024))

