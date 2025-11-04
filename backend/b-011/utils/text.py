import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

_ws_re = re.compile(r"\s+")
_non_word = re.compile(r"[^a-z0-9\s]")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    t = text.lower()
    t = _non_word.sub(" ", t)
    t = _ws_re.sub(" ", t).strip()
    return t


def tokenize_simple(text: str):
    t = normalize_text(text)
    tokens = [w for w in t.split() if w and w not in ENGLISH_STOP_WORDS]
    return tokens

