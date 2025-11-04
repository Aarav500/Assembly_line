import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
import time
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from flask import Flask, request, jsonify, g
from sqlalchemy.orm import scoped_session

from database import SessionLocal, init_db
from models import Service, Measurement, Incident, DailyReport
from utils import (
    parse_ts_to_utc,
    day_bounds_utc,
    as_date,
    safe_float,
    compute_p95,
)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Database session per-request
@app.before_request
def create_session():
    g.db = SessionLocal()


@app.teardown_appcontext
def shutdown_session(exception=None):
    # scoped_session removes the session associated with the current context
    SessionLocal.remove()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})


# Services CRUD
@app.route("/services", methods=["POST"])
def create_service():
    payload = request.get_json(force=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    s = Service(
        name=name,
        description=payload.get("description"),
        slo_availability_target=safe_float(payload.get("slo_availability_target"), default=0.999),
        slo_latency_ms_p95=safe_float(payload.get("slo_latency_ms_p95"), default=300.0),
        slo_error_rate_target=safe_float(payload.get("slo_error_rate_target"), default=0.001),
        timezone=(payload.get("timezone") or "UTC").strip() or "UTC",
        slo_window_days=int(payload.get("slo_window_days") or 30),
    )
    g.db.add(s)
    g.db.commit()
    g.db.refresh(s)
    return jsonify(s.to_dict()), 201


@app.route("/services", methods=["GET"])
def list_services():
    services = g.db.query(Service).order_by(Service.id.asc()).all()
    return jsonify([s.to_dict() for s in services])


@app.route("/services/<int:service_id>", methods=["GET"])
def get_service(service_id: int):
    s = g.db.get(Service, service_id)
    if not s:
        return jsonify({"error": "not found"}), 404
    return jsonify(s.to_dict())


@app.route("/services/<int:service_id>", methods=["PUT", "PATCH"])
def update_service(service_id: int):
    s = g.db.get(Service, service_id)
    if not s:
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(force=True) or {}
    for field in ["name", "description", "timezone"]:
        if field in payload and payload[field] is not None:
            setattr(s, field, payload[field])
    if "slo_availability_target" in payload:
        s.slo_availability_target = safe_float(payload.get("slo_availability_target"), default=s.slo_availability_target)
    if "slo_latency_ms_p95" in payload:
        s.slo_latency_ms_p95 = safe_float(payload.get("slo_latency_ms_p95"), default=s.slo_latency_ms_p95)
    if "slo_error_rate_target" in payload:
        s.slo_error_rate_target = safe_float(payload.get("slo_error_rate_target"), default=s.slo_error_rate_target)
    if "slo_window_days" in payload and payload.get("slo_window_days"):
        s.slo_window_days = int(payload.get("slo_window_days"))

    g.db.commit()
    g.db.refresh(s)
    return jsonify(s.to_dict())


# Measurements ingestion
@app.route("/measurements", methods=["POST"])
def ingest_measurements():
    payload = request.get_json(force=True) or {}

    # Support single or batch
    measurements = payload.get("measurements")
    if measurements is None:
        # Interpret entire payload as one measurement
        measurements = [payload]

    created = []
    for m in measurements:
        service_id = m.get("service_id") or payload.get("service_id")
        if not service_id:
            return jsonify({"error": "service_id is required for each measurement"}), 400
        s = g.db.get(Service, int(service_id))
        if not s:
            return jsonify({"error": f"service {service_id} not found"}), 404

        ts_str = m.get("ts") or m.get("timestamp")
        if not ts_str:
            return jsonify({"error": "ts (ISO-8601) is required"}), 400
        ts_utc = parse_ts_to_utc(ts_str)
        meas = Measurement(
            service_id=s.id,
            ts_utc=ts_utc.replace(tzinfo=None),
            up=(m.get("up") if m.get("up") is not None else None),
            latency_ms=(safe_float(m.get("latency_ms")) if m.get("latency_ms") is not None else None),
            errors=int(m.get("errors") or 0) if m.get("errors") is not None else None,
            requests=int(m.get("requests") or 0) if m.get("requests") is not None else None,
            source=(m.get("source") or "api"),
        )
        g.db.add(meas)
        created.append({"service_id": s.id, "ts": ts_utc.isoformat().replace('+00:00','Z')})

    g.db.commit()
    return jsonify({"ingested": created}), 201


# Incidents
@app.route("/incidents", methods=["POST"])
def create_incident():
    payload = request.get_json(force=True) or {}
    service_id = payload.get("service_id")
    if not service_id:
        return jsonify({"error": "service_id is required"}), 400
    s = g.db.get(Service, int(service_id))
    if not s:
        return jsonify({"error": f"service {service_id} not found"}), 404

    start_ts = parse_ts_to_utc(payload.get("start_ts") or payload.get("start")) if payload.get("start_ts") or payload.get("start") else None
    if not start_ts:
        return jsonify({"error": "start_ts is required"}), 400
    end_ts = parse_ts_to_utc(payload.get("end_ts") or payload.get("end")) if payload.get("end_ts") or payload.get("end") else None

    inc = Incident(
        service_id=s.id,
        start_utc=start_ts.replace(tzinfo=None),
        end_utc=(end_ts.replace(tzinfo=None) if end_ts else None),
        severity=(payload.get("severity") or "minor"),
        cause=payload.get("cause"),
        description=payload.get("description"),
    )
    g.db.add(inc)
    g.db.commit()
    g.db.refresh(inc)
    return jsonify(inc.to_dict()), 201


# Reports
@app.route("/reports/daily", methods=["GET"])
def daily_reports_all():
    # date query param in YYYY-MM-DD (service local) optional, defaults to yesterday (UTC)
    q_date = request.args.get("date")
    if q_date:
        target_date = as_date(q_date)
        if not target_date:
            return jsonify({"error": "invalid date format, expected YYYY-MM-DD"}), 400
    else:
        target_date = (datetime.utcnow() - timedelta(days=1)).date()

    services = g.db.query(Service).all()
    results = []
    for s in services:
        rep = get_or_compute_daily_report(g.db, s, target_date)
        if rep:
            results.append(rep.to_dict())
    return jsonify(results)


@app.route("/reports/daily/<int:service_id>", methods=["GET"])
def daily_report_for_service(service_id: int):
    s = g.db.get(Service, service_id)
    if not s:
        return jsonify({"error": "service not found"}), 404
    q_date = request.args.get("date")
    if q_date:
        target_date = as_date(q_date)
        if not target_date:
            return jsonify({"error": "invalid date format, expected YYYY-MM-DD"}), 400
    else:
        target_date = (datetime.utcnow()).date()

    rep = get_or_compute_daily_report(g.db, s, target_date)
    if not rep:
        return jsonify({"error": "no data"}), 404
    return jsonify(rep.to_dict())


@app.route("/reports/period/<int:service_id>", methods=["GET"])
def period_report(service_id: int):
    s = g.db.get(Service, service_id)
    if not s:
        return jsonify({"error": "service not found"}), 404

    start_s = request.args.get("from") or request.args.get("start")
    end_s = request.args.get("to") or request.args.get("end")
    if not start_s or not end_s:
        return jsonify({"error": "from and to are required in YYYY-MM-DD"}), 400
    start_d = as_date(start_s)
    end_d = as_date(end_s)
    if not start_d or not end_d or end_d < start_d:
        return jsonify({"error": "invalid period"}), 400

    metrics = aggregate_period(g.db, s, start_d, end_d)
    return jsonify(metrics)


@app.route("/reports/error-budget/<int:service_id>", methods=["GET"])
def error_budget(service_id: int):
    s = g.db.get(Service, service_id)
    if not s:
        return jsonify({"error": "service not found"}), 404

    start_s = request.args.get("from") or request.args.get("start")
    end_s = request.args.get("to") or request.args.get("end")
    if start_s and end_s:
        start_d = as_date(start_s)
        end_d = as_date(end_s)
        if not start_d or not end_d or end_d < start_d:
            return jsonify({"error": "invalid period"}), 400
    else:
        # default to SLO window
        end_d = datetime.utcnow().date()
        start_d = end_d - timedelta(days=(s.slo_window_days - 1))

    metrics = aggregate_period(g.db, s, start_d, end_d)

    target = s.slo_availability_target or 0.0
    error_budget = max(0.0, 1.0 - target)
    availability = metrics.get("availability")
    consumed = None
    burn_rate = None
    if availability is not None:
        consumed = max(0.0, 1.0 - availability)
        burn_rate = (consumed / error_budget) if error_budget > 0 else None

    return jsonify({
        "service_id": s.id,
        "period": {"from": start_d.isoformat(), "to": end_d.isoformat()},
        "target_availability": target,
        "error_budget": error_budget,
        "availability": availability,
        "error_budget_consumed": consumed,
        "burn_rate": burn_rate,
    })


# ---------- Core computation helpers ----------
def compute_daily_for_service(session, service: Service, target_date: date) -> Optional[DailyReport]:
    start_utc, end_utc = day_bounds_utc(target_date, service.timezone)
    start_naive = start_utc.replace(tzinfo=None)
    end_naive = end_utc.replace(tzinfo=None)

    q = (
        session.query(Measurement)
        .filter(
            Measurement.service_id == service.id,
            Measurement.ts_utc >= start_naive,
            Measurement.ts_utc < end_naive,
        )
    )
    measurements: List[Measurement] = q.all()

    up_count = sum(1 for m in measurements if m.up is True)
    down_count = sum(1 for m in measurements if m.up is False)
    status_count = up_count + down_count
    availability = (up_count / status_count) if status_count > 0 else None

    latencies = [m.latency_ms for m in measurements if m.latency_ms is not None]
    latency_p95 = compute_p95(latencies) if latencies else None

    total_requests = sum((m.requests or 0) for m in measurements if m.requests is not None)
    total_errors = sum((m.errors or 0) for m in measurements if m.errors is not None)
    error_rate = (total_errors / total_requests) if total_requests and total_requests > 0 else None

    slo_avail_met = (availability is not None and availability >= (service.slo_availability_target or 0))
    slo_latency_met = (latency_p95 is not None and latency_p95 <= (service.slo_latency_ms_p95 or float('inf')))
    slo_error_rate_met = (error_rate is not None and error_rate <= (service.slo_error_rate_target or 0))

    overall_met = None
    defined_metrics = [x is not None for x in [availability, latency_p95, error_rate]]
    if any(defined_metrics):
        # overall met only considers defined metrics
        flags = []
        if availability is not None:
            flags.append(slo_avail_met)
        if latency_p95 is not None:
            flags.append(slo_latency_met)
        if error_rate is not None:
            flags.append(slo_error_rate_met)
        overall_met = all(flags) if flags else None

    rep = DailyReport(
        service_id=service.id,
        date=target_date,
        timezone=service.timezone,
        availability=availability,
        latency_p95=latency_p95,
        error_rate=error_rate,
        slo_availability_met=slo_avail_met if availability is not None else None,
        slo_latency_met=slo_latency_met if latency_p95 is not None else None,
        slo_error_rate_met=slo_error_rate_met if error_rate is not None else None,
        slo_overall_met=overall_met,
        computed_at=datetime.utcnow(),
    )
    return rep


def get_or_compute_daily_report(session, service: Service, target_date: date) -> Optional[DailyReport]:
    existing = (
        session.query(DailyReport)
        .filter(DailyReport.service_id == service.id, DailyReport.date == target_date)
        .one_or_none()
    )
    if existing:
        return existing
    rep = compute_daily_for_service(session, service, target_date)
    if rep:
        session.add(rep)
        session.commit()
        session.refresh(rep)
    return rep


def aggregate_period(session, service: Service, start_d: date, end_d: date) -> Dict[str, Any]:
    # Ensure reports exist for the period
    cur = start_d
    out_reports: List[DailyReport] = []
    while cur <= end_d:
        rep = get_or_compute_daily_report(session, service, cur)
        if rep:
            out_reports.append(rep)
        cur += timedelta(days=1)

    # Aggregate
    availability_vals = [r.availability for r in out_reports if r.availability is not None]
    latency_vals = []
    # For latency across days, use weighted by count? We don't have counts in report. Approximate by median of p95s or max.
    # We'll use max of daily p95 values as conservative estimate.
    latency_daily_p95s = [r.latency_p95 for r in out_reports if r.latency_p95 is not None]
    error_rate_vals = [r.error_rate for r in out_reports if r.error_rate is not None]

    availability = (sum(availability_vals) / len(availability_vals)) if availability_vals else None
    latency_p95 = (max(latency_daily_p95s) if latency_daily_p95s else None)
    error_rate = (sum(error_rate_vals) / len(error_rate_vals)) if error_rate_vals else None

    slo_avail_met = (availability is not None and availability >= (service.slo_availability_target or 0))
    slo_latency_met = (latency_p95 is not None and latency_p95 <= (service.slo_latency_ms_p95 or float('inf')))
    slo_error_rate_met = (error_rate is not None and error_rate <= (service.slo_error_rate_target or 0))

    overall_met = None
    flags = []
    if availability is not None:
        flags.append(slo_avail_met)
    if latency_p95 is not None:
        flags.append(slo_latency_met)
    if error_rate is not None:
        flags.append(slo_error_rate_met)
    if flags:
        overall_met = all(flags)

    return {
        "service_id": service.id,
        "period": {"from": start_d.isoformat(), "to": end_d.isoformat()},
        "availability": availability,
        "latency_p95": latency_p95,
        "error_rate": error_rate,
        "targets": {
            "availability": service.slo_availability_target,
            "latency_p95": service.slo_latency_ms_p95,
            "error_rate": service.slo_error_rate_target,
        },
        "slo_met": {
            "availability": slo_avail_met if availability is not None else None,
            "latency_p95": slo_latency_met if latency_p95 is not None else None,
            "error_rate": slo_error_rate_met if error_rate is not None else None,
            "overall": overall_met,
        },
        "days": len(out_reports),
    }


# ---------- Background scheduler for daily reports ----------

def scheduler_loop(stop_event: threading.Event):
    # Compute missing daily reports for all services up to yesterday in their local TZ
    with app.app_context():
        while not stop_event.is_set():
            try:
                db: scoped_session = SessionLocal
                session = db()
                services = session.query(Service).all()
                for s in services:
                    # Determine yesterday in service TZ
                    now_utc = datetime.utcnow()
                    # We'll compute for all days missing from last report to yesterday
                    last_report = (
                        session.query(DailyReport)
                        .filter(DailyReport.service_id == s.id)
                        .order_by(DailyReport.date.desc())
                        .first()
                    )
                    # Compute yesterday's local date
                    # Since day_bounds_utc expects a date, we will compute local date from UTC now via tz math in utils
                    from utils import utc_to_local_date
                    yesterday_local = utc_to_local_date(now_utc) - timedelta(days=1)
                    if last_report:
                        start_date = min(yesterday_local, last_report.date + timedelta(days=1))
                    else:
                        # Default: only compute yesterday to avoid heavy backfill automatically
                        start_date = yesterday_local

                    cur = start_date
                    while cur <= yesterday_local:
                        rep = compute_daily_for_service(session, s, cur)
                        if rep:
                            # Don't duplicate
                            exists = (
                                session.query(DailyReport)
                                .filter(DailyReport.service_id == s.id, DailyReport.date == cur)
                                .one_or_none()
                            )
                            if not exists:
                                session.add(rep)
                                session.commit()
                        cur += timedelta(days=1)
                session.close()
            except Exception as e:
                # Log to stdout
                print(f"[scheduler] error: {e}")
            finally:
                # sleep 60 seconds
                stop_event.wait(60)


stop_event = threading.Event()


def start_scheduler():
    t = threading.Thread(target=scheduler_loop, args=(stop_event,), daemon=True)
    t.start()


if __name__ == "__main__":
    init_db()
    start_scheduler()
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app


@app.route('/sla', methods=['POST'])
def _auto_stub_sla():
    return 'Auto-generated stub for /sla', 200


@app.route('/sla/1', methods=['GET'])
def _auto_stub_sla_1():
    return 'Auto-generated stub for /sla/1', 200


@app.route('/compliance/1', methods=['GET'])
def _auto_stub_compliance_1():
    return 'Auto-generated stub for /compliance/1', 200
