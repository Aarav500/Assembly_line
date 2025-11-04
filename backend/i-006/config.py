import os
from dataclasses import dataclass


@dataclass
class Config:
    DATABASE_URL: str = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    AWS_KMS_KEY_ID: str | None = os.environ.get('AWS_KMS_KEY_ID')
    LOCAL_KMS_MASTER_KEY_B64: str | None = os.environ.get('LOCAL_KMS_MASTER_KEY_B64')
    LOCAL_KMS_MASTER_KEY_PATH: str = os.environ.get('LOCAL_KMS_MASTER_KEY_PATH', 'local_kms_master.key')
    AUDIT_LOG_PATH: str = os.environ.get('AUDIT_LOG_PATH', 'audit.log')

