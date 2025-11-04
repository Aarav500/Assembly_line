import os
import re

DEFAULT_TIMEOUT = float(os.getenv("DEFAULT_TIMEOUT", "2.0"))
TCP_CONNECT_TIMEOUT = float(os.getenv("TCP_CONNECT_TIMEOUT", str(DEFAULT_TIMEOUT)))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", str(DEFAULT_TIMEOUT)))

ALLOWLIST_HOST_REGEX = os.getenv("ALLOWLIST_HOST_REGEX", r".*")
ALLOWLIST_HOST_PATTERN = re.compile(ALLOWLIST_HOST_REGEX)
BLOCK_PRIVATE_IPS = os.getenv("BLOCK_PRIVATE_IPS", "false").strip().lower() in ("1", "true", "yes", "on")

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "8"))

HTTP_ALLOWED_SCHEMES = tuple(s.strip() for s in os.getenv("HTTP_ALLOWED_SCHEMES", "http,https").split(",") if s.strip()) or ("http", "https")
HTTP_VERIFY_TLS = os.getenv("HTTP_VERIFY_TLS", "true").strip().lower() in ("1", "true", "yes", "on")
HTTP_USER_AGENT = os.getenv("HTTP_USER_AGENT", "infra-smoke-tester/1.0")

