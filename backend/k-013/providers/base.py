from abc import ABC, abstractmethod

class Provider(ABC):
    @abstractmethod
    def generate(self, prompt: str, model_name: str, max_output_tokens: int) -> str:
        raise NotImplementedError

