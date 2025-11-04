import random
from decimal import Decimal
from typing import Dict, Optional
from faker import Faker
from sqlalchemy import func

from models import db, User, Product, Order, OrderItem


def get_counts() -> Dict[str, int]:
    users = db.session.scalar(db.select(func.count(User.id))) or 0
    products = db.session.scalar(db.select(func.count(Product.id))) or 0
    orders = db.session.scalar(db.select(func.count(Order.id))) or 0
    items = db.session.scalar(db.select(func.count(OrderItem.id))) or 0
    return {
        'users': users,
        'products': products,
        'orders': orders,
        'order_items': items,
    }


def clear_database() -> None:
    # Delete in child->parent order to satisfy FKs
    db.session.execute(db.delete(OrderItem))
    db.session.execute(db.delete(Order))
    db.session.execute(db.delete(Product))
    db.session.execute(db.delete(User))
    db.session.flush()


def _ensure_decimal(val: float) -> Decimal:
    return (Decimal(val).quantize(Decimal('0.01')))


def generate_demo_data(target_users: int = 25, target_products: int = 20, target_orders: int = 50, seed: Optional[int] = None):
    if seed is not None:
        random.seed(int(seed))
    faker = Faker()
    if seed is not None:
        Faker.seed(int(seed))
        faker.seed_instance(int(seed))

    # Determine how many to add to reach targets
    counts_before = get_counts()
    to_add_users = max(0, target_users - counts_before['users'])
    to_add_products = max(0, target_products - counts_before['products'])
    to_add_orders = max(0, target_orders - counts_before['orders'])

    created = {'users': 0, 'products': 0, 'orders': 0, 'order_items': 0}

    # Users
    new_users = []
    for _ in range(to_add_users):
        name = faker.name()
        email = faker.unique.email()
        new_users.append(User(name=name, email=email))
    if new_users:
        db.session.add_all(new_users)
        db.session.flush()
        created['users'] += len(new_users)

    # Products
    new_products = []
    for _ in range(to_add_products):
        name = faker.unique.catch_phrase()
        description = faker.text(max_nb_chars=160)
        price = _ensure_decimal(random.uniform(5.0, 499.99))
        new_products.append(Product(name=name, description=description, price=price))
    if new_products:
        db.session.add_all(new_products)
        db.session.flush()
        created['products'] += len(new_products)

    # Fetch available users/products for order creation
    users = db.session.scalars(db.select(User)).all()
    products = db.session.scalars(db.select(Product)).all()

    if users and products:
        for _ in range(to_add_orders):
            user = random.choice(users)
            order = Order(user_id=user.id, total=Decimal('0.00'))
            db.session.add(order)
            db.session.flush()  # ensure order.id

            num_items = random.randint(1, min(5, len(products)))
            line_products = random.sample(products, k=num_items)
            order_total = Decimal('0.00')

            for p in line_products:
                qty = random.randint(1, 4)
                unit_price = Decimal(p.price)  # already Decimal via Numeric
                line_total = unit_price * qty
                order_total += line_total
                oi = OrderItem(order_id=order.id, product_id=p.id, quantity=qty, unit_price=unit_price)
                db.session.add(oi)
                created['order_items'] += 1

            order.total = order_total.quantize(Decimal('0.01'))
            created['orders'] += 1

    db.session.flush()

    totals_after = get_counts()

    return {
        'created': created,
        'totals': totals_after
    }

