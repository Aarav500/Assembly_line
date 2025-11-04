import re
from typing import List

_token_re = re.compile(r"\w+", re.UNICODE)


def simple_tokenize(text: str) -> List[str]:
    if not text:
        return []
    return _token_re.findall(text.lower())

