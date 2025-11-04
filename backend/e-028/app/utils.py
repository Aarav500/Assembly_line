import hashlib
import os
import re
import tempfile
from typing import IO, Tuple

NAME_RE = re.compile(r"^[a-z0-9._-]{1,255}$")
TAG_RE = re.compile(r"^[A-Za-z0-9._-]{1,255}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")

try:
    import semver as pysemver
except Exception:
    pysemver = None


def validate_name(name: str) -> bool:
    return bool(NAME_RE.match(name))


def validate_tag(tag: str) -> bool:
    return bool(TAG_RE.match(tag))


def is_valid_sha256(hex_str: str) -> bool:
    return bool(SHA256_RE.match(hex_str))


def compute_stream_sha256_to_tempfile(stream: IO[bytes]) -> Tuple[str, int, str]:
    hasher = hashlib.sha256()
    fd, tmp_path = tempfile.mkstemp(prefix="upload_", suffix=".part")
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
                out.write(chunk)
                size += len(chunk)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise
    sha256_hex = hasher.hexdigest()
    return tmp_path, size, sha256_hex


def parse_semver(version: str):
    if pysemver is None:
        # simple regex fallback
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$", version)
        if not m:
            return None
        major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return {
            "major": major,
            "minor": minor,
            "patch": patch,
            "prerelease": m.group(4),
            "build": m.group(5),
        }
    try:
        v = pysemver.VersionInfo.parse(version)
        return {
            "major": v.major,
            "minor": v.minor,
            "patch": v.patch,
            "prerelease": v.prerelease,
            "build": v.build,
        }
    except Exception:
        return None

