import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def str2bool(v: str) -> bool:
    return str(v).lower() in {"1", "true", "t", "yes", "y", "on"}


@dataclass
class Settings:
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    REPO_FULL_NAME: str = os.getenv("REPO_FULL_NAME", "")  # e.g. owner/repo
    DEFAULT_BRANCH: str = os.getenv("DEFAULT_BRANCH", "main")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
    DRY_RUN: bool = str2bool(os.getenv("DRY_RUN", "false"))
    RELEASE_PREFIX: str = os.getenv("RELEASE_PREFIX", "v")  # e.g. v1.2.3
    MIN_BUMP_IF_EMPTY: str = os.getenv("MIN_BUMP_IF_EMPTY", "patch")  # patch|minor|major|none
    RELEASE_TITLE_TEMPLATE: str = os.getenv("RELEASE_TITLE_TEMPLATE", "{tag}")
    CHANGELOG_HEADER: str = os.getenv("CHANGELOG_HEADER", "")


settings = Settings()

