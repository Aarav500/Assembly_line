from abc import ABC, abstractmethod

class Strategy(ABC):
    name = "base"
    description = "Base strategy"

    @abstractmethod
    def run(self, prompt: str, config: dict) -> str:
        raise NotImplementedError

