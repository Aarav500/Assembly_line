import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class S3Config:
    bucket_name: str
    region_name: Optional[str] = None
    endpoint_url: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    session_token: Optional[str] = None
    use_ssl: bool = True
    addressing_style: str = "virtual"  # or "path"
    signature_version: str = "s3v4"
    verify_ssl: bool = True

    @staticmethod
    def from_env() -> "S3Config":
        return S3Config(
            bucket_name=os.getenv("BUCKET_NAME", ""),
            region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            access_key=os.getenv("AWS_ACCESS_KEY_ID"),
            secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            session_token=os.getenv("AWS_SESSION_TOKEN"),
            use_ssl=os.getenv("S3_USE_SSL", "true").lower() not in {"0", "false", "no"},
            addressing_style=os.getenv("S3_ADDRESSING_STYLE", "virtual"),
            signature_version=os.getenv("S3_SIGNATURE_VERSION", "s3v4"),
            verify_ssl=os.getenv("S3_VERIFY_SSL", "true").lower() not in {"0", "false", "no"},
        )

    def ensure_valid(self):
        if not self.bucket_name:
            raise ValueError("BUCKET_NAME is required. Set in env or pass explicitly.")

