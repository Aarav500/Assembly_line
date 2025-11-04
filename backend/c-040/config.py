import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 64 * 1024 * 1024))
    JOBS_DIR = os.environ.get('JOBS_DIR', os.path.join(os.getcwd(), 'instance', 'jobs'))
    MIN_OCCURRENCES = int(os.environ.get('MIN_OCCURRENCES', '2'))
    MIN_SNIPPET_LENGTH = int(os.environ.get('MIN_SNIPPET_LENGTH', '200'))
    MAX_COMPONENTS = int(os.environ.get('MAX_COMPONENTS', '20'))

