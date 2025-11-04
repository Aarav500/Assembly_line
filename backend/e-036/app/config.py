import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self) -> None:
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        storage_dir = os.environ.get("STORAGE_DIR", os.path.join(base_dir, "storage"))
        self.STORAGE_DIR = storage_dir
        db_path = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(storage_dir, 'app.db')}")
        self.SQLALCHEMY_DATABASE_URI = db_path
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False

        # DNS Provider defaults
        self.DNS_PROVIDER = os.environ.get("DNS_PROVIDER", "mock").lower()
        self.CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")

        # ACME/Certbot configuration
        self.ACME_DIRECTORY_URL = os.environ.get(
            "ACME_DIRECTORY_URL",
            "https://acme-staging-v02.api.letsencrypt.org/directory",
        )
        self.ACME_EMAIL = os.environ.get("ACME_EMAIL", "admin@example.com")
        # If True, issues self-signed certs instead of ACME (useful for local dev)
        self.ENABLE_SELF_SIGNED = os.environ.get("ENABLE_SELF_SIGNED", "false").lower() in ("1", "true", "yes")

        # DNS propagation
        self.DNS_PROPAGATION_TIMEOUT = int(os.environ.get("DNS_PROPAGATION_TIMEOUT", "180"))
        self.DNS_PROPAGATION_CHECK_INTERVAL = int(os.environ.get("DNS_PROPAGATION_CHECK_INTERVAL", "8"))

        # Certbot binary (must be installed on system)
        self.CERTBOT_BIN = os.environ.get("CERTBOT_BIN", "certbot")

        # Default TTL for DNS-01 TXT records
        self.DNS_TTL = int(os.environ.get("DNS_TTL", "60"))

