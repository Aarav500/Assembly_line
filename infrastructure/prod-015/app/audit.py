import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from flask import current_app, request, g
from sqlalchemy import event as sqla_event
from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect as sqla_inspect
from .extensions import db
from .models import AuditChainState, AuditEvent, AuditDataChange


def init_chain_state():
    # Ensure singleton row exists
    if not db.session.query(AuditChainState).filter_by(id=1).first():
        cs = AuditChainState(id=1, last_event_id=None, last_hash=None)
        db.session.add(cs)
        db.session.commit()


def redact_value(key: str, value: Any) -> Any:
    if key is None:
        return value
    if key.lower() in current_app.config.get("AUDIT_REDACT_KEYS", set()):
        return "***REDACTED***"
    return value


def redact_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict):
            out[k] = redact_dict(v)
        elif isinstance(v, list):
            out[k] = [redact_dict(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = redact_value(k, v)
    return out


def canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_event_hash(payload: Dict[str, Any]) -> str:
    canon = canonical_json(payload).encode("utf-8")
    digest = hashlib.sha256(canon).digest()
    return base64.b64encode(digest).decode("ascii")


def compute_hmac(sig_payload: str) -> str:
    secret = current_app.config["AUDIT_HMAC_SECRET"].encode("utf-8")
    hm = hmac.new(secret, sig_payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(hm).decode("ascii")


def get_current_user_id() -> Optional[str]:
    # Example: extract from header or set by auth middleware
    # Try app-provided context first
    uid = getattr(g, "current_user_id", None)
    if uid:
        return str(uid)
    # Fallback to header
    hdr = request.headers.get("X-User-Id")
    return hdr if hdr else None


def capture_request_context() -> Dict[str, Any]:
    max_body = current_app.config.get("AUDIT_MAX_BODY", 4096)

    # Query params
    qparams = {k: request.args.getlist(k) if len(request.args.getlist(k)) > 1 else request.args.get(k) for k in request.args}
    qparams = redact_dict(qparams)

    # Headers subset
    capture_headers = current_app.config.get("AUDIT_CAPTURE_HEADERS", set())
    headers = {k: ("***REDACTED***" if k.lower() in current_app.config.get("AUDIT_REDACT_KEYS", set()) or k.lower() in {"authorization", "cookie"} else v) for k, v in request.headers.items() if k in capture_headers}

    # Body (truncated)
    body_text = None
    try:
        raw = request.get_data(cache=True)
        if raw:
            body_text = raw[:max_body].decode("utf-8", errors="replace")
    except Exception:
        body_text = None

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    return {
        "method": request.method,
        "path": request.path,
        "status_code": None,  # set post-response
        "user_agent": request.headers.get("User-Agent"),
        "headers": headers,
        "query_params": qparams,
        "request_body": body_text,
        "ip": ip,
    }


def append_audit_event(event_type: str, action: Optional[str] = None, ctx: Optional[Dict[str, Any]] = None, details: Optional[Dict[str, Any]] = None) -> AuditEvent:
    # Use a single DB transaction and lock chain state row to ensure consistent hash chain
    session: Session = db.session
    ctx = ctx or {}

    chain_state = session.query(AuditChainState).filter_by(id=1).with_for_update().one()

    payload_for_hash = {
        "created_at": datetime.utcnow().isoformat(timespec="microseconds"),
        "user_id": get_current_user_id(),
        "request_id": getattr(g, "request_id", None),
        "ip": ctx.get("ip"),
        "event_type": event_type,
        "action": action,
        "method": ctx.get("method"),
        "path": ctx.get("path"),
        "status_code": ctx.get("status_code"),
        "user_agent": ctx.get("user_agent"),
        "headers": ctx.get("headers"),
        "query_params": ctx.get("query_params"),
        "request_body": ctx.get("request_body"),
        "details": details or {},
        "previous_hash": chain_state.last_hash,
    }

    event_hash = compute_event_hash(payload_for_hash)
    signature = compute_hmac(event_hash)

    ev = AuditEvent(
        created_at=datetime.fromisoformat(payload_for_hash["created_at"]),
        user_id=payload_for_hash["user_id"],
        request_id=payload_for_hash["request_id"],
        ip=payload_for_hash["ip"],
        event_type=payload_for_hash["event_type"],
        action=payload_for_hash["action"],
        method=payload_for_hash["method"],
        path=payload_for_hash["path"],
        status_code=payload_for_hash["status_code"],
        user_agent=payload_for_hash["user_agent"],
        headers=payload_for_hash["headers"],
        query_params=payload_for_hash["query_params"],
        request_body=payload_for_hash["request_body"],
        details=payload_for_hash["details"],
        previous_hash=payload_for_hash["previous_hash"],
        event_hash=event_hash,
        hmac_signature=signature,
    )

    session.add(ev)
    session.flush()  # ensure ev.id available

    # update chain state
    chain_state.last_event_id = ev.id
    chain_state.last_hash = event_hash
    session.add(chain_state)

    return ev


def after_request_log_api_call(response):
    try:
        ctx = capture_request_context()
        ctx["status_code"] = response.status_code
        with db.session.begin():
            append_audit_event(event_type="api_call", action=None, ctx=ctx, details=None)
    except Exception:
        # Do not break request if audit logging fails
        current_app.logger.exception("Audit logging failed in after_request")
    return response


# ORM change tracking helpers
EXCLUDED_TABLES = {"audit_events", "audit_data_changes", "audit_chain_state"}


def model_table_name(instance) -> str:
    return instance.__table__.name


def get_pk_value(instance) -> str:
    mapper = sqla_inspect(instance).mapper
    pk_keys = [col.key for col in mapper.primary_key]
    data = {}
    for k in pk_keys:
        data[k] = getattr(instance, k)
    if len(pk_keys) == 1:
        return str(data[pk_keys[0]])
    return json.dumps(data, sort_keys=True)


def to_column_dict(instance) -> Dict[str, Any]:
    mapper = sqla_inspect(instance).mapper
    result = {}
    for col in mapper.columns:
        val = getattr(instance, col.key)
        try:
            json.dumps(val, default=str)
            result[col.key] = val
        except TypeError:
            result[col.key] = str(val)
    return result


def before_after_for_update(instance):
    insp = sqla_inspect(instance)
    before = {}
    after = {}
    for attr in insp.attrs:
        if not hasattr(attr, "history"):
            continue
        hist = attr.history
        if hist.has_changes():
            key = attr.key
            old = hist.deleted[0] if hist.deleted else None
            new = hist.added[0] if hist.added else getattr(instance, key)
            before[key] = old
            after[key] = new
    return before, after


def register_audit_listeners():
    @sqla_event.listens_for(Session, "after_flush")
    def receive_after_flush(session, flush_context):
        try:
            changes_to_log = []
            # Inserts
            for obj in session.new:
                if hasattr(obj, "__table__"):
                    tname = model_table_name(obj)
                    if tname in EXCLUDED_TABLES:
                        continue
                    changes_to_log.append({
                        "operation": "insert",
                        "table": tname,
                        "pk": get_pk_value(obj),
                        "before": None,
                        "after": to_column_dict(obj),
                    })
            # Updates
            for obj in session.dirty:
                if hasattr(obj, "__table__"):
                    tname = model_table_name(obj)
                    if tname in EXCLUDED_TABLES:
                        continue
                    if session.is_modified(obj, include_collections=False):
                        before, after = before_after_for_update(obj)
                        if before or after:
                            changes_to_log.append({
                                "operation": "update",
                                "table": tname,
                                "pk": get_pk_value(obj),
                                "before": before,
                                "after": after,
                            })
            # Deletes
            for obj in session.deleted:
                if hasattr(obj, "__table__"):
                    tname = model_table_name(obj)
                    if tname in EXCLUDED_TABLES:
                        continue
                    changes_to_log.append({
                        "operation": "delete",
                        "table": tname,
                        "pk": get_pk_value(obj),
                        "before": to_column_dict(obj),
                        "after": None,
                    })

            if not changes_to_log:
                return

            # We create a single AuditEvent for this flush capturing all changes
            ctx = {}
            try:
                # If within a request
                ctx = capture_request_context()
            except Exception:
                ctx = {
                    "method": None,
                    "path": None,
                    "status_code": None,
                    "user_agent": None,
                    "headers": None,
                    "query_params": None,
                    "request_body": None,
                    "ip": None,
                }

            # Create event and associated change rows within same TX
            ev = append_audit_event(event_type="data_change", action="db_write", ctx=ctx, details={"change_count": len(changes_to_log)})
            for ch in changes_to_log:
                dc = AuditDataChange(
                    event_id=ev.id,
                    table_name=ch["table"],
                    row_pk=str(ch["pk"]),
                    operation=ch["operation"],
                    before_data=redact_dict(ch["before"]) if ch["before"] else None,
                    after_data=redact_dict(ch["after"]) if ch["after"] else None,
                )
                session.add(dc)
        except Exception:
            current_app.logger.exception("Failed to append data change audit logs")


# Public helpers for business-logic user actions

def audit_user_action(action: str, details: Optional[Dict[str, Any]] = None):
    ctx = capture_request_context()
    with db.session.begin():
        append_audit_event(event_type="user_action", action=action, ctx=ctx, details=details or {})


# Chain verification for compliance

def verify_chain(limit: Optional[int] = None, since: Optional[datetime] = None) -> Dict[str, Any]:
    q = db.session.query(AuditEvent).order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    if since:
        q = q.filter(AuditEvent.created_at >= since)
    if limit:
        q = q.limit(limit)
    events = q.all()

    prev_hash = None
    ok = True
    failures = []
    for ev in events:
        payload = {
            "created_at": ev.created_at.isoformat(timespec="microseconds"),
            "user_id": ev.user_id,
            "request_id": ev.request_id,
            "ip": ev.ip,
            "event_type": ev.event_type,
            "action": ev.action,
            "method": ev.method,
            "path": ev.path,
            "status_code": ev.status_code,
            "user_agent": ev.user_agent,
            "headers": ev.headers,
            "query_params": ev.query_params,
            "request_body": ev.request_body,
            "details": ev.details or {},
            "previous_hash": prev_hash,
        }
        computed_hash = compute_event_hash(payload)
        computed_sig = compute_hmac(computed_hash)
        if ev.previous_hash != prev_hash or ev.event_hash != computed_hash or ev.hmac_signature != computed_sig:
            ok = False
            failures.append({
                "event_id": ev.id,
                "expected_prev": prev_hash,
                "stored_prev": ev.previous_hash,
                "recomputed_hash": computed_hash,
                "stored_hash": ev.event_hash,
                "recomputed_hmac": computed_sig,
                "stored_hmac": ev.hmac_signature,
            })
        prev_hash = ev.event_hash

    return {"ok": ok, "checked": len(events), "failures": failures}

