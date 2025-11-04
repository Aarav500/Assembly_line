import os
import json
import csv
from typing import Literal
from ..models import User, Product, Order, OrderItem

ExportFormat = Literal['json', 'csv', 'both']


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def export_json(out_dir: str = "exports/json") -> dict:
    _ensure_dir(out_dir)

    users = [u.to_dict() for u in User.query.order_by(User.id).all()]
    products = [p.to_dict() for p in Product.query.order_by(Product.id).all()]
    orders = [o.to_dict(include_items=True) for o in Order.query.order_by(Order.id).all()]

    with open(os.path.join(out_dir, 'users.json'), 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, 'products.json'), 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, 'orders.json'), 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    return {'json': {'users': len(users), 'products': len(products), 'orders': len(orders)}}


def export_csv(out_dir: str = "exports/csv") -> dict:
    _ensure_dir(out_dir)

    users = User.query.order_by(User.id).all()
    with open(os.path.join(out_dir, 'users.csv'), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'name', 'email', 'created_at'])
        for u in users:
            writer.writerow([u.id, u.name, u.email, u.created_at.isoformat()])

    products = Product.query.order_by(Product.id).all()
    with open(os.path.join(out_dir, 'products.csv'), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'name', 'sku', 'price', 'created_at'])
        for p in products:
            writer.writerow([p.id, p.name, p.sku, p.price, p.created_at.isoformat()])

    orders = Order.query.order_by(Order.id).all()
    with open(os.path.join(out_dir, 'orders.csv'), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'user_id', 'total_amount', 'created_at'])
        for o in orders:
            writer.writerow([o.id, o.user_id, o.total_amount, o.created_at.isoformat()])

    items = OrderItem.query.order_by(OrderItem.id).all()
    with open(os.path.join(out_dir, 'order_items.csv'), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'order_id', 'product_id', 'quantity', 'unit_price'])
        for i in items:
            writer.writerow([i.id, i.order_id, i.product_id, i.quantity, i.unit_price])

    return {
        'csv': {
            'users': len(users),
            'products': len(products),
            'orders': len(orders),
            'order_items': len(items)
        }
    }


def export_data(fmt: ExportFormat = 'both', out_base: str = 'exports') -> dict:
    results = {}
    if fmt in ('json', 'both'):
        results.update(export_json(os.path.join(out_base, 'json')))
    if fmt in ('csv', 'both'):
        results.update(export_csv(os.path.join(out_base, 'csv')))
    return results

