import os
from pathlib import Path


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Database
    DEFAULT_DB_PATH = Path(os.environ.get('DB_PATH') or (Path.cwd() / 'instance' / 'todo_backlog.db'))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{DEFAULT_DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Scanning
    SCAN_ROOT = os.environ.get('SCAN_ROOT', str(Path.cwd()))
    MAX_FILE_SIZE_BYTES = int(os.environ.get('MAX_FILE_SIZE_BYTES', 2 * 1024 * 1024))  # 2MB

    # Comma-separated lists env overrides
    EXCLUDE_DIRS = set((os.environ.get('EXCLUDE_DIRS') or '.git,.hg,.svn,node_modules,venv,.venv,__pycache__,dist,build,.idea,.vscode,.tox,.mypy_cache').split(','))
    INCLUDE_EXTS = set((os.environ.get('INCLUDE_EXTS') or 'py,js,ts,tsx,jsx,java,kt,swift,c,cc,cpp,cxx,h,hpp,cs,go,rs,php,rb,sh,bash,ps1,cmd,bat,html,xml,svg,vue,sql,yaml,yml,toml,ini,cfg,conf,md,txt').split(','))

    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

