import re
from typing import Optional, Tuple

# Minimal CSS named color map (extend as needed)
NAMED_COLORS = {
    'black': '#000000',
    'white': '#ffffff',
    'red': '#ff0000',
    'green': '#008000',
    'blue': '#0000ff',
    'gray': '#808080',
    'grey': '#808080',
    'lightgray': '#d3d3d3',
    'lightgrey': '#d3d3d3',
    'darkgray': '#a9a9a9',
    'darkgrey': '#a9a9a9',
    'yellow': '#ffff00',
    'orange': '#ffa500',
    'purple': '#800080',
    'pink': '#ffc0cb',
    'brown': '#a52a2a',
    'cyan': '#00ffff',
    'magenta': '#ff00ff',
    'transparent': 'transparent',
}

HEX_COLOR_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*(\d*\.?\d+))?\s*\)")


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def parse_color(value: Optional[str]) -> Optional[Tuple[int, int, int, float]]:
    if not value:
        return None
    v = value.strip().lower()
    if v in NAMED_COLORS:
        if v == 'transparent':
            return (0, 0, 0, 0.0)
        v = NAMED_COLORS[v]
    if HEX_COLOR_RE.match(v or ""):
        hexv = v.lstrip('#')
        if len(hexv) == 3:
            r = int(hexv[0] * 2, 16)
            g = int(hexv[1] * 2, 16)
            b = int(hexv[2] * 2, 16)
        else:
            r = int(hexv[0:2], 16)
            g = int(hexv[2:4], 16)
            b = int(hexv[4:6], 16)
        return (r, g, b, 1.0)
    m = RGB_RE.match(v)
    if m:
        r = clamp(int(m.group(1)), 0, 255)
        g = clamp(int(m.group(2)), 0, 255)
        b = clamp(int(m.group(3)), 0, 255)
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        a = clamp(a, 0.0, 1.0)
        return (int(r), int(g), int(b), a)
    return None


def srgb_to_linear(c: float) -> float:
    c = c / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    r, g, b = rgb
    R = srgb_to_linear(r)
    G = srgb_to_linear(g)
    B = srgb_to_linear(b)
    return 0.2126 * R + 0.7152 * G + 0.0722 * B


def blend_over(bg: Tuple[int, int, int], fg: Tuple[int, int, int], alpha: float) -> Tuple[int, int, int]:
    # naive alpha blending: out = fg*alpha + bg*(1-alpha)
    r = int(round(fg[0] * alpha + bg[0] * (1 - alpha)))
    g = int(round(fg[1] * alpha + bg[1] * (1 - alpha)))
    b = int(round(fg[2] * alpha + bg[2] * (1 - alpha)))
    return (r, g, b)


def contrast_ratio(fg_color: Tuple[int, int, int, float], bg_color: Tuple[int, int, int, float]) -> float:
    fg_rgb = (fg_color[0], fg_color[1], fg_color[2])
    bg_rgb = (bg_color[0], bg_color[1], bg_color[2])
    fg_alpha = fg_color[3]
    bg_alpha = bg_color[3]

    # Compose transparency over opaque white bg if needed
    if bg_alpha < 1.0:
        bg_rgb = blend_over((255, 255, 255), bg_rgb, bg_alpha)
    if fg_alpha < 1.0:
        fg_rgb = blend_over(bg_rgb, fg_rgb, fg_alpha)

    L1 = relative_luminance(fg_rgb)
    L2 = relative_luminance(bg_rgb)
    lighter = max(L1, L2)
    darker = min(L1, L2)
    return (lighter + 0.05) / (darker + 0.05)


def meets_wcag_aa(ratio: float, is_large_text: bool) -> bool:
    return ratio >= (3.0 if is_large_text else 4.5)

