from .docker_compose import DockerComposeProvider
from .mock import MockProvider

def get_provider(name: str, **kwargs):
    name = (name or "").lower()
    if name in ("docker_compose", "docker-compose", "docker"):
        return DockerComposeProvider(**kwargs)
    if name == "mock":
        return MockProvider(**kwargs)
    raise ValueError(f"Unknown provider: {name}")

