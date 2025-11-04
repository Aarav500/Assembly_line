import os
import json
import csv
from typing import Literal
from ..extensions import db
from ..models import User, Product, Order, OrderItem

ImportFormat = Literal['json', 'csv']


def reset_database():
    for model in (OrderItem, Order, Product, User):
        model.query.delete()
    db.session.commit()


def import_json(from_dir: str, reset: bool = True) -> dict:
    if reset:
        reset_database()

    users_p = os.path.join(from_dir, 'users.json')
    products_p = os.path.join(from_dir, 'products.json')
    orders_p = os.path.join(from_dir, 'orders.json')

    counts = {'users': 0, 'products': 0, 'orders': 0, 'order_items': 0}

    with open(users_p, 'r', encoding='utf-8') as f:
        users = json.load(f)
    for u in users:
        user = User(id=u.get('id'), name=u['name'], email=u['email'])
        db.session.add(user)
    counts['users'] = len(users)

    with open(products_p, 'r', encoding='utf-8') as f:
        products = json.load(f)
    for p in products:
        product = Product(id=p.get('id'), name=p['name'], sku=p['sku'], price=p['price'])
        db.session.add(product)
    counts['products'] = len(products)

    db.session.flush()

    with open(orders_p, 'r', encoding='utf-8') as f:
        orders = json.load(f)
    for o in orders:
        order = Order(id=o.get('id'), user_id=o['user_id'], total_amount=o.get('total_amount', 0.0))
        db.session.add(order)
        db.session.flush()
        items = o.get('items', [])
        for it in items:
            item = OrderItem(
                id=it.get('id'),
                order_id=order.id,
                product_id=it['product_id'],
                quantity=it['quantity'],
                unit_price=it['unit_price']
            )
            db.session.add(item)
        counts['order_items'] += len(items)
    counts['orders'] = len(orders)

    db.session.commit()
    return counts


def import_csv(from_dir: str, reset: bool = True) -> dict:
    if reset:
        reset_database()

    counts = {'users': 0, 'products': 0, 'orders': 0, 'order_items': 0}

    # Users
    with open(os.path.join(from_dir, 'users.csv'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        for r in rows:
            user = User(id=int(r['id']), name=r['name'], email=r['email'])
            db.session.add(user)
        counts['users'] = len(rows)

    # Products
    with open(os.path.join(from_dir, 'products.csv'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        for r in rows:
            product = Product(id=int(r['id']), name=r['name'], sku=r['sku'], price=float(r['price']))
            db.session.add(product)
        counts['products'] = len(rows)

    db.session.flush()

    # Orders
    with open(os.path.join(from_dir, 'orders.csv'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        for r in rows:
            order = Order(id=int(r['id']), user_id=int(r['user_id']), total_amount=float(r['total_amount']))
            db.session.add(order)
        counts['orders'] = len(rows)

    db.session.flush()

    # Order Items
    with open(os.path.join(from_dir, 'order_items.csv'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        for r in rows:
            item = OrderItem(
                id=int(r['id']),
                order_id=int(r['order_id']),
                product_id=int(r['product_id']),
                quantity=int(r['quantity']),
                unit_price=float(r['unit_price'])
            )
            db.session.add(item)
        counts['order_items'] = len(rows)

    db.session.commit()
    return counts


def import_data(fmt: ImportFormat, from_dir: str, reset: bool = True) -> dict:
    if fmt == 'json':
        return import_json(from_dir, reset=reset)
    elif fmt == 'csv':
        return import_csv(from_dir, reset=reset)
    else:
        raise ValueError("Unsupported import format. Use 'json' or 'csv'.")

