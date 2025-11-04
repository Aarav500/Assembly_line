import re
from typing import Iterable

_SUFFIXES = (
    "ing",
    "ed",
    "es",
    "s",
    "ly",
    "ness",
    "ment",
)


def naive_stem_word(word: str) -> str:
    w = word.lower()
    for suf in _SUFFIXES:
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def normalize_for_dedupe(text: str, by_stem: bool = True) -> str:
    # Lowercase and remove non-alphanumerics except spaces
    t = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    # Collapse spaces
    t = re.sub(r"\s+", " ", t).strip()
    if not by_stem:
        return t
    # Stem each token
    tokens = [naive_stem_word(tok) for tok in t.split()]
    return " ".join(tokens)


def contains_any(text: str, terms: Iterable[str]) -> bool:
    low = text.lower()
    return any(term.lower() in low for term in terms)


def contains_all(text: str, terms: Iterable[str]) -> bool:
    low = text.lower()
    return all(term.lower() in low for term in terms)


def violates_exclusions(text: str, terms: Iterable[str]) -> bool:
    low = text.lower()
    return any(term.lower() in low for term in terms)

