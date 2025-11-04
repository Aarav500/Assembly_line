import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional

from itsdangerous import URLSafeTimedSerializer


def safe_filename(name: str) -> str:
    name = name.strip().replace("\x00", "")
    # Split extension
    if "." in name:
        base, ext = name.rsplit(".", 1)
        ext = "." + re.sub(r"[^A-Za-z0-9]+", "", ext)
    else:
        base, ext = name, ""
    base = base.lower()
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-._")
    if not base:
        base = uuid.uuid4().hex
    return (base + ext)[:255]


class S3Storage:
    def __init__(
        self,
        bucket: str,
        region: str,
        upload_expires: int,
        download_expires: int,
        max_file_size: int,
        allowed_mime_prefixes,
        acl: str = "private",
    ):
        import boto3  # import here to avoid requirement for local backend

        self.bucket = bucket
        self.region = region
        self.upload_expires = upload_expires
        self.download_expires = download_expires
        self.max_file_size = max_file_size
        self.allowed_mime_prefixes = allowed_mime_prefixes or []
        self.acl = acl
        self._s3 = boto3.client("s3", region_name=self.region)

    def create_key(self, filename: str, prefix: str = "uploads/") -> str:
        now = datetime.utcnow()
        day_path = now.strftime("%Y/%m/%d")
        fname = safe_filename(filename)
        uid = uuid.uuid4().hex
        key = f"{prefix.rstrip('/')}/{day_path}/{uid}-{fname}"
        return key

    def _validate_mime(self, content_type: str):
        if not self.allowed_mime_prefixes:
            return True
        return any(content_type.startswith(pref) for pref in self.allowed_mime_prefixes)

    def create_upload_url(
        self,
        key: str,
        content_type: str,
        content_length: int,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict:
        if not self._validate_mime(content_type):
            raise ValueError("Disallowed content type")

        # Use presigned POST with strict conditions
        fields = {
            "acl": self.acl,
            "Content-Type": content_type,
            "key": key,
        }
        conditions = [
            {"acl": self.acl},
            ["eq", "$Content-Type", content_type],
            ["eq", "$key", key],
            ["content-length-range", 1, min(content_length, self.max_file_size)],
        ]

        if metadata:
            for mk, mv in metadata.items():
                sk = f"x-amz-meta-{mk}"
                fields[sk] = str(mv)
                conditions.append(["eq", f"${sk}", str(mv)])

        presigned = self._s3.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=self.upload_expires,
        )

        return {
            "type": "s3-post",
            "method": "POST",
            "url": presigned["url"],
            "fields": presigned["fields"],
            "expires_in": self.upload_expires,
        }

    def create_download_url(
        self,
        key: str,
        response_content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
    ) -> Tuple[str, int]:
        params = {"Bucket": self.bucket, "Key": key}
        if response_content_type:
            params["ResponseContentType"] = response_content_type
        if response_content_disposition:
            params["ResponseContentDisposition"] = response_content_disposition

        url = self._s3.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=self.download_expires,
        )
        return url, self.download_expires


class LocalStorage:
    def __init__(
        self,
        base_dir: os.PathLike,
        signer: URLSafeTimedSerializer,
        upload_expires: int,
        download_expires: int,
        max_file_size: int,
        allowed_mime_prefixes,
    ):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.signer = signer
        self.upload_expires = upload_expires
        self.download_expires = download_expires
        self.max_file_size = max_file_size
        self.allowed_mime_prefixes = allowed_mime_prefixes or []

    def create_key(self, filename: str, prefix: str = "uploads/") -> str:
        now = datetime.utcnow()
        day_path = now.strftime("%Y/%m/%d")
        fname = safe_filename(filename)
        uid = uuid.uuid4().hex
        key = f"{prefix.rstrip('/')}/{day_path}/{uid}-{fname}"
        return key

    def _validate_mime(self, content_type: str):
        if not self.allowed_mime_prefixes:
            return True
        return any(content_type.startswith(pref) for pref in self.allowed_mime_prefixes)

    def token(self, data: Dict, expires: int) -> str:
        return self.signer.dumps(data)

    def verify_token(self, token: str, scope: str):
        data = self.signer.loads(token, max_age=(self.upload_expires if scope == "upload" else self.download_expires))
        if data.get("scope") != scope:
            raise ValueError("Invalid scope")
        return data

    def path_for_key(self, key: str) -> Path:
        path = (self.base_dir / key).resolve()
        # Ensure path is within base_dir
        if not str(path).startswith(str(self.base_dir)):
            raise ValueError("Invalid key path")
        return path

    def create_upload_url(
        self,
        key: str,
        content_type: str,
        content_length: int,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict:
        if content_length > self.max_file_size:
            raise ValueError("File too large")
        if not self._validate_mime(content_type):
            raise ValueError("Disallowed content type")

        payload = {
            "scope": "upload",
            "key": key,
            "content_type": content_type,
            "content_length": content_length,
        }
        tok = self.token(payload, self.upload_expires)
        url = f"/_local/upload?token={tok}"
        return {
            "type": "local-put",
            "method": "PUT",
            "url": url,
            "headers": {"Content-Type": content_type},
            "expires_in": self.upload_expires,
        }

    def create_download_url(
        self,
        key: str,
        response_content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
    ) -> Tuple[str, int]:
        payload = {"scope": "download", "key": key}
        tok = self.token(payload, self.download_expires)
        params = [f"token={tok}"]
        if response_content_disposition:
            params.append(f"as_attachment=true")
        if response_content_type:
            # Browser will infer; skipping explicit content type for local
            pass
        url = f"/_local/download/{key}?" + "&".join(params)
        return url, self.download_expires

