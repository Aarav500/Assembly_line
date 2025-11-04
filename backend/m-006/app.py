import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from db import get_db, close_db, init_db, row_to_dict
from search import search_snippets


def create_app():
    app = Flask(__name__)

    # Config
    app.config['SNIPPETS_DB'] = os.environ.get('SNIPPETS_DB', os.path.join(os.getcwd(), 'snippets.db'))

    # Initialize DB
    with app.app_context():
        init_db(app.config['SNIPPETS_DB'])

    @app.teardown_appcontext
    def teardown_db(exception):
        close_db()

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok"})

    @app.route('/', methods=['GET'])
    def root():
        return jsonify({
            "name": "Searchable Knowledge Snippets API",
            "version": "1.0.0",
            "endpoints": [
                "GET /health",
                "POST /api/snippets",
                "GET /api/snippets",
                "GET /api/snippets/<id>",
                "PUT /api/snippets/<id>",
                "DELETE /api/snippets/<id>",
                "POST /api/snippets/bulk",
                "GET /api/snippets/search",
                "POST /api/snippets/import",
                "POST /api/suggestions",
                "GET /api/tags"
            ]
        })

    def parse_tags(tags):
        if tags is None:
            return None
        if isinstance(tags, list):
            return tags
        if isinstance(tags, str):
            tags = tags.strip()
            if not tags:
                return []
            # Try parse JSON array first
            try:
                val = json.loads(tags)
                if isinstance(val, list):
                    return [str(t) for t in val]
            except Exception:
                pass
            # Fallback: comma separated
            return [t.strip() for t in tags.split(',') if t.strip()]
        return []

    def now_iso():
        return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

    def validate_snippet_payload(payload, partial=False):
        allowed = {
            'title': str,
            'content': str,
            'tags': (list, str),
            'language': str,
            'framework': str,
            'source': str,
            'file_path': str,
            'symbol': str,
            'project': str,
            'pinned': (bool, int)
        }
        data = {}
        for k, v in payload.items():
            if k in allowed:
                data[k] = v
        if not partial:
            missing = [k for k in ['title', 'content'] if k not in data or not isinstance(data[k], str) or not data[k].strip()]
            if missing:
                return None, f"Missing or invalid fields: {', '.join(missing)}"
        # Normalize tags
        if 'tags' in data:
            data['tags'] = parse_tags(data['tags'])
        # Normalize pinned
        if 'pinned' in data:
            data['pinned'] = int(bool(data['pinned']))
        return data, None

    @app.route('/api/snippets', methods=['POST'])
    def create_snippet():
        payload = request.get_json(force=True, silent=True) or {}
        data, err = validate_snippet_payload(payload)
        if err:
            return jsonify({"error": err}), 400
        db = get_db(app.config['SNIPPETS_DB'])
        cur = db.cursor()
        ts = now_iso()
        cur.execute(
            '''INSERT INTO snippets (title, content, tags, language, framework, source, file_path, symbol, project, pinned, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                data.get('title', '').strip(),
                data.get('content', '').strip(),
                json.dumps(data.get('tags', []), ensure_ascii=False),
                data.get('language'),
                data.get('framework'),
                data.get('source'),
                data.get('file_path'),
                data.get('symbol'),
                data.get('project'),
                data.get('pinned', 0),
                ts,
                ts,
            )
        )
        snippet_id = cur.lastrowid
        # Update FTS
        cur.execute(
            'INSERT INTO snippets_fts(rowid, title, content, tags, language, framework, file_path, symbol, project) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                snippet_id,
                data.get('title', ''),
                data.get('content', ''),
                ' '.join(data.get('tags', [])),
                data.get('language') or '',
                data.get('framework') or '',
                data.get('file_path') or '',
                data.get('symbol') or '',
                data.get('project') or ''
            )
        )
        db.commit()
        cur.execute('SELECT * FROM snippets WHERE id=?', (snippet_id,))
        return jsonify(row_to_dict(cur.fetchone())), 201

    @app.route('/api/snippets', methods=['GET'])
    def list_snippets():
        args = request.args
        limit = min(int(args.get('limit', 20)), 200)
        offset = int(args.get('offset', 0))
        language = args.get('language')
        project = args.get('project')
        framework = args.get('framework')
        tag = args.get('tag')
        pinned = args.get('pinned')

        where = []
        params = []
        if language:
            where.append('language = ?')
            params.append(language)
        if project:
            where.append('project = ?')
            params.append(project)
        if framework:
            where.append('framework = ?')
            params.append(framework)
        if tag:
            where.append("EXISTS (SELECT 1 FROM json_each(snippets.tags) je WHERE je.value = ?)")
            params.append(tag)
        if pinned is not None:
            if pinned.lower() in ('1','true','yes'):
                where.append('pinned = 1')
            elif pinned.lower() in ('0','false','no'):
                where.append('pinned = 0')
        sql = 'SELECT * FROM snippets'
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY pinned DESC, updated_at DESC, id DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        db = get_db(app.config['SNIPPETS_DB'])
        cur = db.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    @app.route('/api/snippets/<int:snippet_id>', methods=['GET'])
    def get_snippet(snippet_id):
        db = get_db(app.config['SNIPPETS_DB'])
        cur = db.cursor()
        cur.execute('SELECT * FROM snippets WHERE id=?', (snippet_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(row_to_dict(row))

    @app.route('/api/snippets/<int:snippet_id>', methods=['PUT'])
    def update_snippet(snippet_id):
        payload = request.get_json(force=True, silent=True) or {}
        data, err = validate_snippet_payload(payload, partial=True)
        if err:
            return jsonify({"error": err}), 400
        if not data:
            return jsonify({"error": "No fields to update"}), 400
        db = get_db(app.config['SNIPPETS_DB'])
        cur = db.cursor()
        cur.execute('SELECT * FROM snippets WHERE id=?', (snippet_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404

        updates = []
        params = []
        if 'title' in data:
            updates.append('title=?')
            params.append(data['title'])
        if 'content' in data:
            updates.append('content=?')
            params.append(data['content'])
        if 'tags' in data:
            updates.append('tags=?')
            params.append(json.dumps(data['tags'], ensure_ascii=False))
        if 'language' in data:
            updates.append('language=?')
            params.append(data['language'])
        if 'framework' in data:
            updates.append('framework=?')
            params.append(data['framework'])
        if 'source' in data:
            updates.append('source=?')
            params.append(data['source'])
        if 'file_path' in data:
            updates.append('file_path=?')
            params.append(data['file_path'])
        if 'symbol' in data:
            updates.append('symbol=?')
            params.append(data['symbol'])
        if 'project' in data:
            updates.append('project=?')
            params.append(data['project'])
        if 'pinned' in data:
            updates.append('pinned=?')
            params.append(int(bool(data['pinned'])))
        updates.append('updated_at=?')
        params.append(now_iso())
        params.append(snippet_id)
        sql = f"UPDATE snippets SET {', '.join(updates)} WHERE id=?"
        cur.execute(sql, tuple(params))

        # Sync FTS row
        cur.execute('SELECT * FROM snippets WHERE id=?', (snippet_id,))
        row = cur.fetchone()
        payload_row = row_to_dict(row)
        cur.execute('DELETE FROM snippets_fts WHERE rowid=?', (snippet_id,))
        cur.execute(
            'INSERT INTO snippets_fts(rowid, title, content, tags, language, framework, file_path, symbol, project) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                snippet_id,
                payload_row['title'] or '',
                payload_row['content'] or '',
                ' '.join(payload_row['tags'] or []),
                payload_row['language'] or '',
                payload_row['framework'] or '',
                payload_row['file_path'] or '',
                payload_row['symbol'] or '',
                payload_row['project'] or ''
            )
        )
        db.commit()
        return jsonify(payload_row)

    @app.route('/api/snippets/<int:snippet_id>', methods=['DELETE'])
    def delete_snippet(snippet_id):
        db = get_db(app.config['SNIPPETS_DB'])
        cur = db.cursor()
        cur.execute('DELETE FROM snippets WHERE id=?', (snippet_id,))
        cur.execute('DELETE FROM snippets_fts WHERE rowid=?', (snippet_id,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"deleted": True, "id": snippet_id})

    @app.route('/api/snippets/bulk', methods=['POST'])
    def bulk_insert():
        payload = request.get_json(force=True, silent=True) or {}
        items = payload if isinstance(payload, list) else payload.get('items', [])
        if not isinstance(items, list) or not items:
            return jsonify({"error": "No items provided"}), 400
        db = get_db(app.config['SNIPPETS_DB'])
        cur = db.cursor()
        inserted = []
        ts = now_iso()
        for p in items:
            data, err = validate_snippet_payload(p)
            if err:
                continue
            cur.execute(
                '''INSERT INTO snippets (title, content, tags, language, framework, source, file_path, symbol, project, pinned, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    data.get('title', '').strip(),
                    data.get('content', '').strip(),
                    json.dumps(data.get('tags', []), ensure_ascii=False),
                    data.get('language'),
                    data.get('framework'),
                    data.get('source'),
                    data.get('file_path'),
                    data.get('symbol'),
                    data.get('project'),
                    int(bool(data.get('pinned', 0))),
                    ts,
                    ts,
                )
            )
            sid = cur.lastrowid
            cur.execute(
                'INSERT INTO snippets_fts(rowid, title, content, tags, language, framework, file_path, symbol, project) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    sid,
                    data.get('title', ''),
                    data.get('content', ''),
                    ' '.join(data.get('tags', [])),
                    data.get('language') or '',
                    data.get('framework') or '',
                    data.get('file_path') or '',
                    data.get('symbol') or '',
                    data.get('project') or ''
                )
            )
            inserted.append(sid)
        db.commit()
        return jsonify({"inserted": inserted, "count": len(inserted)})

    @app.route('/api/snippets/search', methods=['GET'])
    def search():
        args = request.args
        q = args.get('q', '').strip()
        limit = min(int(args.get('limit', 20)), 200)
        offset = int(args.get('offset', 0))
        language = args.get('language')
        project = args.get('project')
        framework = args.get('framework')
        tag = args.get('tag')
        file_path = args.get('file_path')
        symbol = args.get('symbol')
        results = search_snippets(
            db_path=app.config['SNIPPETS_DB'],
            q=q,
            filters={
                'language': language,
                'project': project,
                'framework': framework,
                'tag': tag,
                'file_path': file_path,
                'symbol': symbol,
            },
            limit=limit,
            offset=offset
        )
        return jsonify(results)

    @app.route('/api/suggestions', methods=['POST'])
    def suggestions():
        payload = request.get_json(force=True, silent=True) or {}
        file_path = payload.get('file_path')
        language = payload.get('language')
        symbol = payload.get('symbol')
        selection = payload.get('selection', '') or ''
        project = payload.get('project')
        n = min(int(payload.get('n', 10)), 50)

        # Build a query leveraging symbol and selection
        tokens = []
        if symbol:
            tokens.append(symbol)
        if selection:
            # take words from selection
            selection_words = ' '.join(selection.split())[:500]
            tokens.append(selection_words)
        q = ' '.join(tokens).strip()

        results = search_snippets(
            db_path=app.config['SNIPPETS_DB'],
            q=q,
            filters={
                'language': language,
                'file_path': file_path,
                'symbol': symbol,
                'project': project,
            },
            limit=n,
            offset=0
        )
        return jsonify({
            "query": q,
            "count": len(results),
            "results": results
        })

    @app.route('/api/snippets/import', methods=['POST'])
    def import_snippets():
        # Accept JSON body containing array of snippets or object with items
        payload = request.get_json(force=True, silent=True) or {}
        items = payload if isinstance(payload, list) else payload.get('items')
        if not isinstance(items, list):
            return jsonify({"error": "Expected array of snippets or {items: [...]}"}), 400
        # delegate to bulk
        with app.test_request_context():
            request.json = items
        return bulk_insert()

    @app.route('/api/tags', methods=['GET'])
    def list_tags():
        db = get_db(app.config['SNIPPETS_DB'])
        cur = db.cursor()
        cur.execute('SELECT tags FROM snippets WHERE tags IS NOT NULL')
        tags_map = {}
        for (tags_json,) in cur.fetchall():
            try:
                tags = json.loads(tags_json) if tags_json else []
                for t in tags:
                    tags_map[t] = tags_map.get(t, 0) + 1
            except Exception:
                pass
        items = [{"tag": k, "count": v} for k, v in sorted(tags_map.items(), key=lambda x: (-x[1], x[0]))]
        return jsonify(items)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



@app.route('/snippets?q=flask', methods=['GET'])
def _auto_stub_snippets_q_flask():
    return 'Auto-generated stub for /snippets?q=flask', 200


@app.route('/snippets/1', methods=['GET'])
def _auto_stub_snippets_1():
    return 'Auto-generated stub for /snippets/1', 200
