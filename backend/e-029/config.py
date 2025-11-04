import os
from pathlib import Path


class AppConfig:
    ROOT_DIR = Path(__file__).parent.resolve()
    DATA_DIR = os.environ.get('APP_DATA_DIR', str(ROOT_DIR / 'data'))
    BACKUP_DIR = os.environ.get('APP_BACKUP_DIR', str(Path(DATA_DIR) / 'backups'))
    EVIDENCE_DIR = os.environ.get('APP_EVIDENCE_DIR', str(Path(DATA_DIR) / 'evidence'))
    DB_PATH = os.environ.get('APP_DB_PATH', str(Path(DATA_DIR) / 'app.db'))

    @staticmethod
    def default_policy():
        return {
            'retain_days': 30,
            'min_backups': 7,
            'max_backups': 100,
            'require_frequency_hours': 24,
            'backup_dir': AppConfig.BACKUP_DIR
        }

