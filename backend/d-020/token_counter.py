import math

try:
    import tiktoken  # Optional dependency for OpenAI models
except Exception:  # pragma: no cover
    tiktoken = None


OPENAI_MODEL_FALLBACK_ENCODING = "cl100k_base"


def _openai_count(text: str, model: str = None) -> int:
    if not tiktoken:
        # Fallback heuristic: ~4 chars per token
        return math.ceil(len(text) / 4) if text else 0
    try:
        if model:
            enc = tiktoken.encoding_for_model(model)
        else:
            enc = tiktoken.get_encoding(OPENAI_MODEL_FALLBACK_ENCODING)
        return len(enc.encode(text or ""))
    except Exception:
        enc = tiktoken.get_encoding(OPENAI_MODEL_FALLBACK_ENCODING)
        return len(enc.encode(text or ""))


def estimate_tokens(text: str, model: str = None, provider: str = None) -> int:
    if not text:
        return 0
    # crude routing: if model name resembles openai naming, try openai counter
    m = (model or "").lower()
    if any(k in m for k in ["gpt", "o1", "openai", "4o", "3.5"]):
        return _openai_count(text, model=model)
    # generic fallback
    return math.ceil(len(text) / 4)

