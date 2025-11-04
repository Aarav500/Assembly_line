import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    METADB_URL = os.getenv("METADB_URL", "sqlite:///pipeline_meta.db")
    SECRET_KEY = os.getenv("SECRET_KEY", "devsecret")

    # Mapping of env name to DB URL
    TARGET_DBS = {}
    for key, value in os.environ.items():
        if key.startswith("TARGET_DB_URL_") and value:
            env = key.replace("TARGET_DB_URL_", "").lower()
            TARGET_DBS[env] = value

    # Required approval roles by env
    REQUIRED_ROLES = {}
    for key, value in os.environ.items():
        if key.startswith("REQUIRED_ROLES_") and value:
            env = key.replace("REQUIRED_ROLES_", "").lower()
            roles = [r.strip() for r in value.split(",") if r.strip()]
            REQUIRED_ROLES[env] = roles

    # Defaults if none set
    if not TARGET_DBS:
        TARGET_DBS = {
            "dev": os.getenv("TARGET_DB_URL_DEV", "sqlite:///target_dev.db"),
        }
    if not REQUIRED_ROLES:
        REQUIRED_ROLES = {
            "dev": ["owner"],
            "prod": ["owner", "dba"],
        }

    # Safety check tuning
    DIALECT_BY_ENV = {}  # env -> dialect string like 'postgresql' or 'sqlite'
    for env, url in TARGET_DBS.items():
        if "://" in url:
            dialect = url.split("://", 1)[0]
            # normalize sqlalchemy postgres dialect names
            if dialect.startswith("postgres"):
                dialect = "postgresql"
            if dialect.startswith("sqlite"):
                dialect = "sqlite"
            DIALECT_BY_ENV[env] = dialect
        else:
            DIALECT_BY_ENV[env] = "unknown"

