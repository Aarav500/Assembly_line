from typing import Dict, Optional


def parse_inline_style(style: Optional[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not style:
        return result
    try:
        parts = [p for p in style.split(';') if p.strip()]
        for p in parts:
            if ':' in p:
                k, v = p.split(':', 1)
                result[k.strip().lower()] = v.strip()
    except Exception:
        pass
    return result


def shorten(text: str, limit: int = 220) -> str:
    t = ' '.join(text.split())
    if len(t) <= limit:
        return t
    return t[:limit] + '…'


def build_selector(el) -> str:
    try:
        if not getattr(el, 'name', None):
            return ''
        name = el.name
        sel = name
        el_id = el.get('id')
        if el_id:
            sel += f"#{el_id}"
        classes = el.get('class') or []
        if classes:
            sel += ''.join([f".{c}" for c in classes])
        if not el_id:
            # add nth-of-type for better specificity
            idx = 1
            sib = el.previous_sibling
            while sib is not None:
                try:
                    if getattr(sib, 'name', None) == name:
                        idx += 1
                except Exception:
                    pass
                sib = sib.previous_sibling
            sel += f":nth-of-type({idx})"
        return sel
    except Exception:
        return ''


def get_text_content(el) -> str:
    try:
        return (el.get_text(separator=' ', strip=True) or '').strip()
    except Exception:
        return ''

