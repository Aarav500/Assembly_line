import threading

_items = []
_lock = threading.Lock()
_next_id = 1


def next_id():
    global _next_id
    with _lock:
        nid = _next_id
        _next_id += 1
        return nid


def add_item(item: dict):
    with _lock:
        _items.append(item)


def get_items():
    with _lock:
        return list(_items)


def reset():
    global _items, _next_id
    with _lock:
        _items = []
        _next_id = 1

