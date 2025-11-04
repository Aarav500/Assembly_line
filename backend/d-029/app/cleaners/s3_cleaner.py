import logging
from typing import List

import boto3
from botocore.exceptions import ClientError

from .base import BaseCleaner, CleanupResult

logger = logging.getLogger(__name__)


class S3Cleaner(BaseCleaner):
    def __init__(self, settings):
        super().__init__(settings, name="s3")
        self.bucket = settings.s3_bucket
        self.prefix_template = settings.s3_prefix_template
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client("s3")
        return self._client

    def _list_keys(self, bucket: str, prefix: str) -> List[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        page_iter = paginator.paginate(Bucket=bucket, Prefix=prefix)
        keys: List[str] = []
        for page in page_iter:
            contents = page.get("Contents", [])
            for obj in contents:
                keys.append(obj["Key"])
        return keys

    def _delete_batch(self, bucket: str, keys: List[str]) -> int:
        if not keys:
            return 0
        deleted = 0
        for i in range(0, len(keys), 1000):
            chunk = keys[i:i+1000]
            if self.dry_run:
                logger.info("[dry-run] Would delete %d S3 objects from s3://%s", len(chunk), bucket)
                deleted += len(chunk)
                continue
            try:
                resp = self.client.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
                )
                deleted += len(resp.get("Deleted", []))
            except ClientError as e:
                logger.warning("Failed deleting batch in bucket %s: %s", bucket, e)
        return deleted

    def cleanup(self, ctx: dict) -> CleanupResult:
        if not self.bucket:
            return {"name": self.name, "ok": True, "details": {"skipped": "No S3 bucket configured"}}

        prefix = self.settings.format_template(self.prefix_template, ctx)
        try:
            keys = self._list_keys(self.bucket, prefix)
            deleted = self._delete_batch(self.bucket, keys)
            return {
                "name": self.name,
                "ok": True,
                "details": {
                    "bucket": self.bucket,
                    "prefix": prefix,
                    "matched": len(keys),
                    "deleted": deleted,
                    "dry_run": self.dry_run,
                },
            }
        except ClientError as e:
            return {"name": self.name, "ok": False, "error": str(e)}

