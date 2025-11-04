from typing import Dict
from .base import Provider
from .dummy import DummyProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, Provider] = {}
        self.register(DummyProvider())

    def register(self, provider: Provider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> Provider | None:
        return self._providers.get(name)

    def list(self):
        return [
            {
                "name": p.name,
                "label": p.label,
                "capabilities": p.capabilities(),
            }
            for p in self._providers.values()
        ]


registry = ProviderRegistry()

