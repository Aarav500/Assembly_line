import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload
from db import db_session, init_db
from models import KnowledgeItem, KnowledgeVersion
from utils import parse_as_of_param, utc_now_naive, to_iso8601


def create_app():
    app = Flask(__name__)

    # Initialize DB
    with app.app_context():
        init_db()

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    def get_item_or_404(key: str) -> KnowledgeItem:
        item = db_session.query(KnowledgeItem).filter(KnowledgeItem.key == key).first()
        if not item:
            return None
        return item

    def item_to_dict(item: KnowledgeItem):
        return {
            "key": item.key,
            "created_at": to_iso8601(item.created_at),
            "id": item.id,
        }

    def version_to_dict(v: KnowledgeVersion):
        return {
            "id": v.id,
            "item_id": v.item_id,
            "version": v.version_number,
            "content": v.content,
            "author": v.author,
            "created_at": to_iso8601(v.created_at),
        }

    @app.post("/items")
    def create_item_or_version():
        data = request.get_json(silent=True) or {}
        key = data.get("key")
        content = data.get("content")
        author = data.get("author")
        timestamp_str = data.get("timestamp")

        if not key:
            return jsonify({"error": "Missing 'key'"}), 400
        if not content:
            return jsonify({"error": "Missing 'content'"}), 400

        if timestamp_str:
            try:
                ts = parse_as_of_param(timestamp_str)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
        else:
            ts = utc_now_naive()

        item = db_session.query(KnowledgeItem).filter(KnowledgeItem.key == key).first()
        if item is None:
            # Create new item and version 1
            item = KnowledgeItem(key=key, created_at=ts)
            db_session.add(item)
            db_session.flush()  # to get item.id
            version_number = 1
            v = KnowledgeVersion(
                item_id=item.id,
                version_number=version_number,
                content=content,
                author=author,
                created_at=ts,
            )
            db_session.add(v)
            db_session.commit()
            return jsonify({"item": item_to_dict(item), "version": version_to_dict(v)}), 201
        else:
            # Append new version
            last = (
                db_session.query(KnowledgeVersion)
                .filter(KnowledgeVersion.item_id == item.id)
                .order_by(KnowledgeVersion.version_number.desc())
                .first()
            )
            if last and ts < last.created_at:
                return jsonify({
                    "error": "timestamp must be >= last version timestamp",
                    "last_version_created_at": to_iso8601(last.created_at),
                }), 400
            version_number = (last.version_number + 1) if last else 1
            v = KnowledgeVersion(
                item_id=item.id,
                version_number=version_number,
                content=content,
                author=author,
                created_at=ts,
            )
            db_session.add(v)
            db_session.commit()
            return jsonify({"item": item_to_dict(item), "version": version_to_dict(v)}), 201

    @app.post("/items/<string:key>/versions")
    def create_version(key):
        data = request.get_json(silent=True) or {}
        content = data.get("content")
        author = data.get("author")
        timestamp_str = data.get("timestamp")
        if not content:
            return jsonify({"error": "Missing 'content'"}), 400

        item = get_item_or_404(key)
        if not item:
            return jsonify({"error": "Item not found"}), 404

        if timestamp_str:
            try:
                ts = parse_as_of_param(timestamp_str)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
        else:
            ts = utc_now_naive()

        last = (
            db_session.query(KnowledgeVersion)
            .filter(KnowledgeVersion.item_id == item.id)
            .order_by(KnowledgeVersion.version_number.desc())
            .first()
        )
        if last and ts < last.created_at:
            return jsonify({
                "error": "timestamp must be >= last version timestamp",
                "last_version_created_at": to_iso8601(last.created_at),
            }), 400

        version_number = (last.version_number + 1) if last else 1
        v = KnowledgeVersion(
            item_id=item.id,
            version_number=version_number,
            content=content,
            author=author,
            created_at=ts,
        )
        db_session.add(v)
        db_session.commit()
        return jsonify({"item": item_to_dict(item), "version": version_to_dict(v)}), 201

    @app.get("/items/<string:key>")
    def get_item_snapshot(key):
        item = get_item_or_404(key)
        if not item:
            return jsonify({"error": "Item not found"}), 404

        version_param = request.args.get("version")
        as_of_param = request.args.get("as_of")

        if version_param:
            try:
                version_number = int(version_param)
            except ValueError:
                return jsonify({"error": "version must be an integer"}), 400
            v = (
                db_session.query(KnowledgeVersion)
                .filter(and_(KnowledgeVersion.item_id == item.id, KnowledgeVersion.version_number == version_number))
                .first()
            )
            if not v:
                return jsonify({"error": "Version not found"}), 404
            return jsonify({"item": item_to_dict(item), "version": version_to_dict(v)})

        # Time-travel by as_of
        try:
            as_of = parse_as_of_param(as_of_param) if as_of_param else utc_now_naive()
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        v = (
            db_session.query(KnowledgeVersion)
            .filter(and_(KnowledgeVersion.item_id == item.id, KnowledgeVersion.created_at <= as_of))
            .order_by(KnowledgeVersion.created_at.desc(), KnowledgeVersion.version_number.desc())
            .first()
        )
        if not v:
            return jsonify({"error": "No version exists at or before as_of"}), 404
        return jsonify({"item": item_to_dict(item), "version": version_to_dict(v)})

    @app.get("/items/<string:key>/versions")
    def list_versions(key):
        item = get_item_or_404(key)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        try:
            limit = int(request.args.get("limit", 50))
            offset = int(request.args.get("offset", 0))
        except ValueError:
            return jsonify({"error": "limit and offset must be integers"}), 400
        q = (
            db_session.query(KnowledgeVersion)
            .filter(KnowledgeVersion.item_id == item.id)
            .order_by(KnowledgeVersion.version_number.asc())
            .limit(limit)
            .offset(offset)
        )
        versions = [version_to_dict(v) for v in q.all()]
        return jsonify({"item": item_to_dict(item), "versions": versions, "limit": limit, "offset": offset})

    @app.get("/search")
    def search():
        q = request.args.get("q")
        if not q:
            return jsonify({"error": "Missing 'q'"}), 400
        try:
            as_of = parse_as_of_param(request.args.get("as_of")) if request.args.get("as_of") else utc_now_naive()
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        try:
            limit = int(request.args.get("limit", 50))
            offset = int(request.args.get("offset", 0))
        except ValueError:
            return jsonify({"error": "limit and offset must be integers"}), 400

        # Subquery to get latest version per item as_of timestamp
        from sqlalchemy import select
        sub = (
            db_session.query(
                KnowledgeVersion.item_id.label("item_id"),
                func.max(KnowledgeVersion.created_at).label("max_created_at"),
            )
            .filter(KnowledgeVersion.created_at <= as_of)
            .group_by(KnowledgeVersion.item_id)
            .subquery()
        )

        # Join with versions and items
        lower_q = f"%{q.lower()}%"
        rows = (
            db_session.query(KnowledgeItem, KnowledgeVersion)
            .join(sub, KnowledgeItem.id == sub.c.item_id)
            .join(
                KnowledgeVersion,
                and_(
                    KnowledgeVersion.item_id == sub.c.item_id,
                    KnowledgeVersion.created_at == sub.c.max_created_at,
                ),
            )
            .filter(func.lower(KnowledgeVersion.content).like(lower_q))
            .order_by(KnowledgeItem.key.asc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        results = []
        for item, version in rows:
            results.append(
                {
                    "item": item_to_dict(item),
                    "version": version_to_dict(version),
                }
            )
        return jsonify({"results": results, "limit": limit, "offset": offset, "as_of": to_iso8601(as_of), "q": q})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)



@app.route('/knowledge/test_key', methods=['GET', 'POST'])
def _auto_stub_knowledge_test_key():
    return 'Auto-generated stub for /knowledge/test_key', 200


@app.route('/knowledge/version_key', methods=['POST'])
def _auto_stub_knowledge_version_key():
    return 'Auto-generated stub for /knowledge/version_key', 200


@app.route('/knowledge/version_key/history', methods=['GET'])
def _auto_stub_knowledge_version_key_history():
    return 'Auto-generated stub for /knowledge/version_key/history', 200


@app.route('/knowledge/time_key', methods=['POST'])
def _auto_stub_knowledge_time_key():
    return 'Auto-generated stub for /knowledge/time_key', 200
