from typing import List, Dict

_items: List[Dict] = []
_next_id: int = 1


def add_item(name: str, price: float, tags=None) -> Dict:
    global _next_id
    if tags is None:
        tags = []
    item = {
        "id": _next_id,
        "name": name,
        "price": float(price),
        "tags": list(tags),
    }
    _items.append(item)
    _next_id += 1
    return item


def get_items() -> List[Dict]:
    return list(_items)

