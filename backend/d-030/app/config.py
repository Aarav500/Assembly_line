import os

SUPPORTED_REGIONS = ["us-east-1", "eu-west-1", "ap-southeast-1"]
DEFAULT_REGION = "us-east-1"

REGION_CONFIG: dict[str, dict[str, str]] = {
    "us-east-1": {
        "GREETING": "Howdy",
        "CDN_URL": "https://cdn.use1.example.com",
    },
    "eu-west-1": {
        "GREETING": "Cheers",
        "CDN_URL": "https://cdn.euw1.example.com",
    },
    "ap-southeast-1": {
        "GREETING": "G'day",
        "CDN_URL": "https://cdn.apse1.example.com",
    },
}


def resolve_region(value: str | None = None) -> str:
    region = (value or os.getenv("GEO_REGION") or DEFAULT_REGION).strip()
    if region not in REGION_CONFIG:
        raise ValueError(f"Unsupported region: {region}")
    return region


def load_config(region: str | None = None) -> dict:
    region = resolve_region(region)
    base = {
        "REGION": region,
        "APP_NAME": "geo-flask",
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "ci"),
    }
    base.update(REGION_CONFIG[region])
    return base

