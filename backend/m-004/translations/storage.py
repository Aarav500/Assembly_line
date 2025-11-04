import json
import os
from typing import Dict, List, Optional
from config import DATA_DIR

PROJECT_FILE = os.path.join(DATA_DIR, "project.json")


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(PROJECT_FILE):
        with open(PROJECT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "source_lang": "en",
                "languages": [],
                "strings": {},
                "translations": {}
            }, f, ensure_ascii=False, indent=2)


def load_project() -> Dict:
    ensure_dirs()
    with open(PROJECT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_project(project: Dict):
    with open(PROJECT_FILE, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)


def set_source_strings(project: Dict, strings: Dict[str, str], source_lang: str) -> Dict:
    project["source_lang"] = source_lang
    project["strings"] = strings
    # Remove any translations for keys no longer present
    to_remove: List[str] = []
    for lang, entries in project.get("translations", {}).items():
        keys_to_delete = [k for k in list(entries.keys()) if k not in strings]
        for k in keys_to_delete:
            del entries[k]
    return project


def set_languages(project: Dict, languages: List[str]) -> Dict:
    project["languages"] = languages
    for lang in languages:
        project.setdefault("translations", {}).setdefault(lang, {})
    # Prune languages not in list
    for lang in list(project.get("translations", {}).keys()):
        if lang not in languages:
            del project["translations"][lang]
    return project


def upsert_translation_entry(project: Dict, lang: str, key: str, *, text: Optional[str] = None, status: Optional[str] = None, score: Optional[float] = None, issues: Optional[List[str]] = None):
    translations = project.setdefault("translations", {}).setdefault(lang, {})
    entry = translations.setdefault(key, {})
    if text is not None:
        entry["text"] = text
    if status is not None:
        entry["status"] = status
    if score is not None:
        entry["score"] = score
    if issues is not None:
        entry["issues"] = issues


def export_locales(project: Dict, out_dir: str) -> List[str]:
    files: List[str] = []
    os.makedirs(out_dir, exist_ok=True)
    for lang in project.get("languages", []):
        entries = project.get("translations", {}).get(lang, {})
        payload = {}
        for k, meta in entries.items():
            # Include best available text: approved > auto_approved > edited > flagged > rejected
            txt = meta.get("text")
            if txt is None:
                continue
            payload[k] = txt
        path = os.path.join(out_dir, f"{lang}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        files.append(path)
    # Also write source
    with open(os.path.join(out_dir, f"{project.get('source_lang','en')}.source.json"), "w", encoding="utf-8") as f:
        json.dump(project.get("strings", {}), f, ensure_ascii=False, indent=2)
    return files

