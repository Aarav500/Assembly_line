from typing import Optional

try:
    import magic  # python-magic
except Exception:  # pragma: no cover
    magic = None

import mimetypes

DEFAULT_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

def sniff_mime(path: str) -> str:
    if magic is not None:
        try:
            m = magic.Magic(mime=True)
            return m.from_file(path) or "application/octet-stream"
        except Exception:
            pass
    # Fallback: guess by extension only if magic unavailable
    guess, _ = mimetypes.guess_type(path)
    return guess or "application/octet-stream"


def extension_for_mime(mime: str) -> str:
    if mime in DEFAULT_EXTENSIONS:
        return DEFAULT_EXTENSIONS[mime]
    # Best-effort fallback
    exts = mimetypes.guess_all_extensions(mime) or []
    if exts:
        return exts[0]
    return ""

