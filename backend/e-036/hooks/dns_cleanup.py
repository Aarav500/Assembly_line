import os
import sys

# Ensure project root is importable
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, BASE_DIR)

from app.dns_providers import provider_from_env  # noqa: E402


def main():
    domain = os.environ.get("CERTBOT_DOMAIN")
    validation = os.environ.get("CERTBOT_VALIDATION")
    if not domain or not validation:
        print("Missing CERTBOT_DOMAIN or CERTBOT_VALIDATION in environment", file=sys.stderr)
        sys.exit(1)
    record_name = f"_acme-challenge.{domain}"
    provider = provider_from_env()
    try:
        provider.delete_txt_record(record_name, validation)
    except Exception as e:  # noqa: BLE001
        print(f"Cleanup error: {e}")


if __name__ == "__main__":
    main()

