import os
from dataclasses import dataclass

@dataclass
class Config:
    DATA_DIR: str
    DATABASE_URL: str
    REGISTRY_TOKEN: str | None = None

    @staticmethod
    def from_env() -> "Config":
        data_dir = os.environ.get("DATA_DIR", os.path.abspath(os.path.join(os.getcwd(), "data")))
        os.makedirs(data_dir, exist_ok=True)
        db_url = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(data_dir, 'registry.db')}")
        token = os.environ.get("REGISTRY_TOKEN")
        return Config(DATA_DIR=data_dir, DATABASE_URL=db_url, REGISTRY_TOKEN=token)

