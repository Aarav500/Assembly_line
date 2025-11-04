import json
import zipfile
from io import BytesIO
from typing import Dict, Any, Tuple


def _rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(
        max(0, min(255, int(round(r * 255)))) ,
        max(0, min(255, int(round(g * 255)))) ,
        max(0, min(255, int(round(b * 255))))
    )


def _sketch_color_to_css(c: Dict[str, Any]) -> str:
    r = c.get('red', 0)
    g = c.get('green', 0)
    b = c.get('blue', 0)
    a = c.get('alpha', 1)
    if a >= 0.999:
        return _rgb_to_hex(r, g, b)
    return 'rgba({},{},{},{})'.format(
        max(0, min(255, int(round(r * 255)))) ,
        max(0, min(255, int(round(g * 255)))) ,
        max(0, min(255, int(round(b * 255)))) ,
        round(a, 3)
    )


_FONT_WEIGHT_MAP = {
    'thin': 100,
    'extralight': 200,
    'ultralight': 200,
    'light': 300,
    'book': 350,
    'regular': 400,
    'normal': 400,
    'medium': 500,
    'semibold': 600,
    'demibold': 600,
    'bold': 700,
    'extrabold': 800,
    'ultrabold': 800,
    'black': 900,
    'heavy': 900
}


def _guess_weight_from_postscript(name: str) -> int:
    if not name:
        return 400
    n = name.lower()
    for key, val in _FONT_WEIGHT_MAP.items():
        if key in n:
            return val
    return 400


def extract_tokens_from_sketch(file_like: BytesIO, filename: str = "document.sketch") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    zf = zipfile.ZipFile(file_like)
    try:
        doc = json.loads(zf.read('document.json').decode('utf-8'))
    except KeyError:
        raise Exception('Invalid .sketch file: document.json missing')

    colors = {}
    typography = {}

    # Color assets
    assets = (doc.get('assets') or {})
    color_assets = assets.get('colorAssets') or []
    for ca in color_assets:
        name = ca.get('name') or 'color/unnamed'
        color = ca.get('color') or {}
        colors[name] = {
            'value': _sketch_color_to_css(color),
            'source': 'Sketch',
            'assetType': 'colorAsset'
        }

    # Shared layer styles with fills
    layer_styles = (doc.get('layerStyles') or {}).get('objects') or []
    for obj in layer_styles:
        name = obj.get('name') or 'layerStyle/unnamed'
        val = obj.get('value') or {}
        fills = val.get('fills') or []
        solid = None
        for f in fills:
            if f.get('isEnabled') and f.get('_class') == 'fill' and (f.get('fillType') == 0):
                color = f.get('color') or {}
                solid = color
                break
        if solid:
            colors[name] = {
                'value': _sketch_color_to_css(solid),
                'source': 'Sketch',
                'assetType': 'layerStyle'
            }

    # Text styles
    text_styles = (doc.get('layerTextStyles') or {}).get('objects') or []
    for ts in text_styles:
        name = ts.get('name') or 'text/unnamed'
        val = ts.get('value') or {}
        ts_attr = (val.get('textStyle') or {}).get('encodedAttributes') or {}
        font = (ts_attr.get('MSAttributedStringFontAttribute') or {}).get('attributes') or {}
        font_name = font.get('name')
        font_size = font.get('size')
        para = ts_attr.get('paragraphStyle') or {}
        minLH = para.get('minimumLineHeight')
        maxLH = para.get('maximumLineHeight')
        line_height_px = maxLH or minLH
        lh = None
        if line_height_px and font_size:
            try:
                lh = round(float(line_height_px) / float(font_size), 3)
            except Exception:
                lh = None
        letter_spacing = ts_attr.get('kerning')
        if letter_spacing is not None:
            try:
                letter_spacing = f"{round(float(letter_spacing),3)}px"
            except Exception:
                pass
        if font_name and font_size:
            typography[name] = {
                'fontFamily': font_name,
                'fontWeight': _guess_weight_from_postscript(font_name),
                'fontSize': f"{font_size}px",
                'lineHeight': lh if lh is not None else None,
                'letterSpacing': letter_spacing,
                'source': 'Sketch'
            }

    meta = {
        'filename': filename,
        'colorsExtracted': len(colors),
        'textStylesExtracted': len(typography)
    }

    return {'colors': colors, 'typography': typography}, meta

