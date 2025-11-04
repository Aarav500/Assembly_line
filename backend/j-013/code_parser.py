import os
import re
import json
from typing import Dict, List

COLOR_HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
CSS_VAR_DECL_RE = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);")
CLASS_BLOCK_RE = re.compile(r"\.([A-Za-z0-9_-]+)\s*\{([^}]*)\}", re.MULTILINE | re.DOTALL)
DECL_RE = re.compile(r"([a-zA-Z-]+)\s*:\s*([^;]+);")
RGB_RE = re.compile(r"rgba?\(([^\)]+)\)")
HSL_RE = re.compile(r"hsla?\(([^\)]+)\)")

SUPPORTED_CODE_EXTS = {'.css', '.scss', '.sass', '.less'}

# Color normalization helpers

def clamp(n, min_v=0, max_v=255):
    return max(min_v, min(max_v, n))

def to_hex_from_rgb_str(rgb_str: str):
    parts = [p.strip() for p in rgb_str.split(',')]
    if len(parts) < 3:
        return None
    def parse_val(v):
        if v.endswith('%'):
            try:
                return clamp(int(round(float(v[:-1]) * 2.55)))
            except:
                return 0
        try:
            return clamp(int(round(float(v))))
        except:
            return 0
    r = parse_val(parts[0])
    g = parse_val(parts[1])
    b = parse_val(parts[2])
    a = 1.0
    if len(parts) >= 4:
        try:
            a = float(parts[3])
        except:
            a = 1.0
    a_i = clamp(int(round(a * 255)))
    if a_i < 255:
        return f"#{r:02X}{g:02X}{b:02X}{a_i:02X}"
    return f"#{r:02X}{g:02X}{b:02X}"

def to_hex_from_hsl_str(hsl_str: str):
    # Very rough HSL to RGB conversion
    parts = [p.strip() for p in hsl_str.split(',')]
    if len(parts) < 3:
        return None
    try:
        h = float(parts[0].rstrip('deg'))
        s = float(parts[1].rstrip('%')) / 100.0
        l = float(parts[2].rstrip('%')) / 100.0
        a = float(parts[3]) if len(parts) >= 4 else 1.0
    except:
        return None
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = l - c / 2
    r1 = g1 = b1 = 0
    if 0 <= h < 60:
        r1, g1, b1 = c, x, 0
    elif 60 <= h < 120:
        r1, g1, b1 = x, c, 0
    elif 120 <= h < 180:
        r1, g1, b1 = 0, c, x
    elif 180 <= h < 240:
        r1, g1, b1 = 0, x, c
    elif 240 <= h < 300:
        r1, g1, b1 = x, 0, c
    else:
        r1, g1, b1 = c, 0, x
    r = clamp(int(round((r1 + m) * 255)))
    g = clamp(int(round((g1 + m) * 255)))
    b = clamp(int(round((b1 + m) * 255)))
    a_i = clamp(int(round(a * 255)))
    if a_i < 255:
        return f"#{r:02X}{g:02X}{b:02X}{a_i:02X}"
    return f"#{r:02X}{g:02X}{b:02X}"

def normalize_color(value: str):
    value = value.strip()
    m = COLOR_HEX_RE.search(value)
    if m:
        hexv = m.group(0)
        # Expand short hex like #abc to #aabbcc
        hexval = m.group(1)
        if len(hexval) == 3:
            r, g, b = hexval[0], hexval[1], hexval[2]
            return f"#{r}{r}{g}{g}{b}{b}".upper()
        if len(hexval) == 4:  # RGBA short
            r, g, b, a = hexval[0], hexval[1], hexval[2], hexval[3]
            return f"#{r}{r}{g}{g}{b}{b}{a}{a}".upper()
        return hexv.upper()
    m = RGB_RE.search(value)
    if m:
        return to_hex_from_rgb_str(m.group(1))
    m = HSL_RE.search(value)
    if m:
        return to_hex_from_hsl_str(m.group(1))
    return None


def parse_css_file(path: str):
    colors = []
    text_styles = []
    raw_colors_used = set()

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            css = f.read()
    except Exception:
        return colors, text_styles, raw_colors_used

    # CSS variables
    for var_name, val in CSS_VAR_DECL_RE.findall(css):
        hexv = normalize_color(val)
        if hexv:
            colors.append({
                'name': var_name,
                'value': hexv,
                'source': 'css_var',
                'file': path
            })

    # raw colors used
    for m in COLOR_HEX_RE.finditer(css):
        raw_colors_used.add(normalize_color(m.group(0)))
    for m in RGB_RE.finditer(css):
        hexv = to_hex_from_rgb_str(m.group(1))
        if hexv:
            raw_colors_used.add(hexv)
    for m in HSL_RE.finditer(css):
        hexv = to_hex_from_hsl_str(m.group(1))
        if hexv:
            raw_colors_used.add(hexv)

    # Class blocks for text styles
    for class_name, block in CLASS_BLOCK_RE.findall(css):
        decls = dict((prop.strip().lower(), val.strip()) for prop, val in DECL_RE.findall(block))
        fs = decls.get('font-size')
        ff = decls.get('font-family')
        lh = decls.get('line-height')
        if fs or ff or lh:
            ts = {'name': f'.{class_name}', 'source': 'css_class', 'file': path}
            if fs:
                if fs.endswith('px'):
                    try:
                        ts['fontSize'] = float(fs[:-2])
                    except:
                        pass
                elif fs.endswith('rem'):
                    try:
                        ts['fontSize'] = float(fs[:-3]) * 16.0
                    except:
                        pass
            if lh:
                if lh.endswith('px'):
                    try:
                        ts['lineHeightPx'] = float(lh[:-2])
                    except:
                        pass
                elif lh.endswith('%') and 'fontSize' in ts:
                    try:
                        ts['lineHeightPx'] = (float(lh[:-1]) / 100.0) * ts['fontSize']
                    except:
                        pass
                elif lh.replace('.', '', 1).isdigit() and 'fontSize' in ts:
                    try:
                        ts['lineHeightPx'] = float(lh) * ts['fontSize']
                    except:
                        pass
            if ff:
                ts['fontFamily'] = ff.strip().strip('\"\'')
            text_styles.append(ts)

    return colors, text_styles, raw_colors_used


def parse_tokens_json(path: str):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return {'colors': [], 'textStyles': []}

    colors = []
    text_styles = []

    # Heuristic parse common token shapes
    # Colors: object with hex values
    def walk(obj, prefix=''):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, dict):
                    walk(v, key)
                else:
                    if isinstance(v, str):
                        hx = normalize_color(v)
                        if hx:
                            colors.append({'name': key, 'value': hx, 'source': 'json'})
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                key = f"{prefix}[{i}]"
                if isinstance(v, (dict, list)):
                    walk(v, key)
                elif isinstance(v, str):
                    hx = normalize_color(v)
                    if hx:
                        colors.append({'name': key, 'value': hx, 'source': 'json'})
    walk(data)

    # Basic text styles if present (e.g., tokens typography)
    if isinstance(data, dict) and 'typography' in data:
        typo = data['typography']
        if isinstance(typo, dict):
            for name, v in typo.items():
                if isinstance(v, dict):
                    ts = {'name': name, 'source': 'json'}
                    if 'fontSize' in v:
                        try:
                            fs = v['fontSize']
                            if isinstance(fs, str) and fs.endswith('px'):
                                ts['fontSize'] = float(fs[:-2])
                            elif isinstance(fs, (int, float)):
                                ts['fontSize'] = float(fs)
                        except:
                            pass
                    if 'lineHeight' in v:
                        lh = v['lineHeight']
                        if isinstance(lh, str) and lh.endswith('px'):
                            try:
                                ts['lineHeightPx'] = float(lh[:-2])
                            except:
                                pass
                        elif isinstance(lh, (int, float)) and 'fontSize' in ts:
                            ts['lineHeightPx'] = float(lh)
                    if 'fontFamily' in v:
                        ts['fontFamily'] = str(v['fontFamily'])
                    if len(ts) > 2:
                        text_styles.append(ts)

    return {'colors': colors, 'textStyles': text_styles}


def extract_code_tokens(base_dir: str) -> Dict:
    colors: List[dict] = []
    text_styles: List[dict] = []
    raw_used = set()

    # Parse CSS-like files
    for root, dirs, files in os.walk(base_dir):
        for fname in files:
            _, ext = os.path.splitext(fname)
            if ext.lower() in SUPPORTED_CODE_EXTS:
                path = os.path.join(root, fname)
                c, t, used = parse_css_file(path)
                colors.extend(c)
                text_styles.extend(t)
                raw_used |= set(x for x in used if x)

    # Parse token JSON files if exist
    for candidate in ['tokens.json', 'design-tokens.json', 'style-dictionary.json']:
        path = os.path.join(base_dir, candidate)
        if os.path.isfile(path):
            data = parse_tokens_json(path)
            colors.extend(data.get('colors', []))
            text_styles.extend(data.get('textStyles', []))

    # Deduplicate colors by (name, value)
    seen = set()
    dedup_colors = []
    for item in colors:
        key = (item.get('name'), item.get('value'))
        if key not in seen:
            seen.add(key)
            dedup_colors.append(item)

    # Deduplicate text styles by name + key props
    seen_t = set()
    dedup_texts = []
    for ts in text_styles:
        key = (ts.get('name'), ts.get('fontFamily'), ts.get('fontSize'), ts.get('lineHeightPx'))
        if key not in seen_t:
            seen_t.add(key)
            dedup_texts.append(ts)

    return {
        'colors': dedup_colors,
        'textStyles': dedup_texts,
        'colorsUsedRaw': sorted(list(raw_used))
    }

