import os
import sys
import time

# Ensure project root is importable
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, BASE_DIR)

from app.dns_providers import provider_from_env  # noqa: E402


def wait_for_propagation(name: str, value: str, timeout: int, interval: int) -> None:
    try:
        import dns.resolver
    except Exception as e:  # noqa: BLE001
        print(f"dnspython not installed: {e}")
        time.sleep(15)
        return

    end = time.time() + timeout
    while time.time() < end:
        try:
            answers = dns.resolver.resolve(name, "TXT")
            txts = [b"".join(rdata.strings).decode("utf-8") for rdata in answers]  # type: ignore[attr-defined]
            if value in txts:
                return
        except Exception:
            pass
        time.sleep(interval)
    print("Warning: DNS propagation not confirmed before timeout.")


def main():
    domain = os.environ.get("CERTBOT_DOMAIN")
    validation = os.environ.get("CERTBOT_VALIDATION")
    ttl = int(os.environ.get("DNS_TTL", "60"))
    timeout = int(os.environ.get("DNS_PROPAGATION_TIMEOUT", "180"))
    interval = int(os.environ.get("DNS_PROPAGATION_CHECK_INTERVAL", "8"))
    if not domain or not validation:
        print("Missing CERTBOT_DOMAIN or CERTBOT_VALIDATION in environment", file=sys.stderr)
        sys.exit(1)

    record_name = f"_acme-challenge.{domain}"

    provider = provider_from_env()
    provider.ensure_txt_record(record_name, validation, ttl=ttl)

    wait_for_propagation(record_name, validation, timeout=timeout, interval=interval)


if __name__ == "__main__":
    main()

