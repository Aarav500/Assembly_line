import time
import hashlib


class InferenceProvider:
    """
    Replace generate() with a real model call (e.g., OpenAI, Hugging Face, custom model).
    This dummy provider simulates latency and returns a deterministic transformation.
    """

    def __init__(self, simulate_latency_seconds=1.5):
        self.simulate_latency_seconds = float(simulate_latency_seconds)

    def generate(self, model: str, input_text: str, params: dict) -> dict:
        # Simulate provider latency
        time.sleep(self.simulate_latency_seconds)
        # Deterministic pseudo-output
        h = hashlib.sha256(input_text.encode("utf-8")).hexdigest()[:12]
        temperature = params.get("temperature", 0)
        top_p = params.get("top_p", 1)
        output = {
            "model": model,
            "input_preview": input_text[:64],
            "input_hash": h,
            "params": {
                "temperature": temperature,
                "top_p": top_p,
            },
            "output": f"processed({model})::{h}::{input_text[::-1]}",
        }
        return output

