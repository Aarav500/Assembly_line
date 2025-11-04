import os
import json

class Settings:
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'

    DEFAULT_BASENAME = os.environ.get('DEFAULT_BASENAME', 'dataset')

    # Local
    LOCAL_EXPORT_DIR = os.environ.get('LOCAL_EXPORT_DIR', './exports')

    # AWS
    S3_BUCKET = os.environ.get('S3_BUCKET')
    S3_PREFIX = os.environ.get('S3_PREFIX', '')
    S3_REGION = os.environ.get('S3_REGION')
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_SESSION_TOKEN = os.environ.get('AWS_SESSION_TOKEN')

    # GCP
    GCS_BUCKET = os.environ.get('GCS_BUCKET')
    GCS_PREFIX = os.environ.get('GCS_PREFIX', '')
    GCP_PROJECT = os.environ.get('GCP_PROJECT')
    GCP_SERVICE_ACCOUNT_JSON = None
    _gcp_json_env = os.environ.get('GCP_SERVICE_ACCOUNT_JSON')
    if _gcp_json_env:
        try:
            GCP_SERVICE_ACCOUNT_JSON = json.loads(_gcp_json_env)
        except Exception:
            # Could be a path; leave as string
            GCP_SERVICE_ACCOUNT_JSON = _gcp_json_env

    # Azure
    AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    AZURE_STORAGE_ACCOUNT_NAME = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME')
    AZURE_STORAGE_ACCOUNT_KEY = os.environ.get('AZURE_STORAGE_ACCOUNT_KEY')
    AZURE_BLOB_CONTAINER = os.environ.get('AZURE_BLOB_CONTAINER')
    AZURE_BLOB_PREFIX = os.environ.get('AZURE_BLOB_PREFIX', '')

settings = Settings()

