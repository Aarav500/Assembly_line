import os
from datetime import timedelta

# SMTP configuration
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "false").lower() in {"1", "true", "yes", "on"}

FROM_EMAIL = os.getenv("FROM_EMAIL", "no-reply@example.com")
FROM_NAME = os.getenv("FROM_NAME", "Example App")

# Service configuration
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "email_service.db"))
QUEUE_POLL_INTERVAL = float(os.getenv("QUEUE_POLL_INTERVAL", "2.0"))
MAX_RETRIES_DEFAULT = int(os.getenv("MAX_RETRIES_DEFAULT", "5"))
BACKOFF_BASE_SECONDS = float(os.getenv("BACKOFF_BASE_SECONDS", "5.0"))  # exponential backoff base
BACKOFF_MAX_SECONDS = float(os.getenv("BACKOFF_MAX_SECONDS", "300.0"))  # cap backoff at 5 min

# Security
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # optional shared secret for webhooks

# Misc
APP_DOMAIN_FOR_MESSAGE_ID = os.getenv("APP_DOMAIN_FOR_MESSAGE_ID", "example.com")

# Timezone handling note: using naive UTC timestamps stored as ISO strings

