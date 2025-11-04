from typing import List, Optional, Dict, Tuple

try:
    import boto3
except Exception:  # pragma: no cover - optional dependency
    boto3 = None

from config import settings


class SESProvider:
    def __init__(self, region_name: Optional[str] = None):
        if not boto3:
            raise RuntimeError("boto3 is required for SESProvider")
        self.client = boto3.client(
            "ses",
            region_name=region_name or settings.SES_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        )

    def send(
        self,
        *,
        to_email: str,
        from_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        email_id: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        destination = {"ToAddresses": [to_email]}
        message = {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text_body, "Charset": "UTF-8"},
                "Html": {"Data": html_body, "Charset": "UTF-8"},
            },
        }
        headers = {}
        if email_id:
            headers["X-Email-Id"] = email_id
        # Tags
        tags_list = []
        if tags:
            for t in tags:
                tags_list.append({"Name": "category", "Value": t})
        if metadata:
            for k, v in metadata.items():
                tags_list.append({"Name": str(k), "Value": str(v)})

        kwargs = {
            "Source": from_email,
            "Destination": destination,
            "Message": message,
        }
        if tags_list:
            kwargs["Tags"] = tags_list
        if headers:
            # SES supports custom headers via RawEmail. For simplicity we ignore here.
            pass

        resp = self.client.send_email(**kwargs)
        return resp.get("MessageId", ""), resp

