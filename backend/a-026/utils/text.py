import re
from typing import List, Set


TOKEN_RE = re.compile(r"[A-Za-z_]\w+|\d+|[{}()\[\];:.,=+\-*/%<>!|&^~]")


def tokenize_code(s: str) -> List[str]:
    # Remove common block/line comments for several languages (naive)
    s = re.sub(r"(?s)/\*.*?\*/", " ", s)  # C/JS block comments
    s = re.sub(r"(?m)//.*$", " ", s)      # C/JS line comments
    s = re.sub(r"(?m)#.*$", " ", s)       # Python line comments
    tokens = TOKEN_RE.findall(s)
    return tokens


def make_shingles(tokens: List[str], k: int) -> Set[int]:
    if len(tokens) < k:
        return set()
    shingles = set()
    base = 257
    mod = 2**64
    # simple rolling hash for k-grams
    h = 0
    powk = pow(base, k - 1, mod)
    # initial hash
    for i in range(k):
        h = (h * base + hash(tokens[i])) % mod
    shingles.add(h)
    for i in range(k, len(tokens)):
        h = (h - (hash(tokens[i - k]) * powk) % mod + mod) % mod
        h = (h * base + hash(tokens[i])) % mod
        shingles.add(h)
    return shingles


def jaccard(a: Set[int], b: Set[int]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union

