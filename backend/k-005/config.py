import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        # Provider
        self.DOWNSTREAM_PROVIDER = os.getenv("DOWNSTREAM_PROVIDER", "openai")
        self.DOWNSTREAM_URL = os.getenv("DOWNSTREAM_URL")

        # OpenAI
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")

        # Batching
        self.BATCH_WINDOW_MS = int(os.getenv("BATCH_WINDOW_MS", "50"))
        self.MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "8"))

        # Cache
        self.CACHE_TTL_SEC = int(os.getenv("CACHE_TTL_SEC", "300"))
        self.CACHE_MAX_ENTRIES = int(os.getenv("CACHE_MAX_ENTRIES", "4096"))

        # Token budgets
        self.DEFAULT_MAX_OUTPUT_TOKENS = int(os.getenv("DEFAULT_MAX_OUTPUT_TOKENS", "512"))
        self.DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.2"))
        self.DEFAULT_TOP_P = float(os.getenv("DEFAULT_TOP_P", "1.0"))
        self.DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

        # Contexts per model (rough)
        self.DEFAULT_CONTEXT_TOKENS = int(os.getenv("DEFAULT_CONTEXT_TOKENS", "8192"))
        self.MODEL_CONTEXT_TOKENS = {
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-4.1": 128000,
            "gpt-4-turbo": 128000,
            "gpt-3.5-turbo": 16385,
        }
        self.META_OVERHEAD_TOKENS = int(os.getenv("META_OVERHEAD_TOKENS", "256"))

        # Server
        self.REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "60"))

    @staticmethod
    def from_env():
        load_dotenv(override=False)
        return Config()

