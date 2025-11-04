import requests
from typing import Dict, Any, Tuple

FIGMA_API = "https://api.figma.com/v1"


def _collect_nodes(node, all_nodes):
    all_nodes.append(node)
    for child in node.get('children', []) or []:
        _collect_nodes(child, all_nodes)


def _rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(
        max(0, min(255, int(round(r * 255)))) ,
        max(0, min(255, int(round(g * 255)))) ,
        max(0, min(255, int(round(b * 255))))
    )


def _color_to_css(fill):
    color = fill.get('color') or {}
    a = color.get('a', 1.0)
    r, g, b = color.get('r', 0), color.get('g', 0), color.get('b', 0)
    opacity = fill.get('opacity')
    if opacity is not None:
        a = a * opacity
    if a >= 0.999:
        return _rgb_to_hex(r, g, b)
    return 'rgba({},{},{},{})'.format(
        max(0, min(255, int(round(r * 255)))) ,
        max(0, min(255, int(round(g * 255)))) ,
        max(0, min(255, int(round(b * 255)))) ,
        round(a, 3)
    )


def _get_text_style_props(style: Dict[str, Any]) -> Dict[str, Any]:
    if not style:
        return {}
    font_size = style.get('fontSize')
    line_height_px = style.get('lineHeightPx')
    lh = None
    if font_size and line_height_px:
        try:
            lh = round(float(line_height_px) / float(font_size), 3)
        except Exception:
            lh = None
    letter_spacing = style.get('letterSpacing')
    if letter_spacing is not None:
        try:
            letter_spacing = f"{round(float(letter_spacing), 3)}px"
        except Exception:
            pass
    return {
        "fontFamily": style.get('fontFamily'),
        "fontWeight": style.get('fontWeight'),
        "fontSize": f"{style.get('fontSize')}px" if style.get('fontSize') else None,
        "lineHeight": lh if lh is not None else None,
        "letterSpacing": letter_spacing,
        "textCase": style.get('textCase'),
        "textDecoration": style.get('textDecoration')
    }


def extract_tokens_from_figma(file_key: str, token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    headers = {"X-Figma-Token": token}
    resp = requests.get(f"{FIGMA_API}/files/{file_key}", headers=headers, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Figma API error {resp.status_code}: {resp.text}")
    data = resp.json()

    styles = data.get('styles', {})  # id -> {name, style_type}
    document = data.get('document') or {}

    # Build reverse lookup: id -> name
    style_meta = {}
    for style_id, meta in styles.items():
        style_meta[style_id] = {
            'name': meta.get('name'),
            'type': meta.get('style_type')
        }

    all_nodes = []
    _collect_nodes(document, all_nodes)

    color_styles = {}  # styleId -> css_color
    text_styles = {}   # styleId -> text style props

    for node in all_nodes:
        node_styles = node.get('styles') or {}
        # Colors from PAINT_STYLE
        fill_style_id = node_styles.get('fill') or node_styles.get('fills')
        if fill_style_id and style_meta.get(fill_style_id, {}).get('type') == 'FILL':
            fills = node.get('fills') or []
            solid_fill = None
            for f in fills:
                if f.get('visible', True) and f.get('type') == 'SOLID':
                    solid_fill = f
                    break
            if solid_fill:
                color_styles[fill_style_id] = _color_to_css(solid_fill)

        # Text styles
        text_style_id = node_styles.get('text')
        if node.get('type') == 'TEXT' and text_style_id:
            style_props = _get_text_style_props(node.get('style') or {})
            # Only consider if has fontFamily & fontSize
            if style_props.get('fontFamily') and style_props.get('fontSize'):
                text_styles[text_style_id] = style_props

    # Build raw tokens
    raw = {
        'colors': {},
        'typography': {}
    }

    for style_id, value in color_styles.items():
        name = style_meta.get(style_id, {}).get('name') or f"color_{style_id[:6]}"
        raw['colors'][name] = {
            'value': value,
            'source': 'Figma',
            'styleId': style_id
        }

    for style_id, props in text_styles.items():
        name = style_meta.get(style_id, {}).get('name') or f"text_{style_id[:6]}"
        raw['typography'][name] = {
            **{k: v for k, v in props.items() if v is not None},
            'source': 'Figma',
            'styleId': style_id
        }

    meta = {
        'name': data.get('name'),
        'lastModified': data.get('lastModified'),
        'stylesCount': len(styles),
        'colorsExtracted': len(raw['colors']),
        'textStylesExtracted': len(raw['typography'])
    }

    return raw, meta

