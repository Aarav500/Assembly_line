import sqlite3
import json
from typing import Dict, List


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def search_snippets(db_path: str, q: str, filters: Dict, limit: int, offset: int) -> List[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = _dict_factory
    cur = conn.cursor()

    # If no query provided, fall back to filtering only
    base_select = 'SELECT s.*, 0.0 as rank FROM snippets s'
    params = []

    if q:
        # Use FTS5 search with bm25 ranking
        select = 'SELECT s.*, bm25(f) as rank FROM snippets_fts f JOIN snippets s ON s.id = f.rowid'
        where = ['f MATCH ?']
        # Build FTS query: escape quotes
        fts_q = _build_fts_query(q)
        params.append(fts_q)
    else:
        select = base_select
        where = []

    # Apply filters (on real table s)
    if filters:
        if filters.get('language'):
            where.append('s.language = ?')
            params.append(filters['language'])
        if filters.get('project'):
            where.append('s.project = ?')
            params.append(filters['project'])
        if filters.get('framework'):
            where.append('s.framework = ?')
            params.append(filters['framework'])
        if filters.get('file_path'):
            # partial match helpful
            where.append('s.file_path LIKE ?')
            params.append(f"%{filters['file_path']}%")
        if filters.get('symbol'):
            where.append('s.symbol = ?')
            params.append(filters['symbol'])
        if filters.get('tag'):
            where.append("EXISTS (SELECT 1 FROM json_each(s.tags) je WHERE je.value = ?)")
            params.append(filters['tag'])

    sql = select
    if where:
        sql += ' WHERE ' + ' AND '.join(where)

    if q:
        sql += ' ORDER BY rank ASC, s.pinned DESC, s.updated_at DESC'
    else:
        sql += ' ORDER BY s.pinned DESC, s.updated_at DESC'

    sql += ' LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    conn.close()

    # Normalize tags to list and pinned to bool
    results = []
    for r in rows:
        item = dict(r)
        try:
            item['tags'] = json.loads(item.get('tags') or '[]')
        except Exception:
            item['tags'] = []
        item['pinned'] = bool(item.get('pinned', 0))
        # rank may be None; ensure float
        try:
            item['rank'] = float(item.get('rank', 0.0))
        except Exception:
            item['rank'] = 0.0
        results.append(item)
    return results


def _sanitize_token(token: str) -> str:
    # Remove characters problematic for FTS query
    t = token.strip().replace('"', ' ').replace("'", ' ')
    return t


def _build_fts_query(q: str) -> str:
    # Build a simple AND query with quoted tokens for exact-ish matching.
    tokens = [t for t in q.replace('\n', ' ').split(' ') if t.strip()]
    tokens = [_sanitize_token(t) for t in tokens]
    if not tokens:
        return ''
    # Quote tokens and use AND operator to improve precision
    quoted = ['"%s"' % t for t in tokens if t]
    return ' AND '.join(quoted)

