import os
from pathlib import Path

# Temporary working directory for all file operations
TEMP_DIR = Path(os.getenv("TEMP_DIR", "/tmp/file_processing_service"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# FFmpeg binaries
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.getenv("FFPROBE_BIN", "ffprobe")

# Limits and defaults
MAX_FFMPEG_RUNTIME = int(os.getenv("MAX_FFMPEG_RUNTIME", "1800"))  # seconds
DEFAULT_IMAGE_QUALITY = int(os.getenv("DEFAULT_IMAGE_QUALITY", "85"))

