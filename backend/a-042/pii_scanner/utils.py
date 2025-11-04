import fnmatch
import os


def is_probably_binary(path, blocksize=1024):
    try:
        with open(path, 'rb') as f:
            chunk = f.read(blocksize)
            if b'\x00' in chunk:
                return True
            # Heuristic: if >30% bytes are non-text, treat as binary
            if not chunk:
                return False
            text_bytes = bytes(range(32, 127)) + b'\n\r\t\b\f\v\x1b'
            nontext = sum(b not in text_bytes for b in chunk)
            return (nontext / len(chunk)) > 0.30
    except Exception:
        return True


def size_over_limit(path, max_bytes):
    try:
        return os.path.getsize(path) > max_bytes
    except Exception:
        return True


def match_any_glob(name, patterns):
    if not patterns:
        return False
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def luhn_check(number_str):
    digits = [int(ch) for ch in number_str if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d = d * 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def masked_context(line, start, end, radius=6, token='[REDACTED]'):
    prefix = line[max(0, start - radius):start]
    suffix = line[end:min(len(line), end + radius)]
    return f"{prefix}{token}{suffix}"


def safe_join(base, *paths):
    # Simple safe join to avoid path traversal when writing outputs
    final_path = os.path.abspath(os.path.join(base, *paths))
    base = os.path.abspath(base)
    if not final_path.startswith(base + os.sep) and final_path != base:
        raise ValueError('Unsafe path traversal detected')
    return final_path

