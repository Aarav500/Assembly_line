from datetime import datetime, timedelta
import random
from database import init_db, SessionLocal
from models import Service, Measurement


def seed():
    init_db()
    db = SessionLocal()

    svc = Service(
        name="checkout",
        description="Checkout API",
        timezone="UTC",
        slo_availability_target=0.999,
        slo_latency_ms_p95=300,
        slo_error_rate_target=0.001,
        slo_window_days=30,
    )
    db.add(svc)
    db.commit()
    db.refresh(svc)

    # Seed last 2 days of synthetic measurements: 1 per 5 minutes
    now = datetime.utcnow()
    start = now - timedelta(days=2)
    t = start
    while t < now:
        up = random.random() > 0.002  # ~99.8% up
        latency = random.gauss(180 if up else 800, 40)
        requests = random.randint(50, 200)
        errors = 0 if up else random.randint(1, 5)
        m = Measurement(
            service_id=svc.id,
            ts_utc=t,
            up=up,
            latency_ms=max(1.0, latency),
            errors=errors,
            requests=requests,
            source="seed",
        )
        db.add(m)
        t += timedelta(minutes=5)
    db.commit()
    db.close()
    print("Seeded service 'checkout' and measurements")


if __name__ == "__main__":
    seed()

