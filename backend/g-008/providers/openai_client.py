import os
from typing import Tuple, Dict, Any

class OpenAIClient:
    def __init__(self, config):
        self.config = config
        self._client = None
        self._maybe_init()

    def _maybe_init(self):
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            self._client = None
            self._openai_import_error = e
            return
        api_key = self.config.openai_api_key or os.getenv('OPENAI_API_KEY')
        if not api_key:
            self._client = None
            self._openai_import_error = RuntimeError('Missing OPENAI_API_KEY for remote provider')
            return
        self._client = OpenAI(api_key=api_key)
        self._openai_import_error = None

    def _ensure_client(self):
        if self._client is None:
            self._maybe_init()
        if self._client is None:
            raise RuntimeError(f"OpenAI client unavailable: {self._openai_import_error}")

    def _moderate(self, text: str) -> Dict[str, Any]:
        if not self.config.enable_openai_moderation:
            return {"performed": False}
        self._ensure_client()
        try:
            resp = self._client.moderations.create(
                model=self.config.openai_moderation_model,
                input=text
            )
            result = resp.results[0] if getattr(resp, 'results', None) else {}
            flagged = bool(getattr(result, 'flagged', False))
            categories = getattr(result, 'categories', {})
            return {"performed": True, "flagged": flagged, "categories": categories}
        except Exception:
            # If moderation fails, do not block, but report
            return {"performed": True, "flagged": False, "error": "moderation_failed"}

    def generate(self, prompt: str, max_tokens: int, temperature: float, model: str = None) -> Tuple[str, str, Dict[str, int]]:
        self._ensure_client()
        used_model = model or self.config.default_openai_model

        # Optional moderation before generation
        _ = self._moderate(prompt)

        try:
            # Use Chat Completions API
            resp = self._client.chat.completions.create(
                model=used_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = resp.choices[0].message.content
            usage = resp.usage
            usage_dict = {
                'input_tokens': getattr(usage, 'prompt_tokens', None) or getattr(usage, 'input_tokens', None) or 0,
                'output_tokens': getattr(usage, 'completion_tokens', None) or getattr(usage, 'output_tokens', None) or 0,
                'total_tokens': getattr(usage, 'total_tokens', None) or 0
            }
            return text, used_model, usage_dict
        except Exception as e:
            # Attempt fallback to Responses API (in case model only supported there)
            try:
                resp = self._client.responses.create(
                    model=used_model,
                    input=prompt,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
                # Extract text from responses API
                out_text = []
                for item in resp.output or []:
                    if getattr(item, 'type', '') == 'message':
                        for c in getattr(item, 'content', []) or []:
                            if getattr(c, 'type', '') == 'output_text':
                                out_text.append(getattr(c, 'text', ''))
                text = '\n'.join(out_text) if out_text else str(resp)
                # Usage may not be available; return zeros
                usage_dict = {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'total_tokens': 0
                }
                return text, used_model, usage_dict
            except Exception as e2:
                raise RuntimeError(f"OpenAI generation failed: {e} | fallback failed: {e2}")

