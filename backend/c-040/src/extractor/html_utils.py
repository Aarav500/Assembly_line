import hashlib
import re
from dataclasses import dataclass
from bs4 import BeautifulSoup, NavigableString, Tag


ALLOWED_ROOT_TAGS = {
    'div', 'section', 'header', 'footer', 'nav', 'article', 'aside', 'ul', 'ol'
}

GENERIC_CLASS_NAMES = {
    'container', 'row', 'col', 'col-12', 'col-md', 'col-sm', 'grid', 'section', 'content'
}

TEXT_TOKEN = '{TEXT}'


@dataclass
class Placeholder:
    type: str  # 'text' or 'attr'
    path: list  # list of indices through .contents; for attr ends with '@', attr_name held separately
    attr: str | None
    name: str


@dataclass
class NormalizedSubtree:
    signature: str
    normalized: str
    placeholders: list
    size: int  # number of tags


def slugify(name: str) -> str:
    name = name.lower()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    if not name:
        name = 'component'
    if name[0].isdigit():
        name = '_' + name
    return name


def pick_descriptive_class(cls_list):
    for c in cls_list:
        if c not in GENERIC_CLASS_NAMES and len(c) > 2:
            return c
    return cls_list[0] if cls_list else None


def parse_html(content: str):
    return BeautifulSoup(content, 'lxml')


def get_child_indexed_contents(tag: Tag):
    return list(tag.contents)


def normalize_tag(tag: Tag) -> NormalizedSubtree:
    placeholders = []
    counters = {
        'text': 0,
        'attr': 0,
    }

    def norm_attrs(t: Tag, path):
        items = []
        # sort attributes for stability
        attrs = dict(t.attrs)
        # Normalize class order
        if 'class' in attrs and isinstance(attrs['class'], (list, tuple)):
            attrs['class'] = sorted(attrs['class'])
        # Attributes considered placeholders
        placeholder_attr_keys = ['src', 'href', 'alt', 'title', 'value']
        for key in sorted(attrs.keys()):
            val = attrs[key]
            if isinstance(val, list):
                val = ' '.join(val)
            if key in placeholder_attr_keys and isinstance(val, str) and val.strip():
                counters['attr'] += 1
                ph_name = f"{t.name}_{key}_{counters['attr']}"
                placeholders.append(Placeholder(type='attr', path=path.copy(), attr=key, name=ph_name))
                val_str = f"{{ATTR}}"
            else:
                val_str = str(val)
            items.append((key, val_str))
        return ' '.join([f'{k}="{v}"' for k, v in items])

    def walk(node, path):
        nonlocal placeholders
        if isinstance(node, NavigableString):
            text = str(node)
            if text and text.strip():
                counters['text'] += 1
                ph_name = f"text_{counters['text']}"
                placeholders.append(Placeholder(type='text', path=path.copy(), attr=None, name=ph_name))
                return TEXT_TOKEN
            else:
                return ''
        elif isinstance(node, Tag):
            # compute attributes
            attrs_str = norm_attrs(node, path)
            opening = f"<{node.name}{(' ' + attrs_str) if attrs_str else ''}>"
            children_norm = []
            size_local = 1
            for idx, child in enumerate(get_child_indexed_contents(node)):
                child_norm = walk(child, path + [idx])
                if isinstance(child, Tag):
                    size_local += 1
                children_norm.append(child_norm)
            closing = f"</{node.name}>"
            return opening + ''.join(children_norm) + closing
        else:
            return ''

    normalized = walk(tag, [])
    # Compute size as count of tags in normalized string roughly by counting '<' minus closing? Better count during walk but we only counted local; do a simple tag count now.
    # We'll estimate size by number of opening tags
    size = normalized.count('<') - normalized.count('</') + normalized.count('<') // 2  # rough fallback
    signature = hashlib.sha1(normalized.encode('utf-8')).hexdigest()
    return NormalizedSubtree(signature=signature, normalized=normalized, placeholders=placeholders, size=size)


def candidate_roots(soup: BeautifulSoup):
    for tag in soup.find_all(True):
        if tag.name in ALLOWED_ROOT_TAGS:
            yield tag


def extract_text_from_path(root: Tag, path: list):
    node = root
    for idx in path:
        if isinstance(idx, int):
            contents = get_child_indexed_contents(node)
            if idx < 0 or idx >= len(contents):
                return ''
            node = contents[idx]
        else:
            # unknown marker
            break
    if isinstance(node, NavigableString):
        return str(node).strip()
    elif isinstance(node, Tag):
        # concatenate all text
        return node.get_text(strip=True)
    return ''


def extract_attr_from_path(root: Tag, path: list, attr: str):
    node = root
    for idx in path:
        if isinstance(idx, int):
            contents = get_child_indexed_contents(node)
            if idx < 0 or idx >= len(contents):
                return ''
            node = contents[idx]
    if isinstance(node, Tag):
        return node.get(attr, '')
    return ''


def guess_component_name(tag: Tag, existing_names: set[str]):
    classes = tag.get('class', []) if isinstance(tag.get('class', []), list) else []
    base = pick_descriptive_class(classes) or tag.name
    base = slugify(base)
    name = base
    i = 1
    while name in existing_names:
        i += 1
        name = f"{base}_{i}"
    return name

