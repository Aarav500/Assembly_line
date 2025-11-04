from abc import ABC, abstractmethod
from typing import List, Dict


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    def list_resources(self) -> List[Dict]:
        raise NotImplementedError

