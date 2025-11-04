import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from sqlalchemy.orm import scoped_session
from storage import init_db, get_session, Alert, Incident
from models import ModelManager
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize DB and model manager
engine = init_db(app.config.get('DATABASE_URL'))
session_factory = get_session(engine)
db = scoped_session(session_factory)
model_manager = ModelManager(model_dir=app.config.get('MODEL_DIR'))


def parse_timestamp(ts_str: str | None) -> datetime:
    if not ts_str:
        return datetime.utcnow()
    try:
        # Python 3.11 supports fromisoformat with Z
        if ts_str.endswith('Z'):
            ts_str = ts_str[:-1]
        return datetime.fromisoformat(ts_str)
    except Exception:
        # Fallback: try multiple formats
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(ts_str, fmt)
            except Exception:
                continue
        return datetime.utcnow()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db.remove()


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@app.route('/alerts', methods=['POST'])
def ingest_alert():
    payload = request.get_json(force=True, silent=True) or {}

    required = ["source", "service", "severity", "category", "message"]
    missing = [k for k in required if k not in payload]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    ts = parse_timestamp(payload.get("timestamp"))
    metadata = payload.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        return jsonify({"error": "metadata must be an object"}), 400

    alert = Alert(
        timestamp=ts,
        source=str(payload.get("source"))[:128],
        service=str(payload.get("service"))[:128],
        severity=str(payload.get("severity"))[:32].lower(),
        category=str(payload.get("category"))[:64].lower(),
        message=str(payload.get("message"))[:2000],
        metadata=json.dumps(metadata) if metadata is not None else None,
    )

    db.add(alert)
    db.commit()

    # Apply ML noise reduction
    try:
        score, is_noise, used_model = model_manager.score_alert(db, alert)
    except Exception as e:
        # Fallback simple heuristic if model fails
        score = 0.0
        is_noise = alert.severity in ("info", "low")
        used_model = "fallback"

    alert.noise_score = score
    alert.is_noise = is_noise
    db.commit()

    incident_id = None
    if not is_noise:
        try:
            incident_id = model_manager.assign_incident(db, alert)
            db.commit()
        except Exception:
            incident_id = None

    return jsonify({
        "id": alert.id,
        "timestamp": alert.timestamp.isoformat() + "Z",
        "source": alert.source,
        "service": alert.service,
        "severity": alert.severity,
        "category": alert.category,
        "is_noise": bool(alert.is_noise),
        "noise_score": alert.noise_score,
        "incident_id": incident_id,
        "model": used_model,
    })


@app.route('/alerts', methods=['GET'])
def list_alerts():
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = min(200, max(1, int(request.args.get('page_size', 50))))
    except Exception:
        page, page_size = 1, 50

    q = db.query(Alert).order_by(Alert.timestamp.desc(), Alert.id.desc())
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for a in rows:
        items.append({
            "id": a.id,
            "timestamp": a.timestamp.isoformat() + "Z",
            "source": a.source,
            "service": a.service,
            "severity": a.severity,
            "category": a.category,
            "message": a.message,
            "is_noise": bool(a.is_noise) if a.is_noise is not None else None,
            "noise_score": a.noise_score,
            "incident_id": a.incident_id,
        })

    return jsonify({
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items,
    })


@app.route('/incidents', methods=['GET'])
def list_incidents():
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = min(200, max(1, int(request.args.get('page_size', 50))))
    except Exception:
        page, page_size = 1, 50

    q = db.query(Incident).order_by(Incident.updated_at.desc(), Incident.id.desc())
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    out = []
    for inc in rows:
        out.append({
            "id": inc.id,
            "created_at": inc.created_at.isoformat() + "Z",
            "updated_at": inc.updated_at.isoformat() + "Z",
            "size": inc.size,
            "severity": inc.severity,
            "summary": inc.summary,
        })

    return jsonify({"page": page, "page_size": page_size, "total": total, "items": out})


@app.route('/incidents/<int:incident_id>', methods=['GET'])
def get_incident(incident_id: int):
    inc = db.query(Incident).get(incident_id)
    if not inc:
        return jsonify({"error": "not found"}), 404
    alerts = db.query(Alert).filter(Alert.incident_id == inc.id).order_by(Alert.timestamp.asc()).all()
    items = []
    for a in alerts:
        items.append({
            "id": a.id,
            "timestamp": a.timestamp.isoformat() + "Z",
            "source": a.source,
            "service": a.service,
            "severity": a.severity,
            "category": a.category,
            "message": a.message,
            "is_noise": bool(a.is_noise) if a.is_noise is not None else None,
            "noise_score": a.noise_score,
        })
    return jsonify({
        "id": inc.id,
        "created_at": inc.created_at.isoformat() + "Z",
        "updated_at": inc.updated_at.isoformat() + "Z",
        "size": inc.size,
        "severity": inc.severity,
        "summary": inc.summary,
        "alerts": items,
    })


@app.route('/train', methods=['POST'])
def train_models():
    body = request.get_json(silent=True) or {}
    min_samples = int(body.get('min_samples', 30))
    retrain_correlator = bool(body.get('retrain_correlator', True))

    total, trained = model_manager.fit_noise_model(db, min_samples=min_samples)
    if retrain_correlator:
        model_manager.reindex_incidents(db)
    db.commit()

    return jsonify({
        "alerts_seen": total,
        "noise_model_trained": trained,
        "correlator_reindexed": retrain_correlator,
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



def create_app():
    return app


@app.route('/alerts/correlate', methods=['POST'])
def _auto_stub_alerts_correlate():
    return 'Auto-generated stub for /alerts/correlate', 200
