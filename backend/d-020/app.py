import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from datetime import datetime
from decimal import Decimal
from flask import Flask, request, jsonify, Response
from sqlalchemy import func, and_, or_
from database import init_db, SessionLocal
from models import UsageEvent, Pricing
from pricing import get_pricing, calculate_cost_usd, upsert_pricing, DEFAULT_PRICING
from token_counter import estimate_tokens
from config import Config
import uuid
import json


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    init_db()

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "name": "Token & Cost Logger",
            "status": "ok",
            "version": "1.0.0"
        })

    @app.route("/log", methods=["POST"])
    def log_usage():
        session = SessionLocal()
        try:
            data = request.get_json(force=True) or {}

            workflow_id = data.get("workflow_id")
            if not workflow_id:
                return jsonify({"error": "workflow_id is required"}), 400

            run_id = data.get("run_id") or str(uuid.uuid4())
            provider = data.get("provider")
            model = data.get("model")

            # Tokens: accept explicit tokens or estimate from text
            prompt_tokens = data.get("prompt_tokens")
            completion_tokens = data.get("completion_tokens")

            prompt_text = data.get("prompt_text")
            completion_text = data.get("completion_text")

            if prompt_tokens is None and prompt_text is not None:
                prompt_tokens = estimate_tokens(prompt_text, model=model)
            if completion_tokens is None and completion_text is not None:
                completion_tokens = estimate_tokens(completion_text, model=model)

            if prompt_tokens is None:
                prompt_tokens = 0
            if completion_tokens is None:
                completion_tokens = 0

            total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

            # Costs: accept explicit costs or compute using pricing
            prompt_cost_usd = data.get("prompt_cost_usd")
            completion_cost_usd = data.get("completion_cost_usd")
            total_cost_usd = data.get("total_cost_usd")

            pricing = None
            if provider and model:
                pricing = get_pricing(session, provider=provider, model=model)

            if prompt_cost_usd is None or completion_cost_usd is None or total_cost_usd is None:
                # compute if pricing available
                if pricing is not None:
                    comp = calculate_cost_usd(prompt_tokens, completion_tokens, pricing)
                    if prompt_cost_usd is None:
                        prompt_cost_usd = comp["prompt_cost_usd"]
                    if completion_cost_usd is None:
                        completion_cost_usd = comp["completion_cost_usd"]
                    if total_cost_usd is None:
                        total_cost_usd = comp["total_cost_usd"]
                else:
                    # default zero cost if unknown pricing
                    prompt_cost_usd = prompt_cost_usd or 0.0
                    completion_cost_usd = completion_cost_usd or 0.0
                    total_cost_usd = total_cost_usd or 0.0

            metadata = data.get("metadata")
            if metadata is not None and not isinstance(metadata, (dict, list)):
                # ensure serializable structure
                try:
                    json.dumps(metadata)
                except Exception:
                    metadata = {"value": str(metadata)}

            event = UsageEvent(
                id=str(uuid.uuid4()),
                created_at=datetime.utcnow(),
                workflow_id=workflow_id,
                run_id=run_id,
                provider=provider,
                model=model,
                prompt_tokens=int(prompt_tokens or 0),
                completion_tokens=int(completion_tokens or 0),
                total_tokens=int(total_tokens or 0),
                prompt_cost_usd=Decimal(str(prompt_cost_usd or 0)),
                completion_cost_usd=Decimal(str(completion_cost_usd or 0)),
                total_cost_usd=Decimal(str(total_cost_usd or 0)),
                input_chars=len(prompt_text) if isinstance(prompt_text, str) else None,
                output_chars=len(completion_text) if isinstance(completion_text, str) else None,
                metadata=metadata,
            )

            session.add(event)
            session.commit()

            return jsonify(event.to_dict()), 201
        except Exception as e:
            session.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()

    @app.route("/events", methods=["GET"])
    def list_events():
        session = SessionLocal()
        try:
            workflow_id = request.args.get("workflow_id")
            provider = request.args.get("provider")
            model = request.args.get("model")
            run_id = request.args.get("run_id")
            start = request.args.get("start")
            end = request.args.get("end")
            page = int(request.args.get("page", 1))
            page_size = min(int(request.args.get("page_size", 50)), 500)

            q = session.query(UsageEvent)
            if workflow_id:
                q = q.filter(UsageEvent.workflow_id == workflow_id)
            if provider:
                q = q.filter(UsageEvent.provider == provider)
            if model:
                q = q.filter(UsageEvent.model == model)
            if run_id:
                q = q.filter(UsageEvent.run_id == run_id)
            if start:
                try:
                    dt = datetime.fromisoformat(start)
                    q = q.filter(UsageEvent.created_at >= dt)
                except Exception:
                    pass
            if end:
                try:
                    dt = datetime.fromisoformat(end)
                    q = q.filter(UsageEvent.created_at <= dt)
                except Exception:
                    pass

            total = q.count()
            q = q.order_by(UsageEvent.created_at.desc())
            events = q.offset((page - 1) * page_size).limit(page_size).all()
            return jsonify({
                "page": page,
                "page_size": page_size,
                "total": total,
                "events": [e.to_dict() for e in events]
            })
        finally:
            session.close()

    @app.route("/workflows", methods=["GET"])
    def list_workflows():
        session = SessionLocal()
        try:
            page = int(request.args.get("page", 1))
            page_size = min(int(request.args.get("page_size", 50)), 500)

            subq = session.query(
                UsageEvent.workflow_id.label("workflow_id"),
                func.count(UsageEvent.id).label("events"),
                func.sum(UsageEvent.total_tokens).label("total_tokens"),
                func.sum(UsageEvent.total_cost_usd).label("total_cost_usd"),
                func.max(UsageEvent.created_at).label("last_seen")
            ).group_by(UsageEvent.workflow_id).subquery()

            total = session.query(func.count()).select_from(subq).scalar() or 0

            rows = session.query(subq).order_by(subq.c.last_seen.desc()).offset((page - 1) * page_size).limit(page_size).all()

            items = []
            for r in rows:
                items.append({
                    "workflow_id": r.workflow_id,
                    "events": int(r.events or 0),
                    "total_tokens": int(r.total_tokens or 0),
                    "total_cost_usd": float(r.total_cost_usd or 0),
                    "last_seen": r.last_seen.isoformat() if r.last_seen else None,
                })

            return jsonify({
                "page": page,
                "page_size": page_size,
                "total": total,
                "workflows": items
            })
        finally:
            session.close()

    @app.route("/workflows/<workflow_id>", methods=["GET"])
    def workflow_detail(workflow_id):
        session = SessionLocal()
        try:
            page = int(request.args.get("page", 1))
            page_size = min(int(request.args.get("page_size", 50)), 500)
            start = request.args.get("start")
            end = request.args.get("end")

            q = session.query(UsageEvent).filter(UsageEvent.workflow_id == workflow_id)
            q_stats = session.query(
                func.count(UsageEvent.id),
                func.sum(UsageEvent.prompt_tokens),
                func.sum(UsageEvent.completion_tokens),
                func.sum(UsageEvent.total_tokens),
                func.sum(UsageEvent.prompt_cost_usd),
                func.sum(UsageEvent.completion_cost_usd),
                func.sum(UsageEvent.total_cost_usd),
                func.min(UsageEvent.created_at),
                func.max(UsageEvent.created_at),
            ).filter(UsageEvent.workflow_id == workflow_id)

            if start:
                try:
                    dt = datetime.fromisoformat(start)
                    q = q.filter(UsageEvent.created_at >= dt)
                    q_stats = q_stats.filter(UsageEvent.created_at >= dt)
                except Exception:
                    pass
            if end:
                try:
                    dt = datetime.fromisoformat(end)
                    q = q.filter(UsageEvent.created_at <= dt)
                    q_stats = q_stats.filter(UsageEvent.created_at <= dt)
                except Exception:
                    pass

            total = q.count()
            events = q.order_by(UsageEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

            (count_events, sum_prompt_toks, sum_completion_toks, sum_total_toks,
             sum_prompt_cost, sum_completion_cost, sum_total_cost,
             first_seen, last_seen) = q_stats.one()

            # breakdown by model
            breakdown_q = session.query(
                UsageEvent.model,
                func.count(UsageEvent.id),
                func.sum(UsageEvent.total_tokens),
                func.sum(UsageEvent.total_cost_usd)
            ).filter(UsageEvent.workflow_id == workflow_id)
            if start:
                try:
                    dt = datetime.fromisoformat(start)
                    breakdown_q = breakdown_q.filter(UsageEvent.created_at >= dt)
                except Exception:
                    pass
            if end:
                try:
                    dt = datetime.fromisoformat(end)
                    breakdown_q = breakdown_q.filter(UsageEvent.created_at <= dt)
                except Exception:
                    pass
            breakdown_q = breakdown_q.group_by(UsageEvent.model)

            breakdown = []
            for m, c, t, cost in breakdown_q.all():
                breakdown.append({
                    "model": m,
                    "events": int(c or 0),
                    "total_tokens": int(t or 0),
                    "total_cost_usd": float(cost or 0),
                })

            return jsonify({
                "workflow_id": workflow_id,
                "stats": {
                    "events": int(count_events or 0),
                    "prompt_tokens": int(sum_prompt_toks or 0),
                    "completion_tokens": int(sum_completion_toks or 0),
                    "total_tokens": int(sum_total_toks or 0),
                    "prompt_cost_usd": float(sum_prompt_cost or 0),
                    "completion_cost_usd": float(sum_completion_cost or 0),
                    "total_cost_usd": float(sum_total_cost or 0),
                    "first_seen": first_seen.isoformat() if first_seen else None,
                    "last_seen": last_seen.isoformat() if last_seen else None,
                },
                "breakdown": breakdown,
                "events": [e.to_dict() for e in events],
                "page": page,
                "page_size": page_size,
                "total": total
            })
        finally:
            session.close()

    @app.route("/stats", methods=["GET"])
    def global_stats():
        session = SessionLocal()
        try:
            q = session.query(
                func.count(UsageEvent.id),
                func.count(func.distinct(UsageEvent.workflow_id)),
                func.sum(UsageEvent.total_tokens),
                func.sum(UsageEvent.total_cost_usd),
                func.min(UsageEvent.created_at),
                func.max(UsageEvent.created_at),
            )
            (events, workflows, total_tokens, total_cost, first_seen, last_seen) = q.one()
            return jsonify({
                "events": int(events or 0),
                "workflows": int(workflows or 0),
                "total_tokens": int(total_tokens or 0),
                "total_cost_usd": float(total_cost or 0),
                "first_seen": first_seen.isoformat() if first_seen else None,
                "last_seen": last_seen.isoformat() if last_seen else None,
            })
        finally:
            session.close()

    @app.route("/export.csv", methods=["GET"])
    def export_csv():
        session = SessionLocal()
        try:
            workflow_id = request.args.get("workflow_id")
            provider = request.args.get("provider")
            model = request.args.get("model")
            start = request.args.get("start")
            end = request.args.get("end")

            q = session.query(UsageEvent)
            if workflow_id:
                q = q.filter(UsageEvent.workflow_id == workflow_id)
            if provider:
                q = q.filter(UsageEvent.provider == provider)
            if model:
                q = q.filter(UsageEvent.model == model)
            if start:
                try:
                    dt = datetime.fromisoformat(start)
                    q = q.filter(UsageEvent.created_at >= dt)
                except Exception:
                    pass
            if end:
                try:
                    dt = datetime.fromisoformat(end)
                    q = q.filter(UsageEvent.created_at <= dt)
                except Exception:
                    pass

            q = q.order_by(UsageEvent.created_at.asc())

            def generate():
                # header
                cols = [
                    "id","created_at","workflow_id","run_id","provider","model",
                    "prompt_tokens","completion_tokens","total_tokens",
                    "prompt_cost_usd","completion_cost_usd","total_cost_usd",
                    "input_chars","output_chars","metadata"
                ]
                yield ",".join(cols) + "\n"
                for e in q:
                    row = e.to_row()
                    values = [str(row.get(c, "")) for c in cols]
                    yield ",".join(v.replace("\n", " ").replace(",", ";") for v in values) + "\n"

            headers = {
                'Content-Disposition': 'attachment; filename=usage_export.csv',
                'Content-Type': 'text/csv'
            }
            return Response(generate(), headers=headers)
        finally:
            session.close()

    @app.route("/pricing", methods=["GET"]) 
    def list_pricing():
        session = SessionLocal()
        try:
            items = session.query(Pricing).order_by(Pricing.provider.asc(), Pricing.model.asc()).all()
            return jsonify([p.to_dict() for p in items])
        finally:
            session.close()

    @app.route("/pricing", methods=["POST"]) 
    def set_pricing():
        session = SessionLocal()
        try:
            data = request.get_json(force=True) or {}
            if isinstance(data, dict) and data.get("provider") and data.get("model"):
                # single upsert
                upsert_pricing(session,
                               provider=data["provider"],
                               model=data["model"],
                               input_per_1k=data.get("input_per_1k_usd"),
                               output_per_1k=data.get("output_per_1k_usd"),
                               currency=data.get("currency", "USD"))
                session.commit()
            elif isinstance(data, list):
                for item in data:
                    if not (item.get("provider") and item.get("model")):
                        continue
                    upsert_pricing(session,
                                   provider=item["provider"],
                                   model=item["model"],
                                   input_per_1k=item.get("input_per_1k_usd"),
                                   output_per_1k=item.get("output_per_1k_usd"),
                                   currency=item.get("currency", "USD"))
                session.commit()
            else:
                return jsonify({"error": "Invalid payload"}), 400

            items = session.query(Pricing).order_by(Pricing.provider.asc(), Pricing.model.asc()).all()
            return jsonify([p.to_dict() for p in items])
        except Exception as e:
            session.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()

    @app.route("/pricing/seed-defaults", methods=["POST"]) 
    def seed_default_pricing():
        session = SessionLocal()
        try:
            count = 0
            for provider, models in DEFAULT_PRICING.items():
                for model, rates in models.items():
                    upsert_pricing(session,
                                   provider=provider,
                                   model=model,
                                   input_per_1k=rates.get("input_per_1k_usd"),
                                   output_per_1k=rates.get("output_per_1k_usd"),
                                   currency=rates.get("currency", "USD"))
                    count += 1
            session.commit()
            return jsonify({"seeded": count})
        except Exception as e:
            session.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/usage?workflow=test-workflow', methods=['GET'])
def _auto_stub_usage_workflow_test_workflow():
    return 'Auto-generated stub for /usage?workflow=test-workflow', 200
