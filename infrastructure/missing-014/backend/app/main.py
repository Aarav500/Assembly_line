import json
from typing import Dict
import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from .config import settings
from .database import Base, engine, get_db
from .i18n import detect_language_from_request, seed_defaults
from .crud import get_translations_dict, upsert_many
from .schemas import (
    TranslationUpsertPayload,
    TranslateRequest,
    TranslateResponse,
    LocaleDetectResponse,
)

app = FastAPI(title="i18n Translation Management API")

# CORS
origins = settings.ALLOW_ORIGINS if settings.ALLOW_ORIGINS != ["*"] else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:  # type: ignore
        seed_defaults(db)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/detect-locale", response_model=LocaleDetectResponse)
async def detect_locale(request: Request):
    lang = detect_language_from_request(request)
    resp = JSONResponse({"language": lang, "from": "server"})
    resp.set_cookie("i18next", lang, max_age=60 * 60 * 24 * 365, path="/")
    return resp


@app.get("/locales/{lng}/{ns}.json")
async def get_locale_bundle(lng: str, ns: str, db: Session = Depends(get_db)):
    if lng not in settings.SUPPORTED_LANGUAGES:
        # Fallback to default language
        lng = settings.DEFAULT_LANGUAGE
    data = get_translations_dict(db, language=lng, namespace=ns)
    return JSONResponse(content=data)


@app.post("/locales/add/{lng}/{ns}")
async def add_missing(lng: str, ns: str, request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object of key: defaultValue pairs")

    items = []
    for key, default_value in payload.items():
        if not isinstance(key, str):
            continue
        value = default_value if isinstance(default_value, str) else str(default_value)
        items.append((lng, ns, key, value))

    if not items:
        return {"status": "no_items"}
    upsert_many(db, items)
    return {"status": "ok", "count": len(items)}


@app.get("/api/translations")
async def list_translations(language: str, namespace: str = "common", db: Session = Depends(get_db)):
    data = get_translations_dict(db, language=language, namespace=namespace)
    return {"language": language, "namespace": namespace, "items": data}


@app.put("/api/translations")
async def update_translations(payload: TranslationUpsertPayload, db: Session = Depends(get_db)):
    items = []
    for itm in payload.items:
        items.append((itm.language, itm.namespace, itm.key, itm.value))
    upsert_many(db, items)
    return {"status": "updated", "count": len(items)}


@app.post("/api/translate", response_model=TranslateResponse)
async def translate_text(req: TranslateRequest):
    # Optional dynamic translation via LibreTranslate-compatible API
    if not settings.TRANSLATION_PROVIDER_URL:
        # No provider configured, return passthrough
        return TranslateResponse(
            translated_text=req.text,
            provider="none",
            detected_source_language=req.source or None,
        )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            payload = {
                "q": req.text,
                "source": req.source or "auto",
                "target": req.target,
                "format": "text",
            }
            headers = {}
            if settings.TRANSLATION_PROVIDER_API_KEY:
                headers["Authorization"] = f"Bearer {settings.TRANSLATION_PROVIDER_API_KEY}"
            r = await client.post(settings.TRANSLATION_PROVIDER_URL, data=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            # LibreTranslate returns { translatedText: "..." }
            translated = data.get("translatedText") or data.get("translated_text") or req.text
            detected = data.get("detectedLanguage") or data.get("detected_language")
            return TranslateResponse(
                translated_text=translated,
                provider=settings.TRANSLATION_PROVIDER_URL,
                detected_source_language=detected,
            )
    except Exception as e:
        # Fallback to original text on error
        return TranslateResponse(
            translated_text=req.text,
            provider="error",
            detected_source_language=req.source or None,
        )

