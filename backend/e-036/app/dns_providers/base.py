from abc import ABC, abstractmethod


class BaseDNSProvider(ABC):
    @abstractmethod
    def ensure_txt_record(self, name: str, value: str, ttl: int = 60) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_txt_record(self, name: str, value: str) -> None:
        raise NotImplementedError

