from datetime import datetime
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<User {self.id} {self.email}>'


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(Numeric(10, 2), nullable=False, default=Decimal('0.00'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Product {self.id} {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    total = db.Column(Numeric(12, 2), nullable=False, default=Decimal('0.00'))

    user = db.relationship('User', backref=db.backref('orders', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<Order {self.id} u={self.user_id}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(Numeric(10, 2), nullable=False, default=Decimal('0.00'))

    order = db.relationship('Order', backref=db.backref('items', cascade='all, delete-orphan'))
    product = db.relationship('Product')

    def __repr__(self):
        return f'<OrderItem {self.id} o={self.order_id} p={self.product_id}>'

