from typing import Dict
from .mock import MockProvider
try:
    from .openai_provider import OpenAIProvider
except Exception:  # pragma: no cover - optional dependency
    OpenAIProvider = None  # type: ignore

_providers_cache: Dict[str, object] = {}


def get_provider(name: str):
    if name in _providers_cache:
        return _providers_cache[name]

    if name == "mock":
        _providers_cache[name] = MockProvider()
        return _providers_cache[name]

    if name == "openai":
        if OpenAIProvider is None:
            raise RuntimeError("OpenAI provider not available. Install 'openai' and ensure import works.")
        _providers_cache[name] = OpenAIProvider()
        return _providers_cache[name]

    raise ValueError(f"Unknown provider '{name}'")

