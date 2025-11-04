import os

DATA_DIR = os.environ.get("DATA_DIR", "data")
EXPORT_DIR = os.environ.get("EXPORT_DIR", "locales")
QUALITY_THRESHOLD = float(os.environ.get("QUALITY_THRESHOLD", "0.8"))
TRANSLATION_PROVIDER = os.environ.get("TRANSLATION_PROVIDER", "auto")  # auto|openai|dummy
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
SOURCE_LANG_DEFAULT = os.environ.get("SOURCE_LANG", "en")
SUPPORTED_LANGS_DEFAULT = [s for s in os.environ.get("LANGUAGES", "es,fr,de").split(",") if s]

# For clients/providers to access safely
def get_env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "y")

