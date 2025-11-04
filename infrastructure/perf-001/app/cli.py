import argparse
import json
import sys
from .config import Config
from .db import get_connection
from .slow_queries import get_slow_queries
from .plan_analyzer import explain_query
from .index_suggester import suggest_indexes_for_query, apply_index


def cmd_slow_queries(args):
    cfg = Config.load()
    conn = get_connection(cfg)
    try:
        rows = get_slow_queries(conn, limit=args.limit, min_mean_ms=args.min_mean_ms, min_calls=args.min_calls, order_by=args.order)
        print(json.dumps({"slow_queries": rows}, indent=2))
    finally:
        conn.close()


def cmd_analyze_plan(args):
    cfg = Config.load()
    conn = get_connection(cfg)
    try:
        plan = explain_query(conn, args.query, analyze=args.analyze, buffers=True, timeout_ms=args.timeout_ms)
        print(json.dumps({"plan": plan}, indent=2))
    finally:
        conn.close()


def cmd_suggest_indexes(args):
    cfg = Config.load()
    conn = get_connection(cfg)
    try:
        result = suggest_indexes_for_query(
            conn,
            args.query,
            analyze=args.analyze,
            timeout_ms=args.timeout_ms,
            min_table_rows_for_index=cfg.min_table_rows_for_index,
        )
        print(json.dumps(result, indent=2))
        if args.apply:
            for s in result.get("suggestions", []):
                ddl = s.get("create_index_ddl")
                if ddl:
                    apply_index(conn, ddl)
                    print(json.dumps({"applied": s.get("index_name")}))
    finally:
        conn.close()


def build_parser():
    p = argparse.ArgumentParser(prog="dbqopt", description="Database query optimization toolkit for PostgreSQL")
    sub = p.add_subparsers(dest="cmd")

    p1 = sub.add_parser("slow-queries", help="List slow queries from pg_stat_statements")
    p1.add_argument("--limit", type=int, default=20)
    p1.add_argument("--min-mean-ms", type=float, default=50)
    p1.add_argument("--min-calls", type=int, default=5)
    p1.add_argument("--order", type=str, default="mean_time", choices=["mean_time", "total_time", "calls"])
    p1.set_defaults(func=cmd_slow_queries)

    p2 = sub.add_parser("analyze-plan", help="Run EXPLAIN (FORMAT JSON) on a query")
    p2.add_argument("--query", type=str, required=True)
    p2.add_argument("--analyze", action="store_true")
    p2.add_argument("--timeout-ms", type=int, default=None)
    p2.set_defaults(func=cmd_analyze_plan)

    p3 = sub.add_parser("suggest-indexes", help="Suggest indexes for a given query using its plan")
    p3.add_argument("--query", type=str, required=True)
    p3.add_argument("--analyze", action="store_true")
    p3.add_argument("--timeout-ms", type=int, default=None)
    p3.add_argument("--apply", action="store_true", help="Apply suggested indexes (CREATE INDEX CONCURRENTLY)")
    p3.set_defaults(func=cmd_suggest_indexes)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())

