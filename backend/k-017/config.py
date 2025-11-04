import os
from dataclasses import dataclass


@dataclass
class Config:
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    POLICY_FILE: str = "policies.yaml"
    LOG_LEVEL: str = "INFO"
    RELOAD_TOKEN: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            HOST=os.getenv("HOST", "0.0.0.0"),
            PORT=int(os.getenv("PORT", "8000")),
            POLICY_FILE=os.getenv("POLICY_FILE", "policies.yaml"),
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
            RELOAD_TOKEN=os.getenv("RELOAD_TOKEN") or None,
        )

