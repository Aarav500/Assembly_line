import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify, render_template, g
from datetime import datetime, timezone
from typing import Any, Dict, List

from db import get_db, close_db, init_db, ensure_db_initialized
from util import (
    parse_any_timestamp_ms,
    ms_to_iso8601,
    build_search_text,
    safe_json_dumps,
)


def create_app():
    app = Flask(__name__)
    app.config['DB_PATH'] = os.environ.get('LOGS_DB', os.path.join(os.getcwd(), 'logs.db'))
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

    @app.before_request
    def _before_request():
        ensure_db_initialized(app.config['DB_PATH'])

    @app.teardown_appcontext
    def _teardown(_exc):
        close_db()

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/logs', methods=['POST'])
    def ingest_logs():
        db = get_db()
        payload = request.get_json(silent=True) or {}

        # Accept either a single entry object or {"entries": [ ... ]}
        entries = []
        if isinstance(payload, dict) and 'entries' in payload and isinstance(payload['entries'], list):
            entries = payload['entries']
        elif isinstance(payload, list):
            entries = payload
        elif isinstance(payload, dict):
            # Treat as single entry
            entries = [payload]
        else:
            return jsonify({"error": "Invalid JSON payload"}), 400

        normalized_rows = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            message = str(e.get('message', ''))
            if not message:
                # skip empty messages
                continue

            ts_ms = None
            ts_val = e.get('timestamp') or e.get('ts') or e.get('time')
            try:
                ts_ms = parse_any_timestamp_ms(ts_val)
            except Exception:
                ts_ms = None
            if ts_ms is None:
                ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            ts_iso = ms_to_iso8601(ts_ms)

            level = (e.get('level') or e.get('lvl') or 'INFO').upper()
            service = e.get('service') or e.get('svc')
            environment = e.get('environment') or e.get('env')
            user_id = e.get('user_id') or e.get('user')
            request_id = e.get('request_id') or e.get('trace_id') or e.get('corr_id')
            host = e.get('host') or e.get('hostname')
            app_version = e.get('app_version') or e.get('version')
            logger_name = e.get('logger') or e.get('logger_name')
            thread_name = e.get('thread') or e.get('thread_name')

            # structured context
            context = e.get('context') or e.get('ctx') or {}
            # merge any extra fields under 'extra' if present
            extra = e.get('extra') or {}
            if not isinstance(context, dict):
                context = {"_context": str(context)}
            if not isinstance(extra, dict):
                extra = {"_extra": str(extra)}

            # Also include any arbitrary fields that are not standard into extra
            standard_keys = {
                'message','timestamp','ts','time','level','lvl','service','svc','environment','env','user_id','user',
                'request_id','trace_id','corr_id','host','hostname','app_version','version','logger','logger_name',
                'thread','thread_name','context','ctx','extra'
            }
            for k, v in list(e.items()):
                if k not in standard_keys:
                    extra[k] = v

            extra_json = safe_json_dumps({"context": context, "extra": extra})

            search_text = build_search_text(
                message=message,
                level=level,
                service=service,
                environment=environment,
                user_id=user_id,
                request_id=request_id,
                host=host,
                app_version=app_version,
                logger_name=logger_name,
                thread_name=thread_name,
                context=context,
                extra=extra,
            )

            normalized_rows.append((
                ts_ms,
                ts_iso,
                level,
                message,
                service,
                environment,
                user_id,
                request_id,
                host,
                app_version,
                logger_name,
                thread_name,
                extra_json,
                search_text,
            ))

        if not normalized_rows:
            return jsonify({"ingested": 0})

        db.executemany(
            """
            INSERT INTO logs (
                ts, ts_iso, level, message, service, environment, user_id, request_id,
                host, app_version, logger_name, thread_name, extra_json, search_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            normalized_rows,
        )
        db.commit()

        return jsonify({"ingested": len(normalized_rows)})

    @app.route('/api/logs', methods=['GET'])
    def query_logs():
        db = get_db()
        args = request.args
        q = args.get('q')
        level = args.get('level')
        service = args.get('service')
        environment = args.get('environment') or args.get('env')
        user_id = args.get('user_id')
        request_id = args.get('request_id') or args.get('trace_id') or args.get('corr_id')
        host = args.get('host')
        ts_from = args.get('from') or args.get('start')
        ts_to = args.get('to') or args.get('end')
        sort = args.get('sort', 'desc').lower()
        limit = int(args.get('limit', '100'))
        offset = int(args.get('offset', '0'))
        if limit > 1000:
            limit = 1000

        where = []
        params: List[Any] = []
        join_fts = False

        if q:
            join_fts = True
            where.append('logs_fts.search_text MATCH ?')
            params.append(q)

        if level:
            where.append('logs.level = ?')
            params.append(level.upper())
        if service:
            where.append('logs.service = ?')
            params.append(service)
        if environment:
            where.append('logs.environment = ?')
            params.append(environment)
        if user_id:
            where.append('logs.user_id = ?')
            params.append(user_id)
        if request_id:
            where.append('logs.request_id = ?')
            params.append(request_id)
        if host:
            where.append('logs.host = ?')
            params.append(host)

        if ts_from:
            try:
                ts_from_ms = parse_any_timestamp_ms(ts_from)
                where.append('logs.ts >= ?')
                params.append(ts_from_ms)
            except Exception:
                pass
        if ts_to:
            try:
                ts_to_ms = parse_any_timestamp_ms(ts_to)
                where.append('logs.ts <= ?')
                params.append(ts_to_ms)
            except Exception:
                pass

        base = 'SELECT logs.* FROM logs'
        if join_fts:
            base += ' JOIN logs_fts ON logs_fts.rowid = logs.id'

        if where:
            base += ' WHERE ' + ' AND '.join(where)

        order_clause = ' ORDER BY logs.ts DESC' if sort != 'asc' else ' ORDER BY logs.ts ASC'
        limit_clause = ' LIMIT ? OFFSET ?'
        params_with_pagination = params + [limit + 1, offset]

        cur = db.execute(base + order_clause + limit_clause, params_with_pagination)
        rows = cur.fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]

        items = []
        for r in rows:
            try:
                extra_obj = json.loads(r['extra_json']) if r['extra_json'] else None
            except Exception:
                extra_obj = None
            items.append({
                'id': r['id'],
                'timestamp': r['ts_iso'],
                'ts': r['ts'],
                'level': r['level'],
                'message': r['message'],
                'service': r['service'],
                'environment': r['environment'],
                'user_id': r['user_id'],
                'request_id': r['request_id'],
                'host': r['host'],
                'app_version': r['app_version'],
                'logger_name': r['logger_name'],
                'thread_name': r['thread_name'],
                'context': (extra_obj or {}).get('context') if extra_obj else None,
                'extra': (extra_obj or {}).get('extra') if extra_obj else None,
            })

        return jsonify({
            'items': items,
            'count': len(items),
            'has_more': has_more,
            'next_offset': (offset + len(items)) if has_more else None,
        })

    @app.route('/api/stats', methods=['GET'])
    def stats():
        db = get_db()
        # counts by level and service
        levels = db.execute('SELECT level, COUNT(*) as c FROM logs GROUP BY level ORDER BY c DESC').fetchall()
        services = db.execute('SELECT service, COUNT(*) as c FROM logs GROUP BY service ORDER BY c DESC LIMIT 50').fetchall()
        envs = db.execute('SELECT environment, COUNT(*) as c FROM logs GROUP BY environment ORDER BY c DESC').fetchall()
        return jsonify({
            'levels': [{"level": r['level'], "count": r['c']} for r in levels],
            'services': [{"service": r['service'], "count": r['c']} for r in services],
            'environments': [{"environment": r['environment'], "count": r['c']} for r in envs],
        })

    return app


if __name__ == '__main__':
    app = create_app()
    # Initialize DB on startup
    init_db(app.config['DB_PATH'])
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000')), debug=bool(os.environ.get('DEBUG'))) 



@app.route('/logs/search', methods=['GET'])
def _auto_stub_logs_search():
    return 'Auto-generated stub for /logs/search', 200


@app.route('/logs/search?q=error', methods=['GET'])
def _auto_stub_logs_search_q_error():
    return 'Auto-generated stub for /logs/search?q=error', 200


@app.route('/logs/stats', methods=['GET'])
def _auto_stub_logs_stats():
    return 'Auto-generated stub for /logs/stats', 200
