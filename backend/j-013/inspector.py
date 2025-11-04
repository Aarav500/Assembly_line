import math
import re
from typing import Dict, List


def _slugify(name: str):
    name = name or ''
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", '-', name)
    return re.sub(r"-+", '-', name).strip('-')


def _hex_to_rgba(hexv: str):
    v = hexv.strip().lstrip('#')
    if len(v) == 3:
        r = int(v[0]*2, 16)
        g = int(v[1]*2, 16)
        b = int(v[2]*2, 16)
        a = 255
    elif len(v) == 4:
        r = int(v[0]*2, 16)
        g = int(v[1]*2, 16)
        b = int(v[2]*2, 16)
        a = int(v[3]*2, 16)
    elif len(v) == 6:
        r = int(v[0:2], 16)
        g = int(v[2:4], 16)
        b = int(v[4:6], 16)
        a = 255
    elif len(v) == 8:
        r = int(v[0:2], 16)
        g = int(v[2:4], 16)
        b = int(v[4:6], 16)
        a = int(v[6:8], 16)
    else:
        return (0, 0, 0, 255)
    return (r, g, b, a)


def _color_distance(h1: str, h2: str) -> float:
    r1, g1, b1, a1 = _hex_to_rgba(h1)
    r2, g2, b2, a2 = _hex_to_rgba(h2)
    return math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2) + abs(a1 - a2) / 2.0


def match_colors(figma_colors: List[dict], code_colors: List[dict], code_used: List[str]):
    # Build map by value
    code_by_value = {}
    for c in code_colors:
        val = c.get('value')
        if not val:
            continue
        code_by_value.setdefault(val.upper(), []).append(c)

    report = []
    matched = 0

    for fc in figma_colors:
        name = fc.get('name')
        hexv = (fc.get('hex') or '').upper()
        style_id = fc.get('id')
        if not hexv:
            report.append({
                'styleId': style_id,
                'name': name,
                'figma': None,
                'match': False,
                'reason': 'No sampled value found in file for this style',
                'closest': None
            })
            continue
        exact = code_by_value.get(hexv)
        if exact:
            report.append({
                'styleId': style_id,
                'name': name,
                'figma': hexv,
                'match': True,
                'code': exact,
                'type': 'exact'
            })
            matched += 1
            continue
        # Try nearest by distance
        nearest = None
        nearest_d = 1e9
        nearest_src = None
        for val, items in code_by_value.items():
            d = _color_distance(hexv, val)
            if d < nearest_d:
                nearest_d = d
                nearest = val
                nearest_src = items
        # Also check raw used colors (no var)
        nearest_raw = None
        nearest_raw_d = 1e9
        for raw in code_used:
            d = _color_distance(hexv, raw)
            if d < nearest_raw_d:
                nearest_raw_d = d
                nearest_raw = raw
        entry = {
            'styleId': style_id,
            'name': name,
            'figma': hexv,
            'match': False,
            'closest': {
                'value': nearest,
                'distance': nearest_d,
                'code': nearest_src
            },
            'closestRaw': {
                'value': nearest_raw,
                'distance': nearest_raw_d
            }
        }
        report.append(entry)

    return report, matched


def match_text_styles(figma_texts: List[dict], code_texts: List[dict]):
    def score(f, c):
        s = 0.0
        ffs = (f or {}).get('style') or {}
        # font size
        fs_f = ffs.get('fontSize')
        fs_c = c.get('fontSize')
        if fs_f and fs_c:
            diff = abs(float(fs_f) - float(fs_c))
            s += max(0.0, 1.0 - min(diff, 8.0) / 8.0) * 0.5
        # line height
        lh_f = ffs.get('lineHeightPx') or ffs.get('lineHeightPercentFontSize')
        lh_c = c.get('lineHeightPx')
        if isinstance(lh_f, (int, float)) and lh_c:
            diff = abs(float(lh_f) - float(lh_c))
            s += max(0.0, 1.0 - min(diff, 12.0) / 12.0) * 0.3
        # font family
        ff_f = str(ffs.get('fontFamily') or '').lower().strip()
        ff_c = str(c.get('fontFamily') or '').lower().strip()
        if ff_f and ff_c:
            s += (1.0 if ff_f in ff_c or ff_c in ff_f else 0.0) * 0.2
        return s

    report = []
    matched = 0

    for ft in figma_texts:
        best = None
        best_s = -1
        for ct in code_texts:
            sc = score(ft, ct)
            if sc > best_s:
                best_s = sc
                best = ct
        entry = {
            'styleId': ft.get('id'),
            'name': ft.get('name'),
            'figma': ft.get('style'),
            'match': best_s >= 0.9,
            'score': round(best_s, 3),
            'code': best
        }
        if entry['match']:
            matched += 1
        report.append(entry)

    return report, matched


def generate_css_suggestions(color_mismatches: List[dict]):
    lines = [":root {"]
    for item in color_mismatches:
        if item.get('match'):
            continue
        name = item.get('name') or 'unnamed'
        slug = _slugify(name)
        figma_val = item.get('figma')
        if figma_val:
            var_name = f"--color-{slug}"
            lines.append(f"  {var_name}: {figma_val};  /* Figma: {name} */")
    lines.append("}")
    return "\n".join(lines)


def generate_report(figma_tokens: Dict, code_tokens: Dict) -> Dict:
    figma_colors = figma_tokens.get('colors', [])
    figma_texts = figma_tokens.get('textStyles', [])
    code_colors = code_tokens.get('colors', [])
    code_texts = code_tokens.get('textStyles', [])
    code_used = code_tokens.get('colorsUsedRaw', [])

    color_report, color_matched = match_colors(figma_colors, code_colors, code_used)
    text_report, text_matched = match_text_styles(figma_texts, code_texts)

    # CSS suggestions
    css_suggestions = generate_css_suggestions(color_report)

    summary = {
        'colors': {
            'total': len(figma_colors),
            'matched': color_matched,
            'unmatched': max(0, len(figma_colors) - color_matched)
        },
        'textStyles': {
            'total': len(figma_texts),
            'matched': text_matched,
            'unmatched': max(0, len(figma_texts) - text_matched)
        }
    }

    return {
        'summary': summary,
        'colors': color_report,
        'textStyles': text_report,
        'suggestions': {
            'cssVariables': css_suggestions
        }
    }

