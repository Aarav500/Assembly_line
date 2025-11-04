import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from ideater.introspector import introspect_database
from ideater.mapping import build_entity_mapping
from ideater.utils import mask_db_url

app = Flask(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ideater")


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


@app.post("/introspect")
def introspect():
    try:
        data = request.get_json(force=True, silent=False) or {}
        db_url = data.get("database_url") or os.getenv("IDEATER_DATABASE_URL")
        if not db_url:
            return (
                jsonify({
                    "error": "missing_database_url",
                    "message": "Provide 'database_url' in JSON body or set IDEATER_DATABASE_URL env var."
                }),
                400,
            )
        schemas = data.get("schemas")
        include_views = bool(data.get("include_views", True))
        with_backrefs = bool(data.get("with_backrefs", True))
        exclude_system_schemas = bool(data.get("exclude_system_schemas", True))

        raw = introspect_database(
            db_url=db_url,
            schemas=schemas,
            include_views=include_views,
            exclude_system_schemas=exclude_system_schemas,
        )
        mapping = build_entity_mapping(
            raw,
            masked_db_url=mask_db_url(db_url),
            with_backrefs=with_backrefs,
        )
        return jsonify(mapping)
    except Exception as exc:
        logger.exception("introspection_failed")
        return (
            jsonify({
                "error": "introspection_failed",
                "message": str(exc),
            }),
            500,
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))



def create_app():
    return app
