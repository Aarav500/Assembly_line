from typing import Optional
from sqlalchemy.engine import make_url


def mask_db_url(db_url: str) -> str:
    try:
        url = make_url(db_url)
        return url.render_as_string(hide_password=True)
    except Exception:
        # Best effort fallback
        if "@" in db_url and "://" in db_url:
            head, tail = db_url.split("://", 1)
            if "@" in tail and ":" in tail.split("@", 1)[0]:
                creds, rest = tail.split("@", 1)
                if ":" in creds:
                    user = creds.split(":", 1)[0]
                    return f"{head}://{user}:***@{rest}"
        return db_url


def singularize(name: str) -> str:
    n = name.strip()
    if n.endswith("ies"):
        return n[:-3] + "y"
    if n.endswith("ses") or n.endswith("xes") or n.endswith("zes"):
        return n[:-2]
    if n.endswith("s") and not n.endswith("ss"):
        return n[:-1]
    return n


def pluralize(name: str) -> str:
    n = name.strip()
    if n.endswith("y") and len(n) > 1 and n[-2] not in "aeiou":
        return n[:-1] + "ies"
    if n.endswith("s"):
        return n + "es"
    return n + "s"


def safe_rel_name(from_table: str, fk_column: str, to_table: str) -> str:
    # Prefer column name without _id suffix, else referenced table singular
    base = fk_column
    if base.lower().endswith("_id") and len(base) > 3:
        base = base[:-3]
    if not base or base.lower() in {"id", "pk"}:
        base = singularize(to_table)
    return base


def coalesce(a, b):
    return a if a is not None else b

