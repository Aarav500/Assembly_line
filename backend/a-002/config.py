import os
import platform
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
PROJECTS_ROOT = DATA_DIR / "projects"
TEMP_UPLOADS = DATA_DIR / "tmp"

# Max upload size (1GB by default)
MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", str(1024 * 1024 * 1024)))

# Allowed archive types
ALLOWED_EXTENSIONS = set((os.environ.get("ALLOWED_EXTENSIONS", "zip").lower()).split(","))

# Whether to attempt symlinks for path-based additions
USE_SYMLINKS = os.environ.get("USE_SYMLINKS", "1") == "1"

# Allowed base directories for path-based project addition
# Provide a colon/semicolon separated list in ALLOWED_BASE_DIRS; defaults are conservative
if "ALLOWED_BASE_DIRS" in os.environ:
    ALLOWED_BASE_DIRS = [p for p in os.environ["ALLOWED_BASE_DIRS"].split(os.pathsep) if p.strip()]
else:
    system = platform.system().lower()
    if system == "windows":
        # Common additional drives; adjust as needed
        ALLOWED_BASE_DIRS = [
            r"D:\\",
            r"E:\\",
            r"F:\\",
            r"\\\\",  # allow UNC prefixes (\\server\share)
        ]
    else:
        # Typical mount points on Unix
        ALLOWED_BASE_DIRS = [
            "/mnt",
            "/media",
            "/Volumes",  # macOS external volumes
        ]

# Ensure data directories exist (created by app on startup as well)
for p in (DATA_DIR, PROJECTS_ROOT, TEMP_UPLOADS):
    try:
        Path(p).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

