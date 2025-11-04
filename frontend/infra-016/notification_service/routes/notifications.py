from flask import Blueprint, current_app, request, jsonify
from notification_service.schemas import NotificationRequest, NotificationResponse, Channel, SendResult
from notification_service.services.notification_service import NotificationService
from pydantic import ValidationError


bp = Blueprint('notifications', __name__)


def get_service() -> NotificationService:
    settings = current_app.config['SETTINGS']
    # Cache the service instance in app extensions
    svc = current_app.extensions.get('notification_service') if hasattr(current_app, 'extensions') else None
    if not svc:
        svc = NotificationService(settings)
        if not hasattr(current_app, 'extensions'):
            current_app.extensions = {}
        current_app.extensions['notification_service'] = svc
    return svc


@bp.post('/notifications/send')
def send_notification():
    payload = request.get_json(silent=True) or {}
    try:
        req = NotificationRequest.model_validate(payload)
    except ValidationError as e:
        return jsonify({"error": "validation_error", "details": e.errors()}), 400

    service = get_service()

    results: dict[Channel, SendResult] = {}

    if Channel.email in req.channels:
        if not req.email:
            return jsonify({"error": "missing_email_payload"}), 400
        results[Channel.email] = service.send_email(req.email)

    if Channel.sms in req.channels:
        if not req.sms:
            return jsonify({"error": "missing_sms_payload"}), 400
        results[Channel.sms] = service.send_sms(req.sms)

    if Channel.push in req.channels:
        if not req.push:
            return jsonify({"error": "missing_push_payload"}), 400
        results[Channel.push] = service.send_push(req.push)

    resp = NotificationResponse(results=results)
    return jsonify(resp.model_dump())

