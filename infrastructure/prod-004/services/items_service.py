from datetime import datetime
from typing import List, Dict, Tuple
from storage import db


def list_items_v2():
    # Returns v2 representation: id, name, price, created_at
    items = db.get_items()
    return items, 200


def list_items_v1():
    # v1 representation: id, title (name renamed), no price/created_at
    items = db.get_items()
    v1_items = []
    for it in items:
        v1_items.append({
            'id': it['id'],
            'title': it['name'],
        })
    return v1_items, 200


def create_item_v2(payload: Dict):
    # Expecting fields: name (str), price (float)
    name = payload.get('name')
    price = payload.get('price', 0.0)
    if not name:
        return {'error': 'name is required'}, 400
    try:
        price = float(price)
    except Exception:
        return {'error': 'price must be a number'}, 400

    new_item = {
        'id': db.next_id(),
        'name': name,
        'price': price,
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }
    db.add_item(new_item)
    return new_item, 201

