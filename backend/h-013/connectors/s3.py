from typing import Optional

import boto3

from .base import BaseConnector


class S3Connector(BaseConnector):
    def __init__(
        self,
        bucket: str,
        prefix: Optional[str] = None,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        self.bucket = bucket
        self.prefix = (prefix or '').strip('/')
        session_kwargs = {
            'region_name': region_name,
            'aws_access_key_id': aws_access_key_id,
            'aws_secret_access_key': aws_secret_access_key,
            'aws_session_token': aws_session_token,
        }
        # Remove None values
        session_kwargs = {k: v for k, v in session_kwargs.items() if v}
        self.client = boto3.client('s3', **session_kwargs)

    def write(self, content: bytes, path: str, content_type: Optional[str] = None) -> str:
        key = path.strip('/')
        if self.prefix:
            key = f"{self.prefix}/{key}"
        put_args = {
            'Bucket': self.bucket,
            'Key': key,
            'Body': content,
        }
        if content_type:
            put_args['ContentType'] = content_type
        self.client.put_object(**put_args)
        return f"s3://{self.bucket}/{key}"

