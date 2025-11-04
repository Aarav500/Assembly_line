from abc import ABC, abstractmethod
from typing import Any, Dict


class DNSProvider(ABC):
    @abstractmethod
    def update_record(self, name: str, record_type: str, value: str, ttl: int) -> Dict[str, Any]:
        """Create or update DNS record to point to value."""
        raise NotImplementedError

    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

