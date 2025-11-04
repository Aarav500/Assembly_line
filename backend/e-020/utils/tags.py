from typing import Dict
from database import db
from models import ResourceTag


def upsert_tags(resource, tags: Dict[str, str]):
    existing = {t.key: t for t in resource.tags}
    for k, v in tags.items():
        if k in existing:
            existing[k].value = str(v)
        else:
            db.session.add(ResourceTag(resource_id=resource.id, key=str(k), value=str(v)))
    # Remove tags not provided? Keep existing by default; if you want removal send null.
    for k, t in list(existing.items()):
        if k in tags and tags[k] is None:
            db.session.delete(t)


def parse_tag_filters(args):
    # Accept query params tag:key=value or tag_key=value
    tag_filters = {}
    for key, value in args.items(multi=True):
        if key.startswith('tag:'):
            tag_key = key.split(':', 1)[1]
            tag_filters[tag_key] = value
        elif key.startswith('tag_'):
            tag_key = key.split('tag_', 1)[1]
            tag_filters[tag_key] = value
    return tag_filters

