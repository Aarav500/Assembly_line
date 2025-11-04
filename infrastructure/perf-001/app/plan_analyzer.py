import json
import re
from typing import Any, Dict, List, Optional, Tuple, Set
from .db import set_statement_timeout, reset_statement_timeout, fetchall_dicts
from .utils import quote_ident


def explain_query(conn, query: str, analyze: bool = False, buffers: bool = True, timeout_ms: Optional[int] = None) -> Dict[str, Any]:
    set_statement_timeout(conn, timeout_ms)
    try:
        with conn.cursor() as cur:
            opts = [f"ANALYZE {'true' if analyze else 'false'}", f"BUFFERS {'true' if buffers else 'false'}", "FORMAT JSON"]
            cur.execute(f"EXPLAIN ({', '.join(opts)}) {query}")
            plan_rows = cur.fetchall()
            # result is a single row with a JSON plan string per line
            if not plan_rows:
                raise RuntimeError("No EXPLAIN output")
            plan_json = plan_rows[0][0][0]  # EXPLAIN (FORMAT JSON) returns a one-element array
            return plan_json
    finally:
        reset_statement_timeout(conn)


# Helpers to interact with catalog for table stats and existing indexes

def get_table_row_estimate(conn, schema: str, table: str) -> Optional[int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(reltuples::bigint, 0)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table),
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None


def get_existing_indexes(conn, schema: str, table: str) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s
            """,
            (schema, table),
        )
        return [dict(name=r[0], defn=r[1]) for r in cur.fetchall()]


def get_column_stats(conn, schema: str, table: str) -> Dict[str, Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT attname, null_frac, n_distinct
            FROM pg_stats
            WHERE schemaname = %s AND tablename = %s
            """,
            (schema, table),
        )
        stats = {}
        for attname, null_frac, n_distinct in cur.fetchall():
            stats[str(attname)] = {"null_frac": null_frac, "n_distinct": n_distinct}
        return stats


# Expression parsing
_tbl_col_re = re.compile(r"(?:(?:\b|\()([A-Za-z_][A-Za-z0-9_$]*)\.)?\s*\(?\"?([A-Za-z_][A-Za-z0-9_$]*)\"?\)?")
_col_op_re = re.compile(r"\b([A-Za-z_][A-Za-z0-9_$]*)(?:\.([A-Za-z_][A-Za-z0-9_$]*))?\s*(=|!=|<>|>=|<=|>|<|IN|ANY|BETWEEN)\b", re.IGNORECASE)


def extract_columns_from_expression(expr: str) -> List[Tuple[Optional[str], str]]:
    cols: List[Tuple[Optional[str], str]] = []
    # Try to capture left-hand sides of comparisons or lists
    for m in _col_op_re.finditer(expr or ""):
        tbl = m.group(1)
        col = m.group(2)
        if col is None:
            # form: col <op>
            cols.append((None, m.group(1)))
        else:
            cols.append((tbl, col))
    # Fallback: any table.col references
    if not cols:
        for m in _tbl_col_re.finditer(expr or ""):
            tbl = m.group(1)
            col = m.group(2)
            cols.append((tbl, col))
    # Deduplicate preserving order
    seen: Set[Tuple[Optional[str], str]] = set()
    out = []
    for c in cols:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out


def extract_output_columns(node: Dict[str, Any]) -> List[Tuple[Optional[str], str]]:
    out_cols: List[Tuple[Optional[str], str]] = []
    for item in node.get("Output", []):
        # e.g., 'table.col', 'col'
        parts = [p.strip() for p in item.split(".")]
        if len(parts) == 2:
            out_cols.append((parts[0].strip('"'), parts[1].strip('"')))
        elif len(parts) == 1:
            out_cols.append((None, parts[0].strip('"')))
    return out_cols


def find_base_rel_node(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Find first child node with Relation Name
    if "Relation Name" in node:
        return node
    for child in node.get("Plans", []) or []:
        r = find_base_rel_node(child)
        if r:
            return r
    return None


def traverse_plan(node: Dict[str, Any], visit):
    visit(node)
    for ch in node.get("Plans", []) or []:
        traverse_plan(ch, visit)


def analyze_plan_for_suggestions(conn, plan: Dict[str, Any], min_table_rows_for_index: int = 10000) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []

    # Cache existing indexes and stats per table
    cache_indexes: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    cache_stats: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def get_cached_indexes(schema: str, table: str):
        key = (schema, table)
        if key not in cache_indexes:
            cache_indexes[key] = get_existing_indexes(conn, schema, table)
        return cache_indexes[key]

    def get_cached_stats(schema: str, table: str):
        key = (schema, table)
        if key not in cache_stats:
            cache_stats[key] = get_column_stats(conn, schema, table)
        return cache_stats[key]

    def has_similar_index(schema: str, table: str, cols: List[str]) -> bool:
        existing = get_cached_indexes(schema, table)
        from .utils import parse_indexdef_columns
        for idx in existing:
            idx_cols, _ = parse_indexdef_columns(idx["defn"])
            # Check if existing index starts with proposed columns (prefix match)
            if len(idx_cols) >= len(cols) and [c.lower() for c in idx_cols[: len(cols)]] == [c.lower() for c in cols]:
                return True
        return False

    def good_selectivity(schema: str, table: str, col: str) -> bool:
        stats = get_cached_stats(schema, table)
        s = stats.get(col)
        if not s:
            return True  # unknown -> assume good
        nd = s.get("n_distinct")
        if nd is None:
            return True
        try:
            nd_val = float(nd)
        except Exception:
            return True
        # if n_distinct is negative, it's a fraction of rows, reasonable
        if nd_val < 0:
            return abs(nd_val) >= 0.01
        return nd_val >= 50  # at least 50 distinct values

    def maybe_add_suggestion(s: Dict[str, Any]):
        # de-duplicate by key
        key = (
            s.get("schema"), s.get("table"), tuple(s.get("columns", [])), tuple(s.get("include", [])), s.get("purpose", "")
        )
        if not any(
            x.get("schema") == key[0]
            and x.get("table") == key[1]
            and tuple(x.get("columns", [])) == key[2]
            and tuple(x.get("include", [])) == key[3]
            and x.get("purpose") == key[4]
            for x in suggestions
        ):
            suggestions.append(s)

    def handle_seq_scan(node: Dict[str, Any]):
        rel = node.get("Relation Name")
        schema = node.get("Schema") or "public"
        if not rel:
            return
        rows_est = get_table_row_estimate(conn, schema, rel) or 0
        if rows_est < min_table_rows_for_index:
            return
        filt = node.get("Filter")
        if not filt:
            return
        cols = extract_columns_from_expression(filt)
        # Normalize columns to this table
        key_cols: List[str] = []
        for tbl, col in cols:
            if tbl is None or tbl == rel:
                if good_selectivity(schema, rel, col):
                    if col not in key_cols:
                        key_cols.append(col)
        if not key_cols:
            return
        if has_similar_index(schema, rel, key_cols):
            return
        # INCLUDE output columns to help covering
        include: List[str] = []
        for t, c in extract_output_columns(node):
            if t in (None, rel) and c not in key_cols and c not in include:
                include.append(c)
        maybe_add_suggestion(
            {
                "schema": schema,
                "table": rel,
                "columns": key_cols[:3],  # cap for practicality
                "include": include[:5],
                "purpose": "Filter optimization for sequential scan",
                "evidence": {"Filter": filt, "Plan Rows": node.get("Plan Rows"), "Total Cost": node.get("Total Cost")},
            }
        )

    def handle_sort(node: Dict[str, Any]):
        sort_keys = node.get("Sort Key") or []
        if not sort_keys:
            return
        base = find_base_rel_node(node)
        if not base:
            return
        rel = base.get("Relation Name")
        schema = base.get("Schema") or "public"
        if not rel:
            return
        rows_est = get_table_row_estimate(conn, schema, rel) or 0
        if rows_est < min_table_rows_for_index:
            return
        # Extract equality filters from base node if any
        eq_cols: List[str] = []
        filt = base.get("Filter") or ""
        for tbl, col in extract_columns_from_expression(filt):
            if (tbl is None or tbl == rel) and col not in eq_cols:
                eq_cols.append(col)
        # Sort columns parsing
        sort_cols: List[str] = []
        for k in sort_keys:
            parts = k.split(" ")
            colref = parts[0]
            if "." in colref:
                t, c = colref.split(".", 1)
                if t.strip('"') != rel:
                    continue
                col = c.strip('"')
            else:
                col = colref.strip('"')
            if col not in sort_cols:
                sort_cols.append(col)
        key_cols = []
        for c in eq_cols:
            if c not in key_cols:
                key_cols.append(c)
        for c in sort_cols:
            if c not in key_cols:
                key_cols.append(c)
        if not key_cols:
            return
        if has_similar_index(schema, rel, key_cols):
            return
        maybe_add_suggestion(
            {
                "schema": schema,
                "table": rel,
                "columns": key_cols[:3],
                "include": [],
                "purpose": "Support ORDER BY and filtering",
                "evidence": {"Sort Key": sort_keys, "Filter": filt},
            }
        )

    def handle_group(node: Dict[str, Any]):
        grp_keys = node.get("Group Key") or []
        if not grp_keys:
            return
        base = find_base_rel_node(node)
        if not base:
            return
        rel = base.get("Relation Name")
        schema = base.get("Schema") or "public"
        if not rel:
            return
        rows_est = get_table_row_estimate(conn, schema, rel) or 0
        if rows_est < min_table_rows_for_index:
            return
        cols: List[str] = []
        for k in grp_keys:
            colref = k.split(" ")[0]
            if "." in colref:
                t, c = colref.split(".")
                if t.strip('"') != rel:
                    continue
                col = c.strip('"')
            else:
                col = colref.strip('"')
            if col not in cols:
                cols.append(col)
        if not cols:
            return
        if has_similar_index(schema, rel, cols):
            return
        maybe_add_suggestion(
            {
                "schema": schema,
                "table": rel,
                "columns": cols[:3],
                "include": [],
                "purpose": "Support GROUP BY",
                "evidence": {"Group Key": grp_keys},
            }
        )

    def handle_join(node: Dict[str, Any]):
        node_type = node.get("Node Type", "")
        cond = node.get("Hash Cond") or node.get("Merge Cond") or node.get("Join Filter")
        if not cond:
            return
        # extract pairs a.col = b.col
        m = re.findall(r"([A-Za-z_][A-Za-z0-9_$]*)\.\"?([A-Za-z_][A-Za-z0-9_$]*)\"?\s*=\s*([A-Za-z_][A-Za-z0-9_$]*)\.\"?([A-Za-z_][A-Za-z0-9_$]*)\"?", cond)
        for a_tbl, a_col, b_tbl, b_col in m:
            # Prefer indexing the larger side or inner side
            # Find child nodes to match relation names
            rels: Dict[str, Tuple[str, int]] = {}
            for ch in (node.get("Plans") or []):
                base = find_base_rel_node(ch)
                if base and base.get("Relation Name"):
                    schema = base.get("Schema") or "public"
                    t = base.get("Relation Name")
                    rows = get_table_row_estimate(conn, schema, t) or 0
                    rels[t] = (schema, rows)
            for t_name, col in ((a_tbl, a_col), (b_tbl, b_col)):
                if t_name in rels:
                    schema, rows = rels[t_name]
                    if rows >= min_table_rows_for_index and not has_similar_index(schema, t_name, [col]) and good_selectivity(schema, t_name, col):
                        maybe_add_suggestion(
                            {
                                "schema": schema,
                                "table": t_name,
                                "columns": [col],
                                "include": [],
                                "purpose": f"Accelerate {node_type} on join key",
                                "evidence": {"Join Cond": cond},
                            }
                        )

    root = plan.get("Plan", {})

    def visit(n):
        nt = n.get("Node Type", "")
        if nt == "Seq Scan":
            handle_seq_scan(n)
        elif nt == "Sort":
            handle_sort(n)
        elif nt in ("Aggregate", "GroupAggregate", "HashAggregate"):
            handle_group(n)
        elif nt in ("Hash Join", "Merge Join", "Nested Loop"):
            handle_join(n)

    traverse_plan(root, visit)
    return suggestions


def build_index_ddl(schema: str, table: str, columns: List[str], include: Optional[List[str]] = None, name: Optional[str] = None) -> Tuple[str, str]:
    include = include or []
    if not name:
        from .utils import ensure_length, short_hash
        base = f"ix_{table}_{'_'.join(columns)}"
        name = ensure_length(f"{base}_{short_hash(schema + '.' + table + '(' + ','.join(columns) + ')')}")
    q_schema = quote_ident(schema)
    q_table = quote_ident(table)
    cols_expr = ", ".join(quote_ident(c) for c in columns)
    ddl = f"CREATE INDEX CONCURRENTLY {quote_ident(name)} ON {q_schema}.{q_table} USING btree ({cols_expr})"
    if include:
        ddl += f" INCLUDE ({', '.join(quote_ident(c) for c in include)})"
    ddl += ";"
    return name, ddl

