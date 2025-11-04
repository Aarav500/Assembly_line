import uuid
from storage.redis_client import get_redis


def get_user_by_api_key(api_key: str) -> dict | None:
    if not api_key:
        return None
    r = get_redis()
    user_id = r.get(f"api:key:{api_key}")
    if not user_id:
        return None
    return get_user(user_id)


def get_user(user_id: str) -> dict | None:
    r = get_redis()
    data = r.hgetall(f"api:user:{user_id}")
    if not data:
        return None
    data["id"] = user_id
    return data


def create_user(email: str, tier: str, billing_id: str | None = None, user_id: str | None = None) -> dict:
    r = get_redis()
    if not user_id:
        user_id = str(uuid.uuid4())
    api_key = uuid.uuid4().hex
    key = f"api:user:{user_id}"
    r.hset(key, mapping={
        "email": email,
        "tier": tier,
        "api_key": api_key,
        "billing_id": billing_id or "",
    })
    r.set(f"api:key:{api_key}", user_id)
    return {
        "id": user_id,
        "email": email,
        "tier": tier,
        "api_key": api_key,
        "billing_id": billing_id or "",
    }


def list_users() -> list[dict]:
    r = get_redis()
    users = []
    for key in r.scan_iter(match="api:user:*", count=100):
        data = r.hgetall(key)
        uid = key.split(":")[-1]
        data["id"] = uid
        users.append(data)
    return users


def ensure_demo_user():
    r = get_redis()
    # Avoid duplicating
    for ukey in r.scan_iter(match="api:user:*", count=10):
        return
    # Create a demo user
    create_user(email="demo@example.com", tier="free", billing_id="demo-billing")

