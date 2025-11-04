import os
from typing import List

class Config:
    def __init__(self) -> None:
        # Maximum total request size enforced by Flask (in bytes)
        self.MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", str(12 * 1024 * 1024)))  # 12MB default
        # Per-file size limit (in bytes)
        self.MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024)))  # 10MB default

        # Storage and temp directories
        self.STORAGE_ROOT: str = os.getenv("STORAGE_ROOT", "/app/storage")
        self.TMP_DIR: str = os.getenv("TMP_DIR", "/app/tmp")

        # Allowed MIME types (content-sniffed)
        default_allowed = ",".join([
            "image/jpeg",
            "image/png",
            "application/pdf",
            "application/zip",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ])
        allowed = os.getenv("ALLOWED_MIME_TYPES", default_allowed)
        self.ALLOWED_MIME_TYPES: List[str] = [m.strip() for m in allowed.split(",") if m.strip()]

        # ClamAV settings
        self.CLAMAV_MODE: str = os.getenv("CLAMAV_MODE", "clamscan")  # clamscan|clamd|auto
        self.CLAMD_UNIX_SOCKET: str = os.getenv("CLAMD_UNIX_SOCKET", "/var/run/clamav/clamd.ctl")
        self.CLAMD_HOST: str = os.getenv("CLAMD_HOST", "127.0.0.1")
        self.CLAMD_PORT: int = int(os.getenv("CLAMD_PORT", "3310"))
        self.CLAMSCAN_PATH: str = os.getenv("CLAMSCAN_PATH", "/usr/bin/clamscan")
        self.CLAMAV_SCAN_TIMEOUT: int = int(os.getenv("CLAMAV_SCAN_TIMEOUT", "60"))

