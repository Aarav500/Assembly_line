from datetime import datetime, timezone

USERS: dict[int, dict] = {}
_counter = 0


def next_id() -> int:
    global _counter
    _counter += 1
    return _counter


def seed() -> None:
    if USERS:
        return
    for name, email in [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]:
        uid = next_id()
        USERS[uid] = {
            "id": uid,
            "name": name,
            "email": email,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

