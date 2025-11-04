import json
from typing import Optional, Any

from google.cloud import storage
from google.oauth2 import service_account

from .base import BaseConnector


def _credentials_from_any(creds_any: Any):
    if not creds_any:
        return None
    if isinstance(creds_any, dict):
        return service_account.Credentials.from_service_account_info(creds_any)
    if isinstance(creds_any, str):
        # Could be JSON string or file path
        s = creds_any.strip()
        if s.startswith('{'):
            data = json.loads(s)
            return service_account.Credentials.from_service_account_info(data)
        # Treat as path
        try:
            return service_account.Credentials.from_service_account_file(s)
        except Exception:
            # Fall back to None; client may use default
            return None
    return None


class GCSConnector(BaseConnector):
    def __init__(self, bucket: str, prefix: Optional[str] = None, project: Optional[str] = None, credentials: Optional[Any] = None):
        creds = _credentials_from_any(credentials)
        if creds is not None:
            self.client = storage.Client(project=project, credentials=creds)
        else:
            self.client = storage.Client(project=project)
        self.bucket_name = bucket
        self.prefix = (prefix or '').strip('/')

    def write(self, content: bytes, path: str, content_type: Optional[str] = None) -> str:
        bucket = self.client.bucket(self.bucket_name)
        blob_name = path.strip('/')
        if self.prefix:
            blob_name = f"{self.prefix}/{blob_name}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(content, content_type=content_type or 'application/octet-stream')
        return f"gs://{self.bucket_name}/{blob_name}"

