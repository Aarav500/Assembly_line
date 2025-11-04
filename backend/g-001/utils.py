from hashlib import sha256 as _sha256

def compute_sha256_from_bytes(b: bytes):
    return _sha256(b).hexdigest()


def normalize_stage(stage: str | None) -> str | None:
    if stage is None:
        return None
    s = stage.strip().lower()
    if s in ("none", ""):
        return None
    mapping = {
        'staging': 'Staging',
        'production': 'Production',
        'prod': 'Production',
        'archived': 'Archived',
        'archive': 'Archived',
        'dev': 'Development',
        'development': 'Development',
    }
    return mapping.get(s, stage)

