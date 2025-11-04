import re

def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text or " ")
    return text.strip()


def strip_brackets(text: str) -> str:
    return re.sub(r"^[\[(]+|[\])]+$", "", text or "")

