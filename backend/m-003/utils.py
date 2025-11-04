import os


def to_posix_path(p: str) -> str:
    return p.replace("\\", "/")


def normalize_owner_id(owner: str) -> str:
    if not owner:
        return ""
    o = owner.strip()
    if o.startswith("@"):
        return o.lower()
    # assume email or plain user; normalize to lower-case
    return o.lower()

