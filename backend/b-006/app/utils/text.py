import re

_STOPWORDS = set()


def init_stopwords():
    global _STOPWORDS
    if _STOPWORDS:
        return
    # Simple, compact English stopword list
    _STOPWORDS = set(
        "a an and are as at be but by for if in into is it no not of on or s such t that the their then there these they this to was will with you your".split()
    )


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.lower()
    # normalize urls/emails to tokens
    text = re.sub(r"https?://\S+", " url ", text)
    text = re.sub(r"\S+@\S+", " email ", text)
    # keep alphanum and spaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str):
    parts = text.split()
    return [p for p in parts if p not in _STOPWORDS]

