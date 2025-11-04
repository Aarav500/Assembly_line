from datetime import datetime
from typing import Dict, Any, List
from db import db
from models import Delivery, DeliveryStatus
from config import Config


def queue_delivery(team_id: int, route_id: int, channel: str, target: str, payload: Dict[str, Any], delivery_type: str = 'single') -> Delivery:
    d = Delivery(
        team_id=team_id,
        route_id=route_id,
        channel=channel,
        target=target,
        payload=payload,
        delivery_type=delivery_type,
        status=DeliveryStatus.pending.value,
    )
    db.session.add(d)
    db.session.commit()
    return d


def send_delivery(delivery: Delivery) -> None:
    # Simulate sending by marking as sent and timestamping; in real code, integrate providers
    now = datetime.utcnow()
    try:
        if Config.DRY_RUN_DELIVERY:
            # Simulate success
            delivery.status = DeliveryStatus.sent.value
            delivery.sent_at = now
            delivery.error = None
        else:
            # placeholder for real implementation
            delivery.status = DeliveryStatus.sent.value
            delivery.sent_at = now
            delivery.error = None
    except Exception as e:
        delivery.status = DeliveryStatus.failed.value
        delivery.error = str(e)
    finally:
        db.session.add(delivery)
        db.session.commit()


def send_pending_deliveries(batch_size: int = 100) -> int:
    q = Delivery.query.filter_by(status=DeliveryStatus.pending.value).order_by(Delivery.id.asc()).limit(batch_size)
    count = 0
    for d in q.all():
        send_delivery(d)
        count += 1
    return count

