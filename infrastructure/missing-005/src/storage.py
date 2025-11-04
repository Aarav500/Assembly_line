import io
import mimetypes
import posixpath
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from .config import config


class S3Storage:
    def __init__(self):
        session = boto3.session.Session()
        self.client = session.client(
            "s3",
            region_name=config.S3_REGION,
            endpoint_url=config.S3_ENDPOINT_URL,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            aws_session_token=config.AWS_SESSION_TOKEN,
            config=BotoConfig(
                s3={"addressing_style": "path" if config.S3_FORCE_PATH_STYLE else "virtual"},
                signature_version=config.S3_SIGNATURE_VERSION,
            ),
        )
        self.bucket = config.S3_BUCKET
        self.cdn_base_url = config.CDN_BASE_URL.rstrip("/") if config.CDN_BASE_URL else None
        self.endpoint_url = config.S3_ENDPOINT_URL.rstrip("/") if config.S3_ENDPOINT_URL else None
        self.region = config.S3_REGION

    @staticmethod
    def _safe_join(base: str, *paths: str) -> str:
        base = base.rstrip("/")
        tail = posixpath.join(*[p.strip("/") for p in paths if p])
        return f"{base}/{tail}" if tail else base

    @staticmethod
    def _ext_from_filename(filename: str | None) -> str:
        if not filename or "." not in filename:
            return ""
        return "." + filename.rsplit(".", 1)[1].lower()

    def generate_key(self, filename: Optional[str] = None, prefix: Optional[str] = None) -> str:
        now = datetime.utcnow()
        date_path = now.strftime("%Y/%m/%d")
        ext = self._ext_from_filename(filename)
        uid = uuid.uuid4().hex
        prefix_final = prefix if prefix is not None else config.DEFAULT_PREFIX
        key = self._safe_join(prefix_final or "", date_path, f"{uid}{ext}")
        return key

    def guess_content_type(self, filename: Optional[str], default: str = "application/octet-stream") -> str:
        if filename:
            ctype, _ = mimetypes.guess_type(filename)
            if ctype:
                return ctype
        return default

    def create_presigned_post(
        self,
        key: str,
        content_type: Optional[str] = None,
        public: bool = False,
        expires_in: int = config.PRESIGN_EXPIRES,
        max_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        conditions = []
        fields: Dict[str, Any] = {"key": key}
        if content_type:
            conditions.append(["starts-with", "$Content-Type", content_type.split("/")[0]])
            fields["Content-Type"] = content_type
        if public:
            fields["acl"] = "public-read"
            conditions.append({"acl": "public-read"})
        if max_size:
            conditions.append(["content-length-range", 1, max_size])

        post = self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=expires_in,
        )
        return post

    def create_presigned_get(self, key: str, expires_in: int = config.PRESIGN_EXPIRES, response_content_type: Optional[str] = None) -> str:
        params: Dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if response_content_type:
            params["ResponseContentType"] = response_content_type
        url = self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)
        return url

    def upload_bytes(self, data: bytes, key: str, content_type: Optional[str] = None, public: bool = False, cache_control: Optional[str] = None) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        if public:
            extra["ACL"] = "public-read"
        if cache_control:
            extra["CacheControl"] = cache_control
        self.client.put_object(Bucket=self.bucket, Key=key, Body=io.BytesIO(data), **extra)
        return {"key": key, "url": self.object_url(key, public=public)}

    def object_url(self, key: str, public: bool = False) -> str:
        if self.cdn_base_url and public:
            return self._safe_join(self.cdn_base_url, key)
        # Fallback public URL if bucket is public
        if self.endpoint_url:
            if config.S3_FORCE_PATH_STYLE:
                return self._safe_join(self.endpoint_url, self.bucket, key)
            else:
                # virtual-hosted-style
                base = self.endpoint_url.replace("https://", f"https://{self.bucket}.") if self.endpoint_url.startswith("https://") else self.endpoint_url.replace("http://", f"http://{self.bucket}.")
                return self._safe_join(base, key)
        # AWS default
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self.client.head_object(Bucket=self.bucket, Key=key)
            return resp
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                return None
            raise


storage = S3Storage()

