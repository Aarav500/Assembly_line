from abc import ABC, abstractmethod
from typing import Dict


class OptimizationPass(ABC):
    id: str = "base"
    name: str = "Base"
    description: str = "Base optimization pass"

    @abstractmethod
    def analyze(self, path: str) -> Dict:
        raise NotImplementedError

    @abstractmethod
    def apply(self, path: str, dry_run: bool = True) -> Dict:
        raise NotImplementedError

