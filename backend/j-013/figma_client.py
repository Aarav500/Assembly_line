import os
import requests
from collections import defaultdict
from config import Config

API_BASE = 'https://api.figma.com/v1'

class FigmaAPIError(Exception):
    pass

def _auth_headers():
    token = Config.FIGMA_TOKEN or os.environ.get('FIGMA_TOKEN')
    if not token:
        raise FigmaAPIError('Missing FIGMA_TOKEN environment variable')
    return {
        'X-Figma-Token': token
    }

def get_file(file_key: str) -> dict:
    url = f"{API_BASE}/files/{file_key}"
    resp = requests.get(url, headers=_auth_headers())
    if resp.status_code != 200:
        raise FigmaAPIError(f"Figma API error: {resp.status_code} {resp.text}")
    return resp.json()

# Helpers for color normalization

def _clamp(n, min_v=0, max_v=255):
    return max(min_v, min(max_v, n))

def _rgba_to_hex(r, g, b, a=1.0):
    r = _clamp(int(round(r)))
    g = _clamp(int(round(g)))
    b = _clamp(int(round(b)))
    if a is None:
        a = 1.0
    a_i = _clamp(int(round(a * 255)))
    if a_i < 255:
        return f"#{r:02X}{g:02X}{b:02X}{a_i:02X}"
    return f"#{r:02X}{g:02X}{b:02X}"

def _paint_to_hex(paint: dict):
    if not paint:
        return None
    if paint.get('type') != 'SOLID':
        return None
    if not paint.get('visible', True):
        return None
    color = paint.get('color', {})
    r = color.get('r', 0) * 255
    g = color.get('g', 0) * 255
    b = color.get('b', 0) * 255
    opacity = paint.get('opacity', 1)
    return _rgba_to_hex(r, g, b, opacity)

def _extract_fill_hex_from_node(node: dict):
    fills = node.get('fills') or []
    for f in fills:
        hexv = _paint_to_hex(f)
        if hexv:
            return hexv
    return None

def _extract_text_style_from_node(node: dict):
    style = node.get('style') or {}
    if not style:
        return None
    res = {}
    if 'fontFamily' in style:
        res['fontFamily'] = style.get('fontFamily')
    if 'fontPostScriptName' in style:
        res['fontPostScriptName'] = style.get('fontPostScriptName')
    if 'fontWeight' in style:
        res['fontWeight'] = style.get('fontWeight')
    if 'fontSize' in style:
        res['fontSize'] = style.get('fontSize')
    if 'lineHeightPx' in style:
        res['lineHeightPx'] = style.get('lineHeightPx')
    elif 'lineHeightPercentFontSize' in style:
        res['lineHeightPercentFontSize'] = style.get('lineHeightPercentFontSize')
    if 'letterSpacing' in style:
        res['letterSpacing'] = style.get('letterSpacing')
    if 'textCase' in style:
        res['textCase'] = style.get('textCase')
    if 'textDecoration' in style:
        res['textDecoration'] = style.get('textDecoration')
    return res or None

def extract_style_values(file_json: dict) -> dict:
    doc = file_json.get('document', {})
    styles_meta = file_json.get('styles', {})  # id -> meta

    # Prepare structures
    color_styles = {}
    text_styles = {}
    # Track best example value for style ids found in tree
    found_colors = {}
    found_texts = {}

    def walk(node: dict):
        # Check if node uses shared styles via 'styles' map
        styles_map = node.get('styles') or {}
        # fill style
        fill_style_id = styles_map.get('fill')
        if fill_style_id:
            hexv = _extract_fill_hex_from_node(node)
            if hexv:
                found_colors.setdefault(fill_style_id, hexv)
        # text style
        text_style_id = styles_map.get('text')
        if text_style_id and node.get('type') == 'TEXT':
            ts = _extract_text_style_from_node(node)
            if ts:
                found_texts.setdefault(text_style_id, ts)

        # Also collect direct fills even if not shared style to understand palette usage
        for child in node.get('children', []) or []:
            walk(child)

    walk(doc)

    # Build token outputs from styles_meta, enriched with found values
    for style_id, meta in styles_meta.items():
        stype = meta.get('style_type')
        name = meta.get('name')
        if stype == 'FILL':
            color_styles[style_id] = {
                'id': style_id,
                'name': name,
                'type': 'color',
                'hex': found_colors.get(style_id)
            }
        elif stype == 'TEXT':
            text_styles[style_id] = {
                'id': style_id,
                'name': name,
                'type': 'text',
                'style': found_texts.get(style_id)
            }

    # Also include colors inferred from paints without shared style (optional palette)
    inferred_palette = set()
    def collect_palette(node: dict):
        hx = _extract_fill_hex_from_node(node)
        if hx:
            inferred_palette.add(hx)
        for child in node.get('children', []) or []:
            collect_palette(child)
    collect_palette(doc)

    return {
        'fileName': file_json.get('name'),
        'figmaFileKey': file_json.get('key'),
        'colors': list(color_styles.values()),
        'textStyles': list(text_styles.values()),
        'inferredPalette': sorted(list(inferred_palette))
    }

