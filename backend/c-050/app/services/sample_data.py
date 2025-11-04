import random
import string
from datetime import datetime, timedelta
from typing import Optional
from ..extensions import db
from ..models import User, Product, Order, OrderItem

FIRST_NAMES = ["Alex", "Sam", "Taylor", "Jordan", "Morgan", "Chris", "Pat", "Riley", "Casey", "Jamie"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"]
PRODUCT_ADJ = ["Ultra", "Pro", "Lite", "Max", "Mini", "Eco", "Prime", "Smart", "Nano", "Hyper"]
PRODUCT_NOUN = ["Phone", "Laptop", "Headphones", "Monitor", "Keyboard", "Mouse", "Speaker", "Camera", "Router", "Tablet"]


def _rand_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _rand_email(rng: random.Random, name: str) -> str:
    user = ''.join(c for c in name.lower() if c.isalpha())
    num = rng.randint(1, 9999)
    domain = rng.choice(["example.com", "demo.io", "sample.org"]) 
    return f"{user}{num}@{domain}"


def _rand_sku(rng: random.Random) -> str:
    return ''.join(rng.choices(string.ascii_uppercase + string.digits, k=10))


def _rand_product_name(rng: random.Random) -> str:
    return f"{rng.choice(PRODUCT_ADJ)} {rng.choice(PRODUCT_NOUN)}"


def _rand_date_in_past(rng: random.Random, days: int = 180) -> datetime:
    return datetime.utcnow() - timedelta(days=rng.randint(0, days), seconds=rng.randint(0, 86400))


def generate_sample_data(users: int = 10, products: int = 15, orders: int = 20, seed: Optional[int] = None, commit: bool = True):
    rng = random.Random(seed)

    # Clear existing data
    for model in (OrderItem, Order, Product, User):
        model.query.delete()
    db.session.commit()

    # Users
    user_objs = []
    for _ in range(users):
        name = _rand_name(rng)
        user = User(
            name=name,
            email=_rand_email(rng, name),
            created_at=_rand_date_in_past(rng)
        )
        user_objs.append(user)
        db.session.add(user)

    # Products
    product_objs = []
    for _ in range(products):
        p = Product(
            name=_rand_product_name(rng),
            sku=_rand_sku(rng),
            price=round(rng.uniform(9.99, 999.99), 2),
            created_at=_rand_date_in_past(rng)
        )
        product_objs.append(p)
        db.session.add(p)

    db.session.flush()

    # Orders
    order_objs = []
    for _ in range(orders):
        user = rng.choice(user_objs)
        o = Order(
            user_id=user.id,
            created_at=_rand_date_in_past(rng)
        )
        db.session.add(o)
        db.session.flush()  # to get order id

        num_items = rng.randint(1, 5)
        total = 0.0
        for _i in range(num_items):
            product = rng.choice(product_objs)
            qty = rng.randint(1, 4)
            item = OrderItem(
                order_id=o.id,
                product_id=product.id,
                quantity=qty,
                unit_price=product.price
            )
            total += qty * product.price
            db.session.add(item)
        o.total_amount = round(total, 2)
        order_objs.append(o)

    if commit:
        db.session.commit()

    return {
        'users': len(user_objs),
        'products': len(product_objs),
        'orders': len(order_objs)
    }

