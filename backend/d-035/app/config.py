import os
import yaml
from typing import List


def env_bool(key: str, default: bool = False) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.production_images_env = os.environ.get("PRODUCTION_IMAGES", "")
        self.images_file = os.environ.get("IMAGES_FILE", "config/images.yaml")
        self.schedule_cron = os.environ.get("SCHEDULE_CRON", "0 3 * * *")  # daily at 03:00
        self.scanner = os.environ.get("SCANNER", "trivy")  # trivy | mock
        self.db_path = os.environ.get("DB_PATH", "data/cve_scans.db")
        self.retain_runs = int(os.environ.get("RETAIN_RUNS", "0"))  # 0 means keep all
        self.trivy_path = os.environ.get("TRIVY_PATH", "trivy")
        self.trivy_timeout = int(os.environ.get("TRIVY_TIMEOUT", "600"))  # seconds
        self.timezone = os.environ.get("TIMEZONE", "UTC")
        self.flask_host = os.environ.get("FLASK_HOST", "0.0.0.0")
        self.flask_port = int(os.environ.get("FLASK_PORT", "8080"))
        self.debug = env_bool("DEBUG", False)

    def load_images(self) -> List[str]:
        images: List[str] = []
        if self.production_images_env.strip():
            for part in self.production_images_env.split(","):
                item = part.strip()
                if item:
                    images.append(item)
        else:
            images = self._load_images_from_file(self.images_file)
        # Deduplicate while preserving order
        seen = set()
        unique: List[str] = []
        for img in images:
            if img not in seen:
                unique.append(img)
                seen.add(img)
        return unique

    @staticmethod
    def _load_images_from_file(path: str) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                imgs = data.get("images") or []
                return [str(x).strip() for x in imgs if str(x).strip()]
        except FileNotFoundError:
            return []


settings = Settings()

