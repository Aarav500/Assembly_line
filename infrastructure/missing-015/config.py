import os
import json
from dotenv import load_dotenv
from storage.redis_client import get_redis

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "changeme-admin")
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL")
BILLING_WEBHOOK_URL = os.getenv("BILLING_WEBHOOK_URL")
SERVICE_NAME = os.getenv("SERVICE_NAME", "quota-api")
CREATE_DEMO_USER = os.getenv("CREATE_DEMO_USER", "0") == "1"

DEFAULT_TIERS = {
    "free": {
        "name": "free",
        "rps": 2,
        "rpm": 60,
        "monthly_quota": 1000,
        "overage_price": 0.02,
        "currency": "USD",
        "hard_limit": False
    },
    "pro": {
        "name": "pro",
        "rps": 10,
        "rpm": 600,
        "monthly_quota": 100000,
        "overage_price": 0.005,
        "currency": "USD",
        "hard_limit": False
    },
    "enterprise": {
        "name": "enterprise",
        "rps": 50,
        "rpm": 3000,
        "monthly_quota": 1000000,
        "overage_price": 0.002,
        "currency": "USD",
        "hard_limit": False
    }
}


def init_default_data():
    r = get_redis()
    # Initialize tiers if not exist
    for tier_name, tier in DEFAULT_TIERS.items():
        tier_key = f"api:tier:{tier_name}"
        if not r.exists(tier_key):
            r.hset(tier_key, mapping={
                "name": tier["name"],
                "rps": tier["rps"],
                "rpm": tier["rpm"],
                "monthly_quota": tier["monthly_quota"],
                "overage_price": tier["overage_price"],
                "currency": tier["currency"],
                "hard_limit": int(tier["hard_limit"]) or 0,
            })
    # Create demo user if requested
    if CREATE_DEMO_USER:
        from services.users import ensure_demo_user
        ensure_demo_user()

