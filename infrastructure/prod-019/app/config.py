import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
    REGION_ID: str = os.getenv("REGION_ID", "region-unknown")
    NODE_ID: str = os.getenv("NODE_ID", "node-unknown")
    PEERS: list[str] = [p.strip() for p in os.getenv("PEERS", "").split(",") if p.strip()]
    SYNC_INTERVAL_SECONDS: int = int(os.getenv("SYNC_INTERVAL_SECONDS", "5"))
    CHANGE_BATCH_SIZE: int = int(os.getenv("CHANGE_BATCH_SIZE", "500"))
    PORT: int = int(os.getenv("PORT", "8000"))

config = Config()

