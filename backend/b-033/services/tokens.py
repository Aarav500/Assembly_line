import re
from typing import Dict, Tuple, Any


def _slugify(name: str) -> str:
    if not name:
        return 'unnamed'
    name = name.strip().replace('—', '-').replace('–', '-')
    name = re.sub(r'[\\/:]+', '-', name)
    name = re.sub(r'\s+', '-', name)
    name = re.sub(r'[^a-zA-Z0-9\-\.]+', '', name)
    name = name.strip('.-').lower()
    if not name:
        return 'unnamed'
    return name


def _to_var_name(prefix: str, name: str) -> str:
    n = _slugify(name)
    n = n.replace('.', '-')
    if prefix:
        p = _slugify(prefix)
        n = f"{p}-{n}"
    if not re.match(r'^[a-zA-Z_]', n):
        n = f"t-{n}"
    return n


def _to_token_key(name: str) -> str:
    n = _slugify(name)
    n = n.replace('-', '.')
    return n


def normalize_tokens(raw: Dict[str, Dict[str, Any]], prefix: str = '') -> Dict[str, Dict[str, Any]]:
    colors = {}
    typography = {}

    # Normalize colors
    for raw_name, item in (raw.get('colors') or {}).items():
        token_key = _to_token_key(raw_name)
        var_name = _to_var_name(prefix, raw_name)
        # Ensure 'color-' prefix in CSS var name
        if not var_name.startswith('color-'):
            var_name = f"color-{var_name}"
        colors[token_key] = {
            'value': item.get('value'),
            'cssVar': f"--{var_name}",
            'source': item.get('source')
        }

    # Normalize typography
    for raw_name, item in (raw.get('typography') or {}).items():
        token_key = _to_token_key(raw_name)
        base = _to_var_name(prefix, raw_name)
        if not base.startswith('text-'):
            base = f"text-{base}"
        entry = {
            'fontFamily': item.get('fontFamily'),
            'fontSize': item.get('fontSize'),
            'lineHeight': item.get('lineHeight'),
            'fontWeight': item.get('fontWeight'),
            'letterSpacing': item.get('letterSpacing'),
            'cssVars': {
                'fontFamily': f"--{base}-font-family",
                'fontSize': f"--{base}-font-size",
                'lineHeight': f"--{base}-line-height",
                'fontWeight': f"--{base}-font-weight",
                'letterSpacing': f"--{base}-letter-spacing",
            },
            'source': item.get('source')
        }
        typography[token_key] = entry

    return { 'colors': colors, 'typography': typography }


def build_css_from_tokens(tokens: Dict[str, Dict[str, Any]]) -> Tuple[str, str]:
    lines_vars = []
    lines_vars.append(':root {')
    # Colors
    for key, item in (tokens.get('colors') or {}).items():
        lines_vars.append(f"  {item['cssVar']}: {item['value']}; /* {key} */")
    # Typography
    for key, item in (tokens.get('typography') or {}).items():
        cv = item.get('cssVars')
        if not cv:
            continue
        if item.get('fontFamily'):
            lines_vars.append(f"  {cv['fontFamily']}: {item['fontFamily']}; /* {key} */")
        if item.get('fontSize'):
            lines_vars.append(f"  {cv['fontSize']}: {item['fontSize']};")
        if item.get('lineHeight') is not None:
            lines_vars.append(f"  {cv['lineHeight']}: {item['lineHeight']};")
        if item.get('fontWeight'):
            lines_vars.append(f"  {cv['fontWeight']}: {item['fontWeight']};")
        if item.get('letterSpacing') is not None:
            lines_vars.append(f"  {cv['letterSpacing']}: {item['letterSpacing']};")
    lines_vars.append('}')

    # Utilities
    utils = []
    # Color utilities
    for key, item in (tokens.get('colors') or {}).items():
        class_safe = key.replace('.', '-').lower()
        utils.append(f".color-{class_safe} { { } }".replace('{ { } }', '{'))
        utils.append(f"  color: var({item['cssVar']});")
        utils.append('}')
        utils.append(f".bg-{class_safe} { { } }".replace('{ { } }', '{'))
        utils.append(f"  background-color: var({item['cssVar']});")
        utils.append('}')
    # Typography utilities
    for key, item in (tokens.get('typography') or {}).items():
        class_safe = key.replace('.', '-').lower()
        cv = item.get('cssVars')
        utils.append(f".text-{class_safe} { { } }".replace('{ { } }', '{'))
        if item.get('fontFamily'):
            utils.append(f"  font-family: var({cv['fontFamily']});")
        if item.get('fontSize'):
            utils.append(f"  font-size: var({cv['fontSize']});")
        if item.get('lineHeight') is not None:
            utils.append(f"  line-height: var({cv['lineHeight']});")
        if item.get('fontWeight'):
            utils.append(f"  font-weight: var({cv['fontWeight']});")
        if item.get('letterSpacing') is not None:
            utils.append(f"  letter-spacing: var({cv['letterSpacing']});")
        utils.append('}')

    css_vars = '\n'.join(lines_vars)
    css_utils = '\n'.join(utils)
    return css_vars, css_utils

