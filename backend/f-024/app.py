import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify
from datetime import datetime
from db import SessionLocal, init_db
from models import Event, AlertRule, Alert
from alerting import evaluate_rules, compute_metrics
from scheduler import start_scheduler


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    init_db()

    @app.route("/", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "business-metric-linked-alerts"})

    @app.route("/events", methods=["POST"])
    def create_event():
        data = request.get_json(force=True, silent=True) or {}
        etype = (data.get("type") or "").strip().lower()
        user_id = data.get("user_id")
        amount = data.get("amount")
        ts = data.get("timestamp")

        if etype not in {"visit", "signup", "purchase"}:
            return jsonify({"error": "Invalid event type. Must be one of: visit, signup, purchase"}), 400

        if etype == "purchase":
            if amount is None:
                return jsonify({"error": "'amount' is required for purchase events"}), 400
            try:
                amount = float(amount)
            except Exception:
                return jsonify({"error": "'amount' must be a number"}), 400
            if amount < 0:
                return jsonify({"error": "'amount' must be >= 0"}), 400
        else:
            amount = None

        created_at = None
        if ts:
            try:
                created_at = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                return jsonify({"error": "Invalid timestamp. Use ISO8601."}), 400

        s = SessionLocal()
        try:
            ev = Event(
                type=etype,
                user_id=user_id,
                amount=amount,
                created_at=created_at or datetime.utcnow(),
            )
            s.add(ev)
            s.commit()
            s.refresh(ev)
            return jsonify(ev.to_dict()), 201
        except Exception as e:
            s.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            s.close()

    @app.route("/metrics", methods=["GET"])
    def get_metrics():
        try:
            window_minutes = int(request.args.get("window_minutes", 60))
            if window_minutes <= 0:
                return jsonify({"error": "window_minutes must be > 0"}), 400
        except Exception:
            return jsonify({"error": "window_minutes must be an integer"}), 400
        s = SessionLocal()
        try:
            data = compute_metrics(s, window_minutes)
            return jsonify({"window_minutes": window_minutes, **data})
        finally:
            s.close()

    @app.route("/alert-rules", methods=["POST"])
    def create_alert_rule():
        data = request.get_json(force=True, silent=True) or {}
        name = (data.get("name") or "").strip()
        metric = (data.get("metric") or "").strip().lower()
        comparator = (data.get("comparator") or "").strip().lower()
        threshold = data.get("threshold")
        window_minutes = data.get("window_minutes")
        cool_down_minutes = data.get("cool_down_minutes", 60)
        is_active = bool(data.get("is_active", True))
        channels = data.get("channels", [{"type": "console"}])

        if not name:
            return jsonify({"error": "name is required"}), 400
        if metric not in {"revenue", "conversion_rate", "signups"}:
            return jsonify({"error": "metric must be one of: revenue, conversion_rate, signups"}), 400
        if comparator not in {"gt", "lt", "gte", "lte", "eq", "neq"}:
            return jsonify({"error": "comparator must be one of: gt, lt, gte, lte, eq, neq"}), 400
        try:
            threshold = float(threshold)
        except Exception:
            return jsonify({"error": "threshold must be a number"}), 400
        try:
            window_minutes = int(window_minutes)
            cool_down_minutes = int(cool_down_minutes)
        except Exception:
            return jsonify({"error": "window_minutes and cool_down_minutes must be integers"}), 400
        if window_minutes <= 0 or cool_down_minutes < 0:
            return jsonify({"error": "window_minutes must be > 0 and cool_down_minutes >= 0"}), 400
        if not isinstance(channels, list) or any(not isinstance(c, dict) for c in channels):
            return jsonify({"error": "channels must be a list of objects"}), 400

        s = SessionLocal()
        try:
            rule = AlertRule(
                name=name,
                metric=metric,
                comparator=comparator,
                threshold=threshold,
                window_minutes=window_minutes,
                cool_down_minutes=cool_down_minutes,
                is_active=is_active,
                channels_json=AlertRule.serialize_channels(channels),
            )
            s.add(rule)
            s.commit()
            s.refresh(rule)
            return jsonify(rule.to_dict()), 201
        except Exception as e:
            s.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            s.close()

    @app.route("/alert-rules", methods=["GET"])
    def list_alert_rules():
        s = SessionLocal()
        try:
            rules = s.query(AlertRule).order_by(AlertRule.created_at.desc()).all()
            return jsonify([r.to_dict() for r in rules])
        finally:
            s.close()

    @app.route("/alert-rules/<int:rule_id>", methods=["PATCH"])
    def update_alert_rule(rule_id: int):
        data = request.get_json(force=True, silent=True) or {}
        s = SessionLocal()
        try:
            rule = s.query(AlertRule).get(rule_id)
            if not rule:
                return jsonify({"error": "Rule not found"}), 404
            if "name" in data:
                rule.name = (data["name"] or "").strip()
            if "is_active" in data:
                rule.is_active = bool(data["is_active"])
            if "channels" in data:
                channels = data["channels"]
                if not isinstance(channels, list) or any(not isinstance(c, dict) for c in channels):
                    return jsonify({"error": "channels must be a list of objects"}), 400
                rule.channels_json = AlertRule.serialize_channels(channels)
            if "threshold" in data:
                try:
                    rule.threshold = float(data["threshold"]) 
                except Exception:
                    return jsonify({"error": "threshold must be a number"}), 400
            if "comparator" in data:
                comp = (data["comparator"] or "").strip().lower()
                if comp not in {"gt", "lt", "gte", "lte", "eq", "neq"}:
                    return jsonify({"error": "invalid comparator"}), 400
                rule.comparator = comp
            if "window_minutes" in data:
                try:
                    wm = int(data["window_minutes"]) 
                except Exception:
                    return jsonify({"error": "window_minutes must be integer"}), 400
                if wm <= 0:
                    return jsonify({"error": "window_minutes must be > 0"}), 400
                rule.window_minutes = wm
            if "cool_down_minutes" in data:
                try:
                    cd = int(data["cool_down_minutes"]) 
                except Exception:
                    return jsonify({"error": "cool_down_minutes must be integer"}), 400
                if cd < 0:
                    return jsonify({"error": "cool_down_minutes must be >= 0"}), 400
                rule.cool_down_minutes = cd

            s.commit()
            s.refresh(rule)
            return jsonify(rule.to_dict())
        except Exception as e:
            s.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            s.close()

    @app.route("/alerts/test", methods=["POST"])
    def trigger_evaluation():
        s = SessionLocal()
        try:
            results = evaluate_rules(s)
            return jsonify({"evaluated": len(results), "triggers": [r for r in results if r.get("triggered")]})
        finally:
            s.close()

    @app.route("/alerts", methods=["GET"])
    def list_alerts():
        s = SessionLocal()
        try:
            limit = int(request.args.get("limit", 100))
            alerts = (
                s.query(Alert)
                .order_by(Alert.triggered_at.desc())
                .limit(limit)
                .all()
            )
            return jsonify([a.to_dict() for a in alerts])
        finally:
            s.close()

    return app


if __name__ == "__main__":
    app = create_app()
    if os.environ.get("DISABLE_SCHEDULER", "0") != "1":
        start_scheduler(app)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



@app.route('/metrics/revenue', methods=['GET', 'POST'])
def _auto_stub_metrics_revenue():
    return 'Auto-generated stub for /metrics/revenue', 200


@app.route('/thresholds/signups', methods=['GET', 'PUT'])
def _auto_stub_thresholds_signups():
    return 'Auto-generated stub for /thresholds/signups', 200
