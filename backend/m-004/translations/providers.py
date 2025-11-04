import os
from typing import Optional, Dict
from config import TRANSLATION_PROVIDER, OPENAI_MODEL


class BaseTranslationProvider:
    name = "base"

    def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None, context: Optional[Dict] = None) -> str:
        raise NotImplementedError


class DummyProvider(BaseTranslationProvider):
    name = "dummy"

    def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None, context: Optional[Dict] = None) -> str:
        # A simple stand-in provider that echoes with language tag
        return f"[{target_lang}] {text}"


class OpenAIProvider(BaseTranslationProvider):
    name = "openai"

    def __init__(self, model: Optional[str] = None):
        self.model = model or OPENAI_MODEL
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError("openai package not installed. Add openai to requirements.") from e
        self._client = OpenAI()

    def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None, context: Optional[Dict] = None) -> str:
        # System prompt emphasizes preservation of placeholders and tags
        system = (
            "You are a professional localization engine. Translate the user-provided UI string to the specified language. "
            "Strictly preserve placeholders (like {name}, {{variable}}, %s, %1$s) and HTML/XML tags. "
            "Do not add quotes or commentary. Return only the translated string."
        )
        lang_hint = f"Translate to {target_lang}."
        ctx = context or {}
        source_lang = source_lang or ctx.get("source_lang") or ""
        keys = ctx.get("placeholders", [])
        glossary = ctx.get("glossary")
        extra = ""
        if source_lang:
            extra += f" Source language is {source_lang}."
        if keys:
            extra += f" Preserve placeholders: {', '.join(keys)}."
        if glossary:
            extra += f" Use glossary terms where applicable: {glossary}."

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{lang_hint}{extra}\n\n{text}"},
        ]
        try:
            # Using chat completions
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
            )
            out = resp.choices[0].message.content.strip()
            return out
        except Exception as e:
            # Fallback to dummy behavior on failure to avoid hard crashes
            return f"[{target_lang}] {text}"


def get_translation_provider() -> BaseTranslationProvider:
    provider = TRANSLATION_PROVIDER.lower()
    if provider == "openai" or (provider == "auto" and os.environ.get("OPENAI_API_KEY")):
        try:
            return OpenAIProvider()
        except Exception:
            return DummyProvider()
    return DummyProvider()

