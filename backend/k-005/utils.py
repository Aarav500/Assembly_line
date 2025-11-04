import hashlib
import json
import time
from typing import Any, Dict, List


def now_s():
    return int(time.time())


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Rough heuristic: 1 token ~= 4 chars
    return max(1, (len(text) + 3) // 4)


def compute_request_hash(obj: Any) -> str:
    serialized = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def join_messages_as_text(messages: List[Dict[str, str]]) -> str:
    parts = []
    for m in messages:
        parts.append(f"[{m.get('role')}]\n{m.get('content','')}")
    return "\n\n".join(parts)


def normalize_openai_response(resp: Dict[str, Any], model: str) -> Dict[str, Any]:
    # Ensure minimal OpenAI shape
    try:
        _ = resp["choices"][0]["message"]["content"]
        return resp
    except Exception:
        text = ""
        if isinstance(resp, dict) and "content" in resp:
            text = resp["content"]
        return {
            "id": f"cmpl-{compute_request_hash(resp)[:12]}",
            "object": "chat.completion",
            "created": now_s(),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        }

