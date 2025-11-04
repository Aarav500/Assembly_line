import textwrap
from .base import Provider

class MockProvider(Provider):
    def generate(self, prompt: str, model_name: str, max_output_tokens: int) -> str:
        # Deterministic, simple transformation for demo.
        snippet = prompt.strip().replace("\n", " ")
        snippet = snippet[:200]
        return textwrap.shorten(
            f"[MOCK:{model_name}] Echo: {snippet}",
            width=max(32, int(max_output_tokens * 4)),
            placeholder="...",
        )

