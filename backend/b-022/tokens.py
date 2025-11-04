import re
import json
from copy import deepcopy

DEFAULT_TOKENS = {
    "colors": {
        "primary": "#5b6cff",
        "secondary": "#ff6b6b",
        "background": "#ffffff",
        "surface": "#f5f7fb",
        "text": {
            "primary": "#111827",
            "secondary": "#4b5563",
            "inverse": "#ffffff"
        },
        "states": {
            "success": "#10b981",
            "warning": "#f59e0b",
            "error": "#ef4444",
            "info": "#3b82f6"
        }
    },
    "typography": {
        "fontFamilyBase": "Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
        "scale": {
            "xs": "12px",
            "sm": "14px",
            "base": "16px",
            "lg": "18px",
            "xl": "20px",
            "2xl": "24px",
            "3xl": "30px",
            "4xl": "36px"
        },
        "lineHeights": {
            "tight": 1.2,
            "snug": 1.35,
            "normal": 1.5,
            "relaxed": 1.65
        },
        "fontWeights": {
            "regular": 400,
            "medium": 500,
            "semibold": 600,
            "bold": 700
        }
    },
    "radius": {
        "sm": "4px",
        "md": "8px",
        "lg": "12px",
        "xl": "16px",
        "pill": "999px"
    },
    "spacing": {
        "xs": "4px",
        "sm": "8px",
        "md": "12px",
        "lg": "16px",
        "xl": "24px",
        "2xl": "32px"
    },
    "shadows": {
        "sm": "0 1px 2px rgba(0,0,0,0.06)",
        "md": "0 4px 10px rgba(0,0,0,0.08)",
        "lg": "0 10px 24px rgba(0,0,0,0.12)"
    }
}


HEX_COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def is_color(value: str) -> bool:
    if not isinstance(value, str):
        return False
    return bool(HEX_COLOR_RE.match(value.strip()))


def sanitize_tokens(tokens, fallback=None):
    if not isinstance(tokens, dict):
        return deepcopy(fallback or DEFAULT_TOKENS)

    def _sanitize(node):
        if isinstance(node, dict):
            clean = {}
            for k, v in node.items():
                if not isinstance(k, str):
                    k = str(k)
                clean[k] = _sanitize(v)
            return clean
        elif isinstance(node, list):
            return [_sanitize(v) for v in node if isinstance(v, (dict, list, str, int, float))]
        elif isinstance(node, (int, float)):
            return node
        elif isinstance(node, str):
            s = node.strip()
            # normalize hex colors when applicable
            if is_color(s):
                return s.lower()
            return s
        else:
            # drop unsupported types
            return None

    merged = _sanitize(tokens)

    # Shallow-merge onto defaults to ensure required structure
    base = deepcopy(fallback or DEFAULT_TOKENS)

    def deep_merge(dst, src):
        if isinstance(dst, dict) and isinstance(src, dict):
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    deep_merge(dst[k], v)
                else:
                    dst[k] = v
        return dst

    return deep_merge(base, merged)


RENAME_TOPLEVEL = {
    "colors": "color",
    "typography": "type",
    "spacing": "space",
    "radius": "radius",
    "shadows": "shadow",
}


def sanitize_key_part(part: str) -> str:
    # convert camelCase to kebab-case and remove invalid chars
    # Insert hyphen before capitals
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", part)
    s = s.replace("_", "-")
    s = re.sub(r"[^a-zA-Z0-9-]", "-", s)
    return s.lower()


def flatten_tokens(tokens):
    flat = {}

    def _walk(node, path=None):
        path = path or []
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, path + [k])
        else:
            # leaf
            key_parts = []
            for i, p in enumerate(path):
                if i == 0 and p in RENAME_TOPLEVEL:
                    key_parts.append(RENAME_TOPLEVEL[p])
                else:
                    key_parts.append(sanitize_key_part(str(p)))
            var = "--" + "-".join(key_parts)
            flat[var] = node
    _walk(tokens)
    return flat


def to_css_variables_block(tokens, return_map=False):
    flat = flatten_tokens(tokens)
    # ensure stringification for CSS
    lines = [":root {"]
    for k in sorted(flat.keys()):
        v = flat[k]
        if isinstance(v, (int, float)):
            val = str(v)
        else:
            val = str(v)
        lines.append(f"  {k}: {val};")
    lines.append("}")
    block = "\n".join(lines)
    if return_map:
        return block, flat
    return block

