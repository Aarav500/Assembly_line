import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from datetime import datetime, date
from flask import Flask, request, jsonify
from sqlalchemy.orm import scoped_session, sessionmaker

from db import engine
from models import Base, init_db, CostRecord
from services.breakdown import get_breakdown
from services.anomaly import detect_anomalies
from utils.time import parse_date


def create_app():
    app = Flask(__name__)

    # DB init
    init_db()
    Session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))

    @app.teardown_appcontext
    def remove_session(exception=None):
        Session.remove()

    @app.route("/health", methods=["GET"])    
    def health():
        return jsonify({"status": "ok"})

    @app.route("/ingest", methods=["POST"])    
    def ingest():
        payload = request.get_json(silent=True) or {}
        records = payload.get("records", [])
        if not isinstance(records, list):
            return jsonify({"error": "records must be a list"}), 400
        sess = Session()
        inserted = 0
        try:
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                d = rec.get("date")
                amt = rec.get("amount")
                tags = rec.get("tags", {})
                if d is None or amt is None:
                    continue
                try:
                    d_parsed = parse_date(d)
                except Exception:
                    return jsonify({"error": f"Invalid date format: {d}"}), 400
                try:
                    amt_f = float(amt)
                except Exception:
                    return jsonify({"error": f"Invalid amount: {amt}"}), 400
                cr = CostRecord(date=d_parsed, amount=amt_f)
                if isinstance(tags, dict):
                    cr.tags = tags
                else:
                    return jsonify({"error": "tags must be an object (dictionary)"}), 400
                sess.add(cr)
                inserted += 1
            sess.commit()
        except Exception as e:
            sess.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            sess.close()
        return jsonify({"ingested": inserted})

    @app.route("/breakdown", methods=["GET"])    
    def breakdown():
        group_by = request.args.get("group_by")
        period = (request.args.get("period") or "daily").lower()
        start = request.args.get("start")
        end = request.args.get("end")
        if start:
            try:
                start = parse_date(start)
            except Exception:
                return jsonify({"error": "Invalid start date"}), 400
        if end:
            try:
                end = parse_date(end)
            except Exception:
                return jsonify({"error": "Invalid end date"}), 400
        sess = Session()
        try:
            result = get_breakdown(sess, group_by=group_by, period=period, start=start, end=end)
            return jsonify(result)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            sess.close()

    @app.route("/anomalies", methods=["GET"])    
    def anomalies():
        group_by = request.args.get("group_by")
        if not group_by:
            return jsonify({"error": "group_by is required"}), 400
        method = (request.args.get("method") or "zscore").lower()
        period = (request.args.get("period") or "daily").lower()
        threshold = request.args.get("threshold")
        window = request.args.get("window")
        min_points = request.args.get("min_points")
        direction = request.args.get("direction")  # up, down, both
        start = request.args.get("start")
        end = request.args.get("end")
        try:
            threshold = float(threshold) if threshold is not None else 3.0
        except Exception:
            return jsonify({"error": "threshold must be numeric"}), 400
        try:
            window = int(window) if window is not None else 7
        except Exception:
            return jsonify({"error": "window must be integer"}), 400
        try:
            min_points = int(min_points) if min_points is not None else max(2 * window, 14)
        except Exception:
            return jsonify({"error": "min_points must be integer"}), 400
        if direction not in (None, "up", "down", "both"):
            return jsonify({"error": "direction must be one of up, down, both"}), 400
        if start:
            try:
                start = parse_date(start)
            except Exception:
                return jsonify({"error": "Invalid start date"}), 400
        if end:
            try:
                end = parse_date(end)
            except Exception:
                return jsonify({"error": "Invalid end date"}), 400
        sess = Session()
        try:
            results = detect_anomalies(
                sess,
                group_by=group_by,
                period=period,
                start=start,
                end=end,
                method=method,
                threshold=threshold,
                window=window,
                min_points=min_points,
                direction=direction or "both",
            )
            return jsonify(results)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            sess.close()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



@app.route('/costs', methods=['GET', 'POST'])
def _auto_stub_costs():
    return 'Auto-generated stub for /costs', 200


@app.route('/anomalies?tag=prod&threshold=2.0', methods=['GET'])
def _auto_stub_anomalies_tag_prod_threshold_2_0():
    return 'Auto-generated stub for /anomalies?tag=prod&threshold=2.0', 200
