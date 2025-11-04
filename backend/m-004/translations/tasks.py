from typing import Dict, List, Optional
from .providers import BaseTranslationProvider
from .quality import evaluate_quality, extract_placeholders
from .storage import upsert_translation_entry


def translate_all_missing(project: Dict, provider: BaseTranslationProvider, threshold: float, *, target_languages: Optional[List[str]] = None, force: bool = False) -> Dict:
    source_lang = project.get("source_lang", "en")
    strings: Dict[str, str] = project.get("strings", {})
    langs = target_languages or project.get("languages", [])

    total = 0
    translated = 0
    auto_approved = 0
    flagged = 0

    for lang in langs:
        entries = project.setdefault("translations", {}).setdefault(lang, {})
        for key, src in strings.items():
            total += 1
            existing = entries.get(key)
            if existing and existing.get("text") and existing.get("status") == "approved" and not force:
                continue
            if existing and existing.get("text") and existing.get("status") in ("auto_approved", "edited") and not force:
                continue
            context = {
                "source_lang": source_lang,
                "key": key,
                "placeholders": extract_placeholders(src),
            }
            tgt = provider.translate(src, lang, source_lang=source_lang, context=context)
            translated += 1
            quality = evaluate_quality(src, tgt)
            issues = quality["issues"]
            score = quality["score"]
            status = "auto_approved" if score >= threshold else "flagged"
            if status == "auto_approved":
                auto_approved += 1
            else:
                flagged += 1
            upsert_translation_entry(project, lang, key, text=tgt, status=status, score=score, issues=issues)

    return {
        "total_pairs": total,
        "attempted": translated,
        "auto_approved": auto_approved,
        "flagged": flagged,
        "threshold": threshold,
        "provider": getattr(provider, 'name', 'unknown'),
    }

