import boto3
from botocore.exceptions import ClientError
from typing import Any, Dict
from .base import BaseConnector


class S3Connector(BaseConnector):
    slug = "s3"
    name = "AWS S3"

    def _check_enabled(self) -> bool:
        return bool(self.config.get("AWS_ACCESS_KEY_ID") and self.config.get("AWS_SECRET_ACCESS_KEY") and self.config.get("AWS_REGION") and self.config.get("S3_BUCKET"))

    def _client(self):
        return boto3.client(
            "s3",
            region_name=self.config.get("AWS_REGION"),
            aws_access_key_id=self.config.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=self.config.get("AWS_SECRET_ACCESS_KEY"),
        )

    def health(self) -> Dict[str, Any]:
        try:
            c = self._client()
            # List first object to validate permissions
            c.list_objects_v2(Bucket=self.config.get("S3_BUCKET"), MaxKeys=1)
            return {"ok": True}
        except ClientError as e:
            return {"ok": False, "error": str(e)}

    def op_list_objects(self, prefix: str = "", max_keys: int = 100):
        c = self._client()
        res = c.list_objects_v2(Bucket=self.config.get("S3_BUCKET"), Prefix=prefix, MaxKeys=max_keys)
        return {
            "key_count": res.get("KeyCount", 0),
            "objects": [
                {
                    "key": o.get("Key"),
                    "size": o.get("Size"),
                    "last_modified": o.get("LastModified").isoformat() if o.get("LastModified") else None,
                    "etag": o.get("ETag"),
                }
                for o in res.get("Contents", [])
            ],
            "is_truncated": res.get("IsTruncated", False),
            "next_continuation_token": res.get("NextContinuationToken"),
        }

    def op_get_object(self, key: str, as_presigned_url: bool = True, expires_in: int = 3600):
        c = self._client()
        bucket = self.config.get("S3_BUCKET")
        if as_presigned_url:
            url = c.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return {"presigned_url": url, "expires_in": expires_in}
        else:
            obj = c.get_object(Bucket=bucket, Key=key)
            data = obj["Body"].read()
            return {"key": key, "content_length": len(data), "data_base64": data.decode("latin1")}

