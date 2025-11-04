from typing import List
from .base import BaseProvider
from .mock_provider import MockProvider


def get_registered_providers() -> List[BaseProvider]:
    # Extend this list with real providers (AWS, GCP, Azure) when available
    return [
        MockProvider(),
    ]

