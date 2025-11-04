import os
from dataclasses import dataclass


def str_to_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Config:
    app_name: str = os.getenv("APP_NAME", "cross-region-failover")
    api_token: str | None = os.getenv("API_TOKEN")

    primary_region: str = os.getenv("PRIMARY_REGION", "us-east-1")
    secondary_region: str = os.getenv("SECONDARY_REGION", "us-west-2")

    primary_health_url: str | None = os.getenv("PRIMARY_HEALTHCHECK_URL")
    secondary_health_url: str | None = os.getenv("SECONDARY_HEALTHCHECK_URL")
    health_timeout: float = float(os.getenv("HEALTHCHECK_TIMEOUT_SECONDS", "3"))
    health_retries: int = int(os.getenv("HEALTHCHECK_RETRIES", "2"))

    dns_provider: str = os.getenv("DNS_PROVIDER", "mock")  # route53|cloudflare|mock|none
    dns_record_name: str | None = os.getenv("DNS_RECORD_NAME")
    dns_record_type: str = os.getenv("DNS_RECORD_TYPE", "A").upper()
    dns_ttl: int = int(os.getenv("DNS_TTL", "60"))

    primary_dns_value: str | None = os.getenv("PRIMARY_DNS_VALUE")
    secondary_dns_value: str | None = os.getenv("SECONDARY_DNS_VALUE")

    # Route53
    route53_hosted_zone_id: str | None = os.getenv("ROUTE53_HOSTED_ZONE_ID")
    aws_region: str | None = os.getenv("AWS_REGION")

    # Cloudflare
    cloudflare_api_token: str | None = os.getenv("CLOUDFLARE_API_TOKEN")
    cloudflare_zone_id: str | None = os.getenv("CLOUDFLARE_ZONE_ID")

    state_file: str = os.getenv("STATE_FILE", "/data/state.json")

    auto_failback: bool = str_to_bool(os.getenv("AUTO_FAILBACK"), False)

    def validate(self) -> None:
        if self.dns_provider.lower() not in {"route53", "cloudflare", "mock", "none"}:
            raise ValueError("Invalid DNS_PROVIDER")
        if not self.primary_health_url or not self.secondary_health_url:
            raise ValueError("PRIMARY_HEALTHCHECK_URL and SECONDARY_HEALTHCHECK_URL must be set")
        if self.dns_provider.lower() != "none":
            if not self.dns_record_name:
                raise ValueError("DNS_RECORD_NAME must be set when DNS_PROVIDER is not 'none'")
            if not self.primary_dns_value or not self.secondary_dns_value:
                raise ValueError("PRIMARY_DNS_VALUE and SECONDARY_DNS_VALUE must be set")
        if self.dns_record_type not in {"A", "CNAME"}:
            raise ValueError("DNS_RECORD_TYPE must be A or CNAME")

    def record_value_for_region(self, region: str) -> str:
        if region == self.primary_region:
            if not self.primary_dns_value:
                raise ValueError("PRIMARY_DNS_VALUE is not configured")
            return self.primary_dns_value
        if region == self.secondary_region:
            if not self.secondary_dns_value:
                raise ValueError("SECONDARY_DNS_VALUE is not configured")
            return self.secondary_dns_value
        raise ValueError(f"Unknown region: {region}")

    def other_region(self, region: str) -> str:
        return self.secondary_region if region == self.primary_region else self.primary_region

