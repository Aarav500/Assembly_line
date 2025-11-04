import os
import re
from typing import Dict, List, Set
from urllib.parse import urlparse


TAG_SRC_PATTERNS = [
    re.compile(r'<script[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'<img[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'<iframe[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'<link[^>]*rel=["\'](?:stylesheet|preload)["\'][^>]*href=["\']([^"\']+)["\']', re.IGNORECASE),
]
INLINE_SCRIPT_PATTERN = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', re.IGNORECASE | re.DOTALL)
INLINE_STYLE_TAG_PATTERN = re.compile(r'<style[^>]*>(.*?)</style>', re.IGNORECASE | re.DOTALL)
INLINE_STYLE_ATTR_PATTERN = re.compile(r'style=\".*?\"|style=\'.*?\'', re.IGNORECASE | re.DOTALL)

# CSS url(...) and @import
CSS_URL_PATTERN = re.compile(r'url\(([^)]+)\)', re.IGNORECASE)
CSS_IMPORT_PATTERN = re.compile(r'@import\s+(?:url\()?([^)\s;]+)\)?', re.IGNORECASE)

# JavaScript network patterns (fetch/xhr/ws)
JS_FETCH_PATTERN = re.compile(r'fetch\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
JS_XHR_PATTERN = re.compile(r'open\(\s*["\'](?:GET|POST|PUT|PATCH|DELETE|OPTIONS)["\']\s*,\s*["\']([^"\']+)["\']', re.IGNORECASE)
JS_WS_PATTERN = re.compile(r'new\s+WebSocket\(\s*["\'](wss?://[^"\']+)["\']', re.IGNORECASE)

HTTP_URL_PATTERN = re.compile(r'^(https?:|wss?:|data:)', re.IGNORECASE)


def _origin_of(url: str) -> str:
    url = url.strip().strip('"\'')
    if url.startswith("//"):
        # scheme-relative, treat as https
        parsed = urlparse("https:" + url)
    else:
        parsed = urlparse(url)
    if parsed.scheme in ("http", "https", "ws", "wss"):
        return f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else url
    if url.startswith("data:"):
        return "data:"
    if url.startswith("blob:"):
        return "blob:"
    return None


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _gather_files(paths: List[str]) -> List[str]:
    files = []
    for p in paths:
        if not os.path.exists(p):
            continue
        if os.path.isfile(p):
            files.append(p)
        else:
            for root, _, filenames in os.walk(p):
                for name in filenames:
                    if any(name.lower().endswith(ext) for ext in (".html", ".htm", ".js", ".css")):
                        files.append(os.path.join(root, name))
    return files


def suggest_csp_policy_from_paths(paths: List[str]) -> Dict:
    script_src: Set[str] = set(["'self'"])
    style_src: Set[str] = set(["'self'"])
    img_src: Set[str] = set(["'self'"])
    font_src: Set[str] = set(["'self'"])
    connect_src: Set[str] = set(["'self'"])
    frame_src: Set[str] = set(["'self'"])

    object_src: Set[str] = set(["'none'"])
    base_uri: Set[str] = set(["'self'"])
    form_action: Set[str] = set(["'self'"])

    upgrade_insecure_requests = False
    block_all_mixed_content = False

    found_inline_script = False
    found_inline_style = False

    for file_path in _gather_files(paths):
        content = _read_file(file_path)
        lower = file_path.lower()

        # HTML tag src/href
        if lower.endswith(('.html', '.htm')):
            for pat in TAG_SRC_PATTERNS:
                for m in pat.findall(content):
                    origin = _origin_of(m)
                    if not origin:
                        continue
                    if origin == "data:":
                        if 'img' in pat.pattern:
                            img_src.add("data:")
                        elif 'link' in pat.pattern:
                            style_src.add("data:")
                        elif 'script' in pat.pattern:
                            script_src.add("data:")
                    elif 'script' in pat.pattern:
                        script_src.add(origin)
                    elif 'img' in pat.pattern:
                        img_src.add(origin)
                    elif 'iframe' in pat.pattern:
                        frame_src.add(origin)
                    elif 'link' in pat.pattern:
                        style_src.add(origin)

            # Inline detection
            if INLINE_SCRIPT_PATTERN.search(content):
                found_inline_script = True
            if INLINE_STYLE_TAG_PATTERN.search(content) or INLINE_STYLE_ATTR_PATTERN.search(content):
                found_inline_style = True

        # CSS
        if lower.endswith('.css'):
            for m in CSS_URL_PATTERN.findall(content) + CSS_IMPORT_PATTERN.findall(content):
                m = m.strip().strip('"\'')
                origin = _origin_of(m)
                if not origin:
                    continue
                if origin == "data:":
                    # data URIs commonly for fonts/images
                    font_src.add("data:")
                    img_src.add("data:")
                else:
                    # Heuristic: fonts/images via CSS
                    if any(ext in m.lower() for ext in ['.woff', '.woff2', '.ttf', '.otf', '.eot']):
                        font_src.add(origin)
                    else:
                        img_src.add(origin)

        # JS
        if lower.endswith('.js'):
            for pat in (JS_FETCH_PATTERN, JS_XHR_PATTERN):
                for m in pat.findall(content):
                    origin = _origin_of(m)
                    if origin:
                        connect_src.add(origin)
            for m in JS_WS_PATTERN.findall(content):
                origin = _origin_of(m)
                if origin:
                    connect_src.add(origin)

    if found_inline_script:
        script_src.add("'unsafe-inline'")
    if found_inline_style:
        style_src.add("'unsafe-inline'")

    suggestion = {
        "default_src": ["'self'"],
        "script_src": sorted(script_src),
        "style_src": sorted(style_src),
        "img_src": sorted(img_src),
        "font_src": sorted(font_src),
        "connect_src": sorted(connect_src),
        "frame_src": sorted(frame_src),
        "object_src": sorted(object_src),
        "base_uri": sorted(base_uri),
        "form_action": sorted(form_action),
        "upgrade_insecure_requests": upgrade_insecure_requests,
        "block_all_mixed_content": block_all_mixed_content,
        "report_uri": None,
        "report_to": None,
    }
    return suggestion

