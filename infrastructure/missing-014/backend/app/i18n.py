from typing import Dict, List, Optional
from fastapi import Request
from sqlalchemy.orm import Session
from .config import settings
from .crud import get_translations, upsert_many
from .models import Translation


DEFAULT_SEED: Dict[str, Dict[str, str]] = {
    "common": {
        "title": "Internationalization Example",
        "welcome": "Welcome, {{name}}!",
        "description": "This is a demo showing multi-language support with i18next and FastAPI.",
        "change_language": "Change language",
        "current_language": "Current language: {{lng}}",
        "manage_translations": "Manage translations",
        "save": "Save",
        "add_key": "Add key",
        "key": "Key",
        "value": "Value",
        "namespace": "Namespace",
        "language": "Language",
        "load": "Load",
        "updated": "Updated successfully",
        "missing_translation_added": "Missing translations added",
    }
}

DEFAULT_TRANSLATIONS: Dict[str, Dict[str, Dict[str, str]]] = {
    "en": DEFAULT_SEED,
    "es": {
        "common": {
            "title": "Ejemplo de Internacionalización",
            "welcome": "¡Bienvenido, {{name}}!",
            "description": "Esta es una demo que muestra soporte multilenguaje con i18next y FastAPI.",
            "change_language": "Cambiar idioma",
            "current_language": "Idioma actual: {{lng}}",
            "manage_translations": "Gestionar traducciones",
            "save": "Guardar",
            "add_key": "Agregar clave",
            "key": "Clave",
            "value": "Valor",
            "namespace": "Espacio de nombres",
            "language": "Idioma",
            "load": "Cargar",
            "updated": "Actualizado con éxito",
            "missing_translation_added": "Traducciones faltantes agregadas",
        }
    },
    "fr": {
        "common": {
            "title": "Exemple d'internationalisation",
            "welcome": "Bienvenue, {{name}} !",
            "description": "Ceci est une démo montrant la prise en charge multilingue avec i18next et FastAPI.",
            "change_language": "Changer de langue",
            "current_language": "Langue actuelle : {{lng}}",
            "manage_translations": "Gérer les traductions",
            "save": "Enregistrer",
            "add_key": "Ajouter une clé",
            "key": "Clé",
            "value": "Valeur",
            "namespace": "Espace de noms",
            "language": "Langue",
            "load": "Charger",
            "updated": "Mis à jour avec succès",
            "missing_translation_added": "Traductions manquantes ajoutées",
        }
    },
}


def detect_language_from_request(request: Request) -> str:
    # Priority: query param lng -> cookie i18next -> Accept-Language -> default
    qlng = request.query_params.get("lng")
    if qlng and qlng in settings.SUPPORTED_LANGUAGES:
        return qlng
    clng = request.cookies.get("i18next")
    if clng and clng in settings.SUPPORTED_LANGUAGES:
        return clng
    accept = request.headers.get("Accept-Language", "").lower()
    candidates: List[str] = []
    for part in accept.split(","):
        lang = part.split(";")[0].strip()
        if not lang:
            continue
        # match primary subtag
        primary = lang.split("-")[0]
        candidates.extend([lang, primary])
    for cand in candidates:
        if cand in settings.SUPPORTED_LANGUAGES:
            return cand
    return settings.DEFAULT_LANGUAGE


def seed_defaults(db: Session) -> None:
    # If table empty, seed defaults
    any_row = db.query(Translation).first()
    if any_row:
        return
    items = []
    for lng in settings.SUPPORTED_LANGUAGES:
        data = DEFAULT_TRANSLATIONS.get(lng) or DEFAULT_TRANSLATIONS.get("en")
        for ns, pairs in data.items():
            for k, v in pairs.items():
                items.append((lng, ns, k, v))
    upsert_many(db, items)

