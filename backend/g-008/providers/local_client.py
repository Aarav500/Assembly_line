import time
import random
from utils.tokenizer import estimate_tokens

class LocalClient:
    def __init__(self, config):
        self.config = config

    def _toy_generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        # Simple, deterministic local stub: extract key points, limit length
        words = prompt.strip().split()
        if not words:
            return "(no content)"
        # Take first N words as a 'summary', shuffle a bit if temperature > 0.5
        n = max(8, min(len(words), max_tokens))
        selected = words[:n]
        if temperature and temperature > 0.5:
            random.seed(len(prompt))
            random.shuffle(selected)
        result = ' '.join(selected)
        return f"[LOCAL:{self.config.local_model_name}] {result}"

    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.7) -> str:
        # Simulate local latency
        simulated_ms = max(5, min(self.config.latency_local_ms_est, 80))
        time.sleep(simulated_ms / 1000.0)
        # Ensure we don't exceed local max output tokens
        max_out = min(max_tokens, self.config.local_max_output_tokens)
        out = self._toy_generate(prompt, max_out, temperature)
        # Enforce token limit
        out_tokens = estimate_tokens(out)
        if out_tokens > max_out:
            # truncate roughly to token limit
            out_words = out.split()
            out = ' '.join(out_words[:max_out])
        return out

