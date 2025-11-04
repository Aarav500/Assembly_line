import re
import hashlib

_pg_ident_re = re.compile(r"^[a-z_][a-z0-9_]*$")

def quote_ident(ident: str) -> str:
    if _pg_ident_re.match(ident):
        return ident
    escaped = ident.replace('"', '""')
    return f'"{escaped}"'


def short_hash(s: str, length: int = 8) -> str:
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:length]


def parse_indexdef_columns(indexdef: str):
    # crude parse: CREATE INDEX name ON schema.table USING btree (col1, col2) INCLUDE (col3, ...)
    cols = []
    include = []
    try:
        # get first parentheses after USING ... or ON ...
        m = re.search(r"USING\s+\w+\s*\((.*?)\)", indexdef, flags=re.IGNORECASE | re.DOTALL)
        if m:
            cols = [c.strip().strip('"') for c in m.group(1).split(',')]
        m2 = re.search(r"INCLUDE\s*\((.*?)\)", indexdef, flags=re.IGNORECASE | re.DOTALL)
        if m2:
            include = [c.strip().strip('"') for c in m2.group(1).split(',')]
    except Exception:
        pass
    # normalize expressions: take simple column refs
    def normalize_list(lst):
        out = []
        for x in lst:
            # drop expressions like (lower(col)) -> col
            mx = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*$", x)
            out.append(mx.group(1) if mx else x)
        return out
    return normalize_list(cols), normalize_list(include)


def ensure_length(name: str, max_len: int = 63) -> str:
    if len(name) <= max_len:
        return name
    # reserve 9 for '_' and hash
    base = name[: max_len - 9]
    return f"{base}_{short_hash(name)}"

