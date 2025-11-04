import os
from typing import List


class Settings:
    def __init__(self) -> None:
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./i18n.db")
        self.SUPPORTED_LANGUAGES: List[str] = [
            lang.strip() for lang in os.getenv("SUPPORTED_LANGUAGES", "en,es,fr").split(",") if lang.strip()
        ]
        self.DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "en")
        self.TRANSLATION_PROVIDER_URL: str = os.getenv("TRANSLATION_PROVIDER_URL", "")
        self.TRANSLATION_PROVIDER_API_KEY: str = os.getenv("TRANSLATION_PROVIDER_API_KEY", "")
        self.ALLOW_ORIGINS: List[str] = [
            o.strip() for o in os.getenv("ALLOW_ORIGINS", "*").split(",") if o.strip()
        ]


settings = Settings()

