import time
from .base import BaseDNSProvider


class MockDNSProvider(BaseDNSProvider):
    def ensure_txt_record(self, name: str, value: str, ttl: int = 60) -> None:
        print(f"[MOCK DNS] Create TXT {name} TTL={ttl} -> {value}")
        # Simulate propagation delay
        time.sleep(1)

    def delete_txt_record(self, name: str, value: str) -> None:
        print(f"[MOCK DNS] Delete TXT {name} -> {value}")

