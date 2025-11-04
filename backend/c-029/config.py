import os

ALLOWED_ROOT = os.environ.get("ALLOWED_ROOT", os.getcwd())

SIZE_THRESHOLDS = {
    "js_large_bytes": int(os.environ.get("JS_LARGE_BYTES", 200 * 1024)),  # 200KB
    "css_large_bytes": int(os.environ.get("CSS_LARGE_BYTES", 150 * 1024)),  # 150KB
    "img_large_bytes": int(os.environ.get("IMG_LARGE_BYTES", 100 * 1024)),  # 100KB
}

ANALYZE_EXTENSIONS = {
    "html": {".html", ".htm", ".j2", ".jinja2", ".tpl"},
    "js": {".js", ".mjs", ".cjs"},
    "css": {".css"},
    "images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg"},
}

