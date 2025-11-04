import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///notification_center.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHEDULER_API_ENABLED = False
    TIMEZONE = os.getenv("TIMEZONE", "UTC")
    # Delivery - simulate sending instead of real integrations
    DRY_RUN_DELIVERY = os.getenv("DRY_RUN_DELIVERY", "1") == "1"
    # Delivery worker interval seconds
    DELIVERY_INTERVAL_SECONDS = int(os.getenv("DELIVERY_INTERVAL_SECONDS", "10"))
    DIGEST_CHECK_INTERVAL_SECONDS = int(os.getenv("DIGEST_CHECK_INTERVAL_SECONDS", "60"))

