from typing import Dict, Any, List, Optional
from .plan_analyzer import explain_query, analyze_plan_for_suggestions, build_index_ddl, get_existing_indexes
from .db import set_statement_timeout, reset_statement_timeout
from .utils import parse_indexdef_columns


def suggest_indexes_for_query(conn, query: str, analyze: bool = False, timeout_ms: Optional[int] = None, min_table_rows_for_index: int = 10000) -> Dict[str, Any]:
    plan = explain_query(conn, query, analyze=analyze, buffers=True, timeout_ms=timeout_ms)
    suggestions = analyze_plan_for_suggestions(conn, plan, min_table_rows_for_index=min_table_rows_for_index)
    # enrich with DDL and dedupe against existing indexes strictly
    out: List[Dict[str, Any]] = []
    for s in suggestions:
        schema = s["schema"]
        table = s["table"]
        cols = s.get("columns", [])
        include = s.get("include", [])
        # strict dedupe
        existing = get_existing_indexes(conn, schema, table)
        skip = False
        for idx in existing:
            idx_cols, idx_inc = parse_indexdef_columns(idx["defn"])
            if [c.lower() for c in idx_cols] == [c.lower() for c in cols]:
                skip = True
                break
        if skip:
            continue
        name, ddl = build_index_ddl(schema, table, cols, include)
        s2 = dict(s)
        s2["index_name"] = name
        s2["create_index_ddl"] = ddl
        out.append(s2)
    return {"plan": plan, "suggestions": out}


def apply_index(conn, ddl: str) -> None:
    # CREATE INDEX CONCURRENTLY must run outside a transaction block
    set_statement_timeout(conn, None)  # let DDL run without per-statement timeout unless set by caller
    with conn.cursor() as cur:
        cur.execute(ddl)

