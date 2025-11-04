import re

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Very rough: whitespace words as tokens + punctuation handling
    # For routing decisions this is fine; replace with tiktoken for precision if needed
    parts = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    return max(1, len(parts))

