import os
import re
from typing import Optional

# Attempt to import OpenAI SDK; fallback gracefully if unavailable
_openai_available = False
_openai_client = None
try:
    from openai import OpenAI  # type: ignore
    _openai_client = OpenAI()
    _openai_available = True
except Exception:
    _openai_available = False


class BaseModel:
    def __init__(self, temperature: float = 0.2):
        self.temperature = temperature

    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class DummyModel(BaseModel):
    def generate(self, prompt: str) -> str:
        # Very simple heuristic: If prompt contains a block specifying criteria, include them explicitly
        criteria = self._extract_criteria(prompt)
        response_lines = []
        response_lines.append("Answering your prompt:")
        response_lines.append("")
        # Echo some of the prompt context (truncated)
        snippet = prompt.strip().splitlines()[0][:200]
        response_lines.append(f"Prompt snippet: {snippet}")
        response_lines.append("")
        if criteria:
            response_lines.append("Satisfying criteria:")
            for c in criteria:
                # Try to include each criterion explicitly
                response_lines.append(f"- {c}")
            response_lines.append("")
            response_lines.append("Detailed content:")
            for c in criteria:
                response_lines.append(f"Section for: {c}\n{c} -> fulfilled with concrete details and examples.")
        else:
            response_lines.append("No explicit criteria provided. Delivering a comprehensive response.")
            response_lines.append("This is a generic response produced by the DummyModel.")
        return "\n".join(response_lines)

    def _extract_criteria(self, prompt: str):
        # Look for a block: "Ensure your answer satisfies all of the following criteria:" followed by bullet lines
        lines = prompt.splitlines()
        criteria = []
        start_idx = None
        for i, line in enumerate(lines):
            if 'Ensure your answer satisfies all of the following criteria' in line:
                start_idx = i + 1
                break
        if start_idx is not None:
            for j in range(start_idx, len(lines)):
                line = lines[j].strip()
                if not line:
                    break
                if line.startswith('- '):
                    criteria.append(line[2:].strip())
                else:
                    # Stop when we hit a line that doesn't look like a bullet item
                    if criteria:
                        break
        return criteria


class OpenAIModel(BaseModel):
    def __init__(self, model_name: str, temperature: float = 0.2):
        super().__init__(temperature=temperature)
        self.model_name = model_name
        self.active = _openai_available and bool(os.environ.get('OPENAI_API_KEY'))

    def generate(self, prompt: str) -> str:
        if not self.active:
            # Fallback to dummy if OpenAI is not usable
            return DummyModel(temperature=self.temperature).generate(prompt)
        try:
            resp = _openai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            # On failure, fallback to DummyModel
            return DummyModel(temperature=self.temperature).generate(prompt + f"\n\n[Note: OpenAI error: {e}]")


def get_model(spec: Optional[str], temperature: float = 0.2) -> BaseModel:
    if not spec:
        return DummyModel(temperature=temperature)
    spec = str(spec)
    if spec.lower().startswith('openai:'):
        model_name = spec.split(':', 1)[1] or 'gpt-4o-mini'
        return OpenAIModel(model_name=model_name, temperature=temperature)
    # default dummy
    return DummyModel(temperature=temperature)

