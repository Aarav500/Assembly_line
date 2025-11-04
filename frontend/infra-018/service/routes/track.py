import uuid
from datetime import datetime
from dateutil import parser as dateparser

from flask import Blueprint, request, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db import db_session
from ..models import User, Event, Session, Identity

bp = Blueprint("track", __name__)


def _parse_timestamp(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    try:
        return dateparser.isoparse(value)
    except Exception:
        return None


def _get_or_create_user_by_external_id(external_id: str):
    if not external_id:
        return None
    stmt = select(User).where(User.external_id == external_id)
    user = db_session.execute(stmt).scalar_one_or_none()
    if user:
        return user
    user = User(external_id=external_id)
    db_session.add(user)
    db_session.flush()
    return user


def _get_or_create_session(user_id, anonymous_id, context, started_at):
    session_id = context.get("session_id") if isinstance(context, dict) else None
    if session_id:
        try:
            sid = uuid.UUID(session_id)
        except Exception:
            sid = uuid.uuid4()
    else:
        sid = uuid.uuid4()
    session = Session(
        id=sid,
        user_id=user_id,
        anonymous_id=anonymous_id,
        started_at=started_at or datetime.utcnow(),
        user_agent=(context or {}).get("user_agent"),
        ip=(context or {}).get("ip"),
        referrer=(context or {}).get("referrer"),
        utm=(context or {}).get("utm"),
    )
    db_session.add(session)
    db_session.flush()
    return session


@bp.route("/track", methods=["POST"])
def track_event():
    payload = request.get_json(silent=True) or {}
    name = payload.get("event") or payload.get("name")
    if not name:
        return jsonify({"error": "Missing required field 'event'"}), 400

    external_user_id = payload.get("user_id")
    anonymous_id = payload.get("anonymous_id")
    if not external_user_id and not anonymous_id:
        return jsonify({"error": "One of 'user_id' or 'anonymous_id' is required"}), 400

    # optional idempotency
    event_uuid = payload.get("event_id") or payload.get("event_uuid")
    if event_uuid:
        try:
            event_uuid = uuid.UUID(str(event_uuid))
        except Exception:
            return jsonify({"error": "event_id must be a valid UUID"}), 400

    properties = payload.get("properties") or {}
    ts = _parse_timestamp(payload.get("timestamp")) or datetime.utcnow()
    context = payload.get("context") or {}

    try:
        user = _get_or_create_user_by_external_id(external_user_id) if external_user_id else None

        # Ensure identity mapping
        if user and anonymous_id:
            try:
                db_session.add(Identity(anonymous_id=anonymous_id, user_id=user.id))
                db_session.flush()
            except IntegrityError:
                db_session.rollback()

        # Session
        session_obj = None
        if payload.get("session_id"):
            # Try to reference an existing session; if not exist, create
            try:
                sid = uuid.UUID(str(payload.get("session_id")))
            except Exception:
                sid = None
            if sid:
                session_obj = db_session.get(Session, sid)
        if not session_obj:
            session_obj = _get_or_create_session(user.id if user else None, anonymous_id, {**context, "session_id": payload.get("session_id")}, ts)

        event = Event(
            event_uuid=event_uuid or uuid.uuid4(),
            name=name,
            user_id=user.id if user else None,
            anonymous_id=anonymous_id,
            session_id=session_obj.id if session_obj else None,
            properties=properties,
            event_time=ts,
        )
        db_session.add(event)
        db_session.commit()
        return jsonify({
            "status": "ok",
            "event_id": str(event.event_uuid),
            "session_id": str(session_obj.id) if session_obj else None,
            "user_id": user.external_id if user and user.external_id else None,
        })
    except IntegrityError as e:
        db_session.rollback()
        # If it's idempotent duplication, return ok
        if "events_event_uuid_key" in str(e.orig):
            return jsonify({"status": "ok", "duplicate": True, "event_id": str(event_uuid)}), 200
        return jsonify({"error": "Database error", "detail": str(e)}), 500
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": "Unexpected error", "detail": str(e)}), 500


@bp.route("/identify", methods=["POST"])
def identify():
    payload = request.get_json(silent=True) or {}
    external_user_id = payload.get("user_id")
    anonymous_id = payload.get("anonymous_id")
    if not external_user_id or not anonymous_id:
        return jsonify({"error": "'user_id' and 'anonymous_id' are required"}), 400

    try:
        user = _get_or_create_user_by_external_id(external_user_id)
        ident = Identity(anonymous_id=anonymous_id, user_id=user.id)
        db_session.add(ident)
        db_session.commit()
        return jsonify({"status": "ok", "user_id": external_user_id, "anonymous_id": anonymous_id})
    except IntegrityError:
        db_session.rollback()
        return jsonify({"status": "ok", "message": "Identity already linked"})
    except Exception as e:
        db_session.rollback()
        return jsonify({"error": "Unexpected error", "detail": str(e)}), 500

