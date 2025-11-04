from typing import Optional

from azure.storage.blob import BlobServiceClient

from .base import BaseConnector


class ADLSConnector(BaseConnector):
    def __init__(
        self,
        container: str,
        prefix: Optional[str] = None,
        connection_string: Optional[str] = None,
        account_name: Optional[str] = None,
        account_key: Optional[str] = None,
    ):
        self.container_name = container
        self.prefix = (prefix or '').strip('/')
        if connection_string:
            self.service_client = BlobServiceClient.from_connection_string(connection_string)
        elif account_name and account_key:
            account_url = f"https://{account_name}.blob.core.windows.net"
            self.service_client = BlobServiceClient(account_url=account_url, credential=account_key)
        else:
            # Try default from env
            self.service_client = BlobServiceClient.from_connection_string("")
        self.container_client = self.service_client.get_container_client(self.container_name)

    def write(self, content: bytes, path: str, content_type: Optional[str] = None) -> str:
        blob_name = path.strip('/')
        if self.prefix:
            blob_name = f"{self.prefix}/{blob_name}"
        blob_client = self.container_client.get_blob_client(blob_name)
        content_settings = None
        if content_type:
            from azure.storage.blob import ContentSettings
            content_settings = ContentSettings(content_type=content_type)
        blob_client.upload_blob(content, overwrite=True, content_settings=content_settings)
        return f"https://{self.container_client.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}"

