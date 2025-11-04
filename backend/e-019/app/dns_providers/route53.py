from typing import Any, Dict
import boto3
from botocore.config import Config as BotoConfig
from .base import DNSProvider


class Route53Provider(DNSProvider):
    def __init__(self, hosted_zone_id: str, aws_region: str | None = None) -> None:
        session_kwargs = {}
        if aws_region:
            session_kwargs["region_name"] = aws_region
        self.client = boto3.client("route53", config=BotoConfig(retries={"max_attempts": 5}))
        self.hosted_zone_id = hosted_zone_id

    def provider_name(self) -> str:
        return "route53"

    def update_record(self, name: str, record_type: str, value: str, ttl: int) -> Dict[str, Any]:
        change_batch = {
            "Comment": "Automated failover update",
            "Changes": [
                {
                    "Action": "UPSERT",
                    "ResourceRecordSet": {
                        "Name": name,
                        "Type": record_type,
                        "TTL": ttl,
                        "ResourceRecords": [{"Value": value}],
                    },
                }
            ],
        }
        resp = self.client.change_resource_record_sets(
            HostedZoneId=self.hosted_zone_id,
            ChangeBatch=change_batch,
        )
        return {
            "status": resp.get("ChangeInfo", {}).get("Status"),
            "id": resp.get("ChangeInfo", {}).get("Id"),
            "submitted_at": resp.get("ChangeInfo", {}).get("SubmittedAt"),
            "provider": self.provider_name(),
            "name": name,
            "type": record_type,
            "value": value,
            "ttl": ttl,
        }

