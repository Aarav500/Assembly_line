from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, element as bs4element
from .utils import parse_inline_style, shorten, build_selector, get_text_content
from .contrast import parse_color, contrast_ratio, meets_wcag_aa


@dataclass
class Issue:
    severity: str  # error, warning, info
    code: str
    message: str
    selector: str
    snippet: str
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def _issue(severity: str, code: str, message: str, el: Optional[bs4element.Tag], extra: Optional[Dict[str, Any]] = None) -> Issue:
    selector = build_selector(el) if el else ''
    snippet = ''
    if el is not None:
        try:
            snippet = shorten(str(el))
        except Exception:
            snippet = ''
    return Issue(
        severity=severity,
        code=code,
        message=message,
        selector=selector,
        snippet=snippet,
        context=extra or {}
    )


def _has_label(soup: BeautifulSoup, control: bs4element.Tag) -> bool:
    if control.name not in ('input', 'select', 'textarea'):
        return True
    t = control.get('type', '').lower()
    if t == 'hidden':
        return True
    # labelled by 'aria-*'
    if control.get('aria-label') or control.get('aria-labelledby'):
        return True
    # wrapping label
    parent = control.parent
    while parent is not None and getattr(parent, 'name', None):
        if parent.name == 'label':
            return True
        parent = parent.parent
    # for attribute
    cid = control.get('id')
    if cid:
        lab = soup.find('label', attrs={'for': cid})
        if lab is not None:
            return True
    return False


def _accessible_name(soup: BeautifulSoup, el: bs4element.Tag) -> str:
    # Simplified accessible name computation
    aria_label = el.get('aria-label')
    if aria_label:
        return aria_label.strip()
    labelledby = el.get('aria-labelledby')
    if labelledby:
        parts = []
        for tid in labelledby.split():
            lab = soup.find(id=tid)
            if lab is not None:
                parts.append(get_text_content(lab))
        if parts:
            return ' '.join([p for p in parts if p])
    if el.name == 'img':
        alt = el.get('alt')
        if alt:
            return alt.strip()
    # Fallback to element text
    text = get_text_content(el)
    if text:
        return text
    # last resort title
    title = el.get('title')
    if title:
        return title.strip()
    return ''


def _is_large_text(style: dict) -> bool:
    # Approximation: large text if font-size >= 24px OR (>=18.66px and bold)
    size = style.get('font-size')
    weight = style.get('font-weight', '')
    is_bold = False
    try:
        if weight:
            if weight.lower() in ('bold', 'bolder', '600', '700', '800', '900'):
                is_bold = True
            else:
                wnum = int(''.join([c for c in weight if c.isdigit()]) or '0')
                if wnum >= 600:
                    is_bold = True
    except Exception:
        pass
    try:
        if size and size.strip().endswith('px'):
            px = float(size.strip()[:-2])
            if px >= 24:
                return True
            if px >= 18.66 and is_bold:
                return True
    except Exception:
        return False
    return False


def analyze_html(html: str, base_url: Optional[str] = None) -> Dict[str, Any]:
    soup = BeautifulSoup(html, 'html.parser')
    issues: List[Issue] = []

    # Document-level checks
    html_tag = soup.find('html')
    if html_tag is not None:
        if not html_tag.get('lang'):
            issues.append(_issue('warning', 'doc-lang-missing', 'html element is missing a lang attribute.', html_tag))
    else:
        # If not a full document, still proceed
        pass

    # Landmark check
    if soup.find('main') is None:
        issues.append(_issue('info', 'landmark-main-missing', 'Consider adding a <main> landmark to identify primary content.', soup.find('body') or soup))

    # Heading structure checks
    headings = []
    for h in soup.find_all([f'h{i}' for i in range(1, 7)]):
        try:
            level = int(h.name[1])
            headings.append((h, level))
        except Exception:
            continue
    if headings:
        # Ensure first heading is h1 and only one h1 ideally
        h1s = [h for h, lvl in headings if lvl == 1]
        if not h1s:
            issues.append(_issue('warning', 'h1-missing', 'No <h1> found. Include a top-level heading to describe page purpose.', soup.find('body') or soup))
        last = headings[0][1]
        for h, lvl in headings[1:]:
            if lvl - last > 1:
                issues.append(_issue('warning', 'heading-level-skip', f'Heading level jumps from h{last} to h{lvl}. Avoid skipping levels.', h))
            last = lvl
    else:
        # No headings at all
        issues.append(_issue('info', 'headings-missing', 'No headings found. Use headings to structure content.', soup.find('body') or soup))

    # Image alt checks
    for img in soup.find_all('img'):
        alt = img.get('alt')
        aria_hidden = (img.get('aria-hidden') == 'true')
        role = (img.get('role') or '').lower()
        decorative = aria_hidden or role == 'presentation'
        if alt is None and not decorative:
            issues.append(_issue('error', 'img-alt-missing', 'Image is missing alt text.', img))
        elif alt is not None and alt.strip() == '' and not decorative:
            issues.append(_issue('warning', 'img-alt-empty', 'Image has empty alt text. Provide meaningful alternative text or mark decorative images appropriately.', img))

    # Form control labeling
    for control in soup.find_all(['input', 'select', 'textarea']):
        t = control.get('type', '').lower()
        if t == 'hidden':
            continue
        if not _has_label(soup, control):
            issues.append(_issue('error', 'form-control-label-missing', 'Form control is missing a programmatic label (label, aria-label, or aria-labelledby).', control))

    # Links and buttons accessible name
    for btn in soup.find_all(['button']):
        name = _accessible_name(soup, btn)
        if not name:
            issues.append(_issue('error', 'button-name-missing', 'Button lacks an accessible name (text, aria-label, or aria-labelledby).', btn))
        if (btn.get('role') or '').lower() == 'button':
            issues.append(_issue('info', 'role-redundant', 'Redundant role="button" on a <button> element.', btn))

    for a in soup.find_all('a'):
        href = a.get('href', '').strip()
        name = _accessible_name(soup, a)
        if not name:
            issues.append(_issue('error', 'link-name-missing', 'Link lacks an accessible name (text, aria-label, or aria-labelledby).', a))
        if href in ('', '#') or href.lower().startswith('javascript:'):
            issues.append(_issue('warning', 'link-inert', 'Link appears inert (href="#" or javascript). Consider using a <button> for actions.', a))

    # Tabindex checks
    for el in soup.find_all(attrs={'tabindex': True}):
        try:
            val = int(el.get('tabindex'))
            if val > 0:
                issues.append(_issue('warning', 'tabindex-positive', 'Avoid positive tabindex values; they can create confusing tab order.', el, { 'tabindex': val }))
        except Exception:
            issues.append(_issue('info', 'tabindex-invalid', 'Invalid tabindex value.', el, { 'tabindex': el.get('tabindex') }))

    # Title-only name
    for el in soup.find_all(True):
        if el.get('title') and not _accessible_name(soup, el).strip():
            issues.append(_issue('warning', 'title-only-name', 'Title attribute should not be the only means of conveying information; provide visible text or aria-label.', el))

    # Color contrast (inline styles only, approximate background as white if unknown)
    def walk_text_nodes(parent):
        for node in parent.descendants:
            if isinstance(node, bs4element.NavigableString):
                text = str(node).strip()
                if not text:
                    continue
                p = node.parent
                if not p or not getattr(p, 'name', None):
                    continue
                style = parse_inline_style(p.get('style'))
                color = parse_color(style.get('color') or '#000000') or (0, 0, 0, 1.0)
                bg = parse_color(style.get('background-color') or '#ffffff') or (255, 255, 255, 1.0)
                ratio = contrast_ratio(color, bg)
                large = _is_large_text(style)
                if not meets_wcag_aa(ratio, large):
                    issues.append(_issue('error', 'contrast-insufficient', f'Text contrast ratio {ratio:.2f}:1 does not meet WCAG AA.', p, {
                        'text_sample': shorten(text, 80),
                        'ratio': round(ratio, 2),
                        'large_text': large,
                        'fg': style.get('color') or '#000000',
                        'bg': style.get('background-color') or '#ffffff',
                    }))
    body = soup.find('body') or soup
    walk_text_nodes(body)

    # Stats
    stats = {
        'errors': sum(1 for i in issues if i.severity == 'error'),
        'warnings': sum(1 for i in issues if i.severity == 'warning'),
        'info': sum(1 for i in issues if i.severity == 'info'),
        'total': len(issues)
    }

    return {
        'base_url': base_url,
        'stats': stats,
        'issues': [iss.to_dict() for iss in issues]
    }

