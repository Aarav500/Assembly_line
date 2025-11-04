import io
import json
import logging
import os
from urllib.parse import urlencode

from flask import Flask, jsonify, request, abort, redirect

from .config import config
from .storage import storage
from .utils import is_image_content_type, make_thumbnails

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
app.config["SECRET_KEY"] = config.SECRET_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_api_token_from_request() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1].strip()
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key.strip()
    return None


def require_auth():
    if not config.API_TOKENS:
        return  # No auth configured
    token = get_api_token_from_request()
    if not token or token not in config.API_TOKENS:
        abort(401, description="Unauthorized")


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.post("/api/files/presign-upload")
def presign_upload():
    require_auth()
    payload = request.get_json(silent=True) or {}
    filename = payload.get("filename") or request.values.get("filename")
    content_type = payload.get("content_type") or request.values.get("content_type")
    public = payload.get("public") if payload.get("public") is not None else request.values.get("public")
    public = str(public).lower() in ("1", "true", "yes") if public is not None else config.DEFAULT_ACL_PUBLIC
    expires_in = int(payload.get("expires_in") or request.values.get("expires_in") or config.PRESIGN_EXPIRES)
    prefix = payload.get("prefix") or request.values.get("prefix") or config.DEFAULT_PREFIX
    max_size = payload.get("max_size") or request.values.get("max_size")
    max_size = int(max_size) if max_size else None

    key = payload.get("key") or request.values.get("key")
    if not key:
        key = storage.generate_key(filename=filename, prefix=prefix)

    if not content_type and filename:
        content_type = storage.guess_content_type(filename)

    post = storage.create_presigned_post(
        key=key,
        content_type=content_type,
        public=public,
        expires_in=expires_in,
        max_size=max_size or config.MAX_CONTENT_LENGTH,
    )

    response = {
        "key": key,
        "upload_url": post["url"],
        "fields": post["fields"],
        "public": public,
        "cdn_url": storage.object_url(key, public=True) if public else None,
    }
    return jsonify(response)


@app.get("/api/files/presign-download")
def presign_download():
    require_auth()
    key = request.args.get("key")
    if not key:
        abort(400, description="Missing key")
    expires_in = int(request.args.get("expires_in") or config.PRESIGN_EXPIRES)
    response_content_type = request.args.get("response_content_type")
    url = storage.create_presigned_get(key, expires_in=expires_in, response_content_type=response_content_type)
    return jsonify({"key": key, "url": url, "expires_in": expires_in})


@app.post("/api/files/upload")
def upload_server_side():
    require_auth()
    if "file" not in request.files:
        abort(400, description="Missing file field")
    f = request.files["file"]
    filename = f.filename
    content_type = request.form.get("content_type") or f.mimetype or storage.guess_content_type(filename)
    public = request.form.get("public")
    public = str(public).lower() in ("1", "true", "yes") if public is not None else config.DEFAULT_ACL_PUBLIC
    prefix = request.form.get("prefix") or config.DEFAULT_PREFIX
    create_thumbnails = str(request.form.get("thumbnails") or "false").lower() in ("1", "true", "yes")

    key = request.form.get("key") or storage.generate_key(filename=filename, prefix=prefix)

    data = f.read()
    obj = storage.upload_bytes(data, key=key, content_type=content_type, public=public, cache_control="public, max-age=31536000" if public else None)

    thumbs = []
    if create_thumbnails and is_image_content_type(content_type):
        for size, bytes_ in make_thumbnails(data, config.THUMBNAIL_SIZES).items():
            tkey = f"{key.rsplit('.', 1)[0]}_thumb_{size}.jpg"
            t = storage.upload_bytes(bytes_, key=tkey, content_type="image/jpeg", public=public, cache_control="public, max-age=31536000" if public else None)
            thumbs.append({"size": size, **t})

    return jsonify({"uploaded": obj, "thumbnails": thumbs})


@app.post("/api/files/thumbnails")
def create_thumbnails_endpoint():
    require_auth()
    payload = request.get_json(silent=True) or {}
    key = payload.get("key")
    if not key:
        abort(400, description="Missing key")
    # Fetch original object
    try:
        resp = storage.client.get_object(Bucket=storage.bucket, Key=key)
        content_type = resp.get("ContentType")
        body = resp["Body"].read()
    except Exception as e:
        abort(404, description=f"Object not found: {e}")

    if not is_image_content_type(content_type):
        abort(400, description="Not an image content type")

    public = str(payload.get("public")).lower() in ("1", "true", "yes") if payload.get("public") is not None else config.DEFAULT_ACL_PUBLIC
    sizes = payload.get("sizes") or config.THUMBNAIL_SIZES

    thumbs = []
    for size, bytes_ in make_thumbnails(body, sizes).items():
        tkey = f"{key.rsplit('.', 1)[0]}_thumb_{size}.jpg"
        t = storage.upload_bytes(bytes_, key=tkey, content_type="image/jpeg", public=public, cache_control="public, max-age=31536000" if public else None)
        thumbs.append({"size": size, **t})

    return jsonify({"key": key, "thumbnails": thumbs})


@app.get("/api/files/url")
def resolve_url():
    require_auth()
    key = request.args.get("key")
    if not key:
        abort(400, description="Missing key")
    public = str(request.args.get("public") or str(config.DEFAULT_ACL_PUBLIC)).lower() in ("1", "true", "yes")
    if public:
        return jsonify({"key": key, "url": storage.object_url(key, public=True)})
    else:
        url = storage.create_presigned_get(key)
        return jsonify({"key": key, "url": url})


@app.get("/files/<path:key>")
def access_file(key: str):
    # No auth: this endpoint is for public linking/redirecting only
    # If CDN or public object is available -> redirect there; else -> presigned URL redirect
    public_url = storage.object_url(key, public=True)
    if config.CDN_BASE_URL:
        return redirect(public_url, code=302)
    # Try HEAD to see if object is public
    head = storage.head_object(key)
    if head and head.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
        # We don't truly know if public, but attempt direct
        return redirect(public_url, code=302)
    # Fallback to signed
    signed = storage.create_presigned_get(key)
    return redirect(signed, code=302)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=config.DEBUG)

