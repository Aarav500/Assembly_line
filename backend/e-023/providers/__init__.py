from .mock import MockProvider
from .base import ComputeProvider


def provider_from_name(name: str, params: dict) -> ComputeProvider:
    name = (name or 'mock').lower()
    if name == 'mock':
        return MockProvider(**(params or {}))
    # Placeholder for additional providers (e.g., aws, azure, gcp)
    raise ValueError(f"Unsupported provider: {name}")

