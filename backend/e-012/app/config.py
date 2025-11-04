import os
from typing import Dict, Any


def str_to_bool(v: str, default: bool = False) -> bool:
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


def load_config() -> Dict[str, Any]:
    # Optionally load from .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    default_ttl = int(os.getenv("DEFAULT_TTL", "60"))
    surrogate_ttl = int(os.getenv("SURROGATE_TTL", "300"))

    return {
        "DEBUG": str_to_bool(os.getenv("FLASK_DEBUG", os.getenv("DEBUG", "0"))),
        "ENV": os.getenv("FLASK_ENV", "production"),
        "APP_NAME": os.getenv("APP_NAME", "flask-app"),
        "RELEASE_SHA": os.getenv("RELEASE_SHA", "dev"),
        "PREVIOUS_RELEASE_SHA": os.getenv("PREVIOUS_RELEASE_SHA", ""),
        "DEFAULT_TTL": default_ttl,
        "SURROGATE_TTL": surrogate_ttl,
        "ENABLE_ETAG": str_to_bool(os.getenv("ENABLE_ETAG", "1"), True),
        "CDN_PROVIDER": (os.getenv("CDN_PROVIDER") or "").lower(),
        # Cloudflare
        "CLOUDFLARE_API_TOKEN": os.getenv("CLOUDFLARE_API_TOKEN", ""),
        "CLOUDFLARE_ZONE_ID": os.getenv("CLOUDFLARE_ZONE_ID", ""),
        "CLOUDFLARE_SITE_URL": os.getenv("CLOUDFLARE_SITE_URL", ""),
        # Fastly
        "FASTLY_API_TOKEN": os.getenv("FASTLY_API_TOKEN", ""),
        "FASTLY_SERVICE_ID": os.getenv("FASTLY_SERVICE_ID", ""),
        # CloudFront
        "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
        "CLOUDFRONT_DISTRIBUTION_ID": os.getenv("CLOUDFRONT_DISTRIBUTION_ID", ""),
        # Deploy purge config
        "CDN_PURGE_ALL_ON_DEPLOY": str_to_bool(os.getenv("CDN_PURGE_ALL_ON_DEPLOY", "0"), False),
        "DEPLOY_CHANGED_PATHS_FILE": os.getenv("DEPLOY_CHANGED_PATHS_FILE", ""),
    }

