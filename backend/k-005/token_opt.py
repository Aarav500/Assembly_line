import re
from typing import List, Dict, Any, Optional
from utils import estimate_tokens

class TokenOptimizer:
    def __init__(self, config):
        self.config = config

    def extract_system_prompt(self, messages: List[Dict[str, str]]) -> Optional[str]:
        for m in messages:
            if m.get("role") == "system" and m.get("content"):
                return m.get("content")
        return None

    def compress_text(self, text: str, max_tokens: int) -> str:
        if not text:
            return text
        # Basic whitespace normalization
        s = text.strip()
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        # Collapse long code blocks while preserving start/end
        s = self._compress_code_blocks(s, max_tokens=max_tokens)
        # Truncate if still too long
        if estimate_tokens(s) > max_tokens:
            s = self._head_tail_keep(s, max_tokens=max_tokens)
        return s

    def _compress_code_blocks(self, text: str, max_tokens: int) -> str:
        # Identify fenced code blocks ```lang ... ``` and compress middle
        pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
        def repl(m):
            block = m.group(0)
            if estimate_tokens(block) <= max_tokens // 2:
                return block
            lines = block.splitlines()
            if len(lines) <= 12:
                return block
            head = "\n".join(lines[:8])
            tail = "\n".join(lines[-8:])
            return head + "\n...\n" + tail
        return pattern.sub(repl, text)

    def _head_tail_keep(self, text: str, max_tokens: int) -> str:
        # Keep 70% head and 30% tail by tokens
        tokens = estimate_tokens(text)
        if tokens <= max_tokens:
            return text
        ratio = max(min(max_tokens / max(tokens, 1), 1.0), 0.1)
        head_tokens = int(max_tokens * 0.7)
        tail_tokens = max_tokens - head_tokens
        # Approximate by characters
        n = len(text)
        head_chars = int(len(text) * (head_tokens / tokens))
        tail_chars = int(len(text) * (tail_tokens / tokens))
        head = text[:head_chars]
        tail = text[-tail_chars:] if tail_chars > 0 else ""
        return head + "\n...\n" + tail

    def prepare_messages(self, messages: List[Dict[str, str]], model: str, requested_output_tokens: int) -> List[Dict[str, str]]:
        # Trim conversation to fit context window
        context_limit = self.config.MODEL_CONTEXT_TOKENS.get(model, self.config.DEFAULT_CONTEXT_TOKENS)
        reserve = min(requested_output_tokens or self.config.DEFAULT_MAX_OUTPUT_TOKENS, self.config.DEFAULT_MAX_OUTPUT_TOKENS)
        budget = max(context_limit - reserve - self.config.META_OVERHEAD_TOKENS, 256)

        # Preserve system message
        system_msg = None
        rest: List[Dict[str, str]] = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system" and system_msg is None:
                system_msg = {"role": "system", "content": self.compress_text(content, max_tokens=min(budget, 2048))}
            else:
                rest.append({"role": role, "content": content})

        # Reverse-accumulate from the end until budget fits
        acc: List[Dict[str, str]] = []
        used = estimate_tokens(system_msg["content"]) if system_msg else 0
        for m in reversed(rest):
            c = m.get("content", "")
            c_comp = self.compress_text(c, max_tokens=min(budget // 2, 4096))
            t = estimate_tokens(c_comp)
            if used + t > budget:
                # Try stricter compression for user messages
                if m.get("role") == "user":
                    c_comp = self._head_tail_keep(c_comp, max_tokens=max(budget - used, 128))
                    t = estimate_tokens(c_comp)
                if used + t > budget:
                    break
            acc.append({"role": m.get("role"), "content": c_comp})
            used += t
        acc.reverse()

        out = []
        if system_msg:
            out.append(system_msg)
        out.extend(acc)
        # Ensure last message is from user; if not, keep last turn user-only
        if out and out[-1].get("role") != "user":
            # Drop trailing assistant if any to ensure the model answers
            for i in range(len(out) - 1, -1, -1):
                if out[i].get("role") == "user":
                    out = out[: i + 1]
                    break
        return out if out else messages

    def condense_messages_for_batch(self, messages: List[Dict[str, str]]) -> str:
        # Build a compact representation suitable for single-turn processing
        # Prefer the last user message and include brief context lines
        lines = []
        sys = self.extract_system_prompt(messages)
        if sys:
            lines.append(f"[System]\n{sys.strip()}")
        # Include up to last 4 messages excluding system
        context = [m for m in messages if m.get("role") != "system"][-4:]
        for m in context:
            role = m.get("role")
            content = m.get("content", "").strip()
            content = self.compress_text(content, max_tokens=1024)
            lines.append(f"[{role}]\n{content}")
        # Mark expected action
        lines.append("[Task]\nProvide the best possible assistant reply for the above conversation.")
        return "\n\n".join(lines)

