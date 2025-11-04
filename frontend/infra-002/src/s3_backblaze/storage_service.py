import io
import logging
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import boto3
import botocore
from botocore.client import Config as BotoConfig
from boto3.s3.transfer import TransferConfig

logger = logging.getLogger(__name__)


@dataclass
class StorageInitOptions:
    bucket_name: str
    region_name: Optional[str] = None
    endpoint_url: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    session_token: Optional[str] = None
    use_ssl: bool = True
    verify_ssl: bool = True
    signature_version: str = "s3v4"
    addressing_style: str = "virtual"  # or "path"


class StorageService:
    def __init__(self, opts: StorageInitOptions) -> None:
        self.bucket_name = opts.bucket_name
        session = boto3.session.Session(
            aws_access_key_id=opts.access_key or os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=opts.secret_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=opts.session_token or os.getenv("AWS_SESSION_TOKEN"),
            region_name=opts.region_name or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        )

        config = BotoConfig(
            s3={"addressing_style": opts.addressing_style},
            signature_version=opts.signature_version,
            retries={"max_attempts": 10, "mode": "standard"},
        )

        self._client = session.client(
            "s3",
            endpoint_url=opts.endpoint_url or os.getenv("S3_ENDPOINT_URL"),
            use_ssl=opts.use_ssl,
            verify=opts.verify_ssl,
            config=config,
        )

        self._resource = session.resource(
            "s3",
            endpoint_url=opts.endpoint_url or os.getenv("S3_ENDPOINT_URL"),
            use_ssl=opts.use_ssl,
            verify=opts.verify_ssl,
            config=config,
        )

        # Transfer configuration for multipart uploads
        self._transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,  # 8MB threshold
            multipart_chunksize=8 * 1024 * 1024,  # 8MB parts
            max_concurrency=10,
            use_threads=True,
        )

    @property
    def client(self):
        return self._client

    @property
    def resource(self):
        return self._resource

    def ensure_bucket(self, create_if_missing: bool = False, acl: Optional[str] = None) -> bool:
        try:
            self._client.head_bucket(Bucket=self.bucket_name)
            return True
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchBucket"):
                if not create_if_missing:
                    return False
                self.create_bucket(acl=acl)
                return True
            if code in ("403",):
                raise PermissionError(f"Access denied to bucket {self.bucket_name}")
            raise

    def create_bucket(self, acl: Optional[str] = None) -> None:
        params = {"Bucket": self.bucket_name}
        if acl:
            params["ACL"] = acl
        # us-east-1 requires no LocationConstraint, others do.
        region = self._client.meta.region_name
        if region and region != "us-east-1":
            params["CreateBucketConfiguration"] = {"LocationConstraint": region}
        self._client.create_bucket(**params)

    def set_bucket_versioning(self, enabled: bool) -> None:
        status = "Enabled" if enabled else "Suspended"
        self._client.put_bucket_versioning(
            Bucket=self.bucket_name,
            VersioningConfiguration={"Status": status}
        )

    def upload_file(
        self,
        file_path: str,
        key: str,
        content_type: Optional[str] = None,
        acl: Optional[str] = None,
        storage_class: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        extra_args: Optional[Dict[str, str]] = None,
    ) -> Dict:
        args: Dict[str, str] = extra_args.copy() if extra_args else {}
        if content_type:
            args["ContentType"] = content_type
        if acl:
            args["ACL"] = acl
        if storage_class:
            args["StorageClass"] = storage_class
        if metadata:
            args["Metadata"] = metadata
        return self.resource.Bucket(self.bucket_name).upload_file(
            file_path,
            key,
            ExtraArgs=args if args else None,
            Config=self._transfer_config,
        )

    def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: Optional[str] = None,
        acl: Optional[str] = None,
        storage_class: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        extra_args: Optional[Dict[str, str]] = None,
    ) -> Dict:
        args: Dict[str, str] = extra_args.copy() if extra_args else {}
        if content_type:
            args["ContentType"] = content_type
        if acl:
            args["ACL"] = acl
        if storage_class:
            args["StorageClass"] = storage_class
        if metadata:
            args["Metadata"] = metadata
        fileobj = io.BytesIO(data)
        return self._client.upload_fileobj(
            fileobj,
            self.bucket_name,
            key,
            ExtraArgs=args if args else None,
            Config=self._transfer_config,
        )

    def download_file(self, key: str, dest_path: str) -> None:
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        self.resource.Bucket(self.bucket_name).download_file(key, dest_path, Config=self._transfer_config)

    def download_bytes(self, key: str, byte_range: Optional[Tuple[int, int]] = None) -> bytes:
        params: Dict[str, str] = {"Bucket": self.bucket_name, "Key": key}
        if byte_range is not None:
            start, end = byte_range
            params["Range"] = f"bytes={start}-{end}"
        resp = self._client.get_object(**params)
        return resp["Body"].read()

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket_name, Key=key)

    def list_objects(self, prefix: Optional[str] = None, max_keys: int = 1000) -> List[Dict]:
        paginator = self._client.get_paginator("list_objects_v2")
        page_iter = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix or "", PaginationConfig={"PageSize": max_keys})
        results: List[Dict] = []
        for page in page_iter:
            results.extend(page.get("Contents", []))
        return results

    def generate_presigned_url_get(
        self,
        key: str,
        expires_in: int = 3600,
        response_content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None,
    ) -> str:
        params: Dict[str, str] = {"Bucket": self.bucket_name, "Key": key}
        if response_content_type:
            params["ResponseContentType"] = response_content_type
        if response_content_disposition:
            params["ResponseContentDisposition"] = response_content_disposition
        return self._client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def generate_presigned_url_put(
        self,
        key: str,
        expires_in: int = 3600,
        content_type: Optional[str] = None,
        acl: Optional[str] = None,
    ) -> str:
        params: Dict[str, str] = {"Bucket": self.bucket_name, "Key": key}
        if content_type:
            params["ContentType"] = content_type
        if acl:
            params["ACL"] = acl
        return self._client.generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def generate_presigned_post(
        self,
        key: str,
        expires_in: int = 3600,
        fields: Optional[Dict[str, str]] = None,
        conditions: Optional[List] = None,
    ) -> Dict[str, str]:
        return self._client.generate_presigned_post(
            Bucket=self.bucket_name,
            Key=key,
            Fields=fields or {},
            Conditions=conditions or [],
            ExpiresIn=expires_in,
        )

    # Manual multipart operations (if you need granular control beyond TransferManager)
    def create_multipart_upload(
        self,
        key: str,
        content_type: Optional[str] = None,
        acl: Optional[str] = None,
        storage_class: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        args: Dict[str, str] = {}
        if content_type:
            args["ContentType"] = content_type
        if acl:
            args["ACL"] = acl
        if storage_class:
            args["StorageClass"] = storage_class
        if metadata:
            args["Metadata"] = metadata
        resp = self._client.create_multipart_upload(Bucket=self.bucket_name, Key=key, **({} if not args else args))
        return resp["UploadId"]

    def upload_part(self, key: str, upload_id: str, part_number: int, data: bytes) -> Dict:
        resp = self._client.upload_part(
            Bucket=self.bucket_name,
            Key=key,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=data,
        )
        return {"ETag": resp["ETag"], "PartNumber": part_number}

    def complete_multipart_upload(self, key: str, upload_id: str, parts: Iterable[Dict]) -> Dict:
        return self._client.complete_multipart_upload(
            Bucket=self.bucket_name,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": list(parts)},
        )

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        self._client.abort_multipart_upload(Bucket=self.bucket_name, Key=key, UploadId=upload_id)

