from abc import ABC, abstractmethod
from typing import Optional


class BaseConnector(ABC):
    @abstractmethod
    def write(self, content: bytes, path: str, content_type: Optional[str] = None) -> str:
        """
        Write content to destination.
        Returns a URI-like location string.
        """
        raise NotImplementedError

