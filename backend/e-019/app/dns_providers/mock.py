from typing import Any, Dict
from .base import DNSProvider


class MockDNSProvider(DNSProvider):
    def __init__(self) -> None:
        self._last: Dict[str, Any] | None = None

    def update_record(self, name: str, record_type: str, value: str, ttl: int) -> Dict[str, Any]:
        self._last = {
            "name": name,
            "type": record_type,
            "value": value,
            "ttl": ttl,
            "status": "mock-updated",
        }
        return self._last

    def provider_name(self) -> str:
        return "mock"

