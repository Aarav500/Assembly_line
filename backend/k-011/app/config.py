import os

class Config:
    SANDBOX_DRY_RUN = os.getenv("SANDBOX_DRY_RUN", "true").strip().lower() in ("1", "true", "yes", "on")
    DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data"))


def ensure_data_dir(path: str):
    os.makedirs(path, exist_ok=True)

