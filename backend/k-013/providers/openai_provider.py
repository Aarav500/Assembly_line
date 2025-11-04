import os
from .base import Provider

class OpenAIProvider(Provider):
    def __init__(self):
        from openai import OpenAI  # lazy import
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=api_key)

    def generate(self, prompt: str, model_name: str, max_output_tokens: int) -> str:
        # Use chat.completions for broad compatibility
        resp = self.client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_output_tokens,
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""

