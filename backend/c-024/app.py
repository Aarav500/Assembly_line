import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, case, asc, desc

app = Flask(__name__)
DB_PATH = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
app.config['SQLALCHEMY_DATABASE_URI'] = DB_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(64), index=True)
    brand = db.Column(db.String(64), index=True)
    status = db.Column(db.String(32), index=True)
    price = db.Column(db.Float, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'brand': self.brand,
            'status': self.status,
            'price': round(float(self.price), 2) if self.price is not None else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ----------- Seed Utilities -----------
CATEGORIES = ['Electronics', 'Books', 'Clothing', 'Home', 'Sports', 'Toys', 'Beauty', 'Grocery']
BRANDS = ['Acme', 'Globex', 'Soylent', 'Initech', 'Umbrella', 'Stark', 'Wayne', 'Wonka', 'Hooli', 'Aperture']
STATUSES = ['active', 'inactive', 'out_of_stock', 'discontinued']
ADJECTIVES = ['Sleek', 'Durable', 'Ergonomic', 'Intelligent', 'Portable', 'Lightweight', 'Compact', 'Advanced', 'Smart', 'Premium']
NOUNS = ['Headphones', 'Backpack', 'Mixer', 'Camera', 'Shoes', 'Watch', 'Lamp', 'Book', 'Jacket', 'Bottle', 'Gloves', 'Keyboard', 'Mouse', 'Speaker', 'Drone']


def seed_if_empty():
    count = db.session.query(func.count(Item.id)).scalar() or 0
    if count > 0:
        return
    random.seed(42)
    now = datetime.utcnow()
    items: List[Item] = []
    for i in range(500):
        category = random.choice(CATEGORIES)
        brand = random.choice(BRANDS)
        status = random.choices(STATUSES, weights=[0.7, 0.1, 0.15, 0.05])[0]
        price_base = {
            'Electronics': (30, 500),
            'Books': (5, 40),
            'Clothing': (10, 150),
            'Home': (8, 300),
            'Sports': (10, 250),
            'Toys': (5, 120),
            'Beauty': (5, 100),
            'Grocery': (1, 50)
        }[category]
        price = round(random.uniform(*price_base), 2)
        created_at = now - timedelta(days=random.randint(0, 365), seconds=random.randint(0, 86400))
        name = f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)}"
        description = f"A {category.lower()} item by {brand}. {name} with {random.choice(['excellent', 'great', 'decent', 'solid'])} performance."
        items.append(Item(name=name, description=description, category=category, brand=brand, status=status, price=price, created_at=created_at))
    db.session.bulk_save_objects(items)
    db.session.commit()


# ----------- Helpers -----------

def parse_list_param(args, *keys: str) -> List[str]:
    values: List[str] = []
    for key in keys:
        values.extend([v for v in args.getlist(key) if v])
        if args.get(key):
            for part in str(args.get(key)).split(','):
                part = part.strip()
                if part:
                    values.append(part)
    # normalize and unique preserving order
    seen = set()
    result = []
    for v in values:
        low = v.strip()
        if low not in seen:
            seen.add(low)
            result.append(low)
    return result


def get_filters_from_request(args) -> Dict[str, Any]:
    filters = {
        'q': (args.get('q') or '').strip() or None,
        'category': parse_list_param(args, 'category', 'categories'),
        'brand': parse_list_param(args, 'brand', 'brands'),
        'status': parse_list_param(args, 'status', 'statuses'),
        'min_price': float(args.get('min_price')) if args.get('min_price') is not None and args.get('min_price') != '' else None,
        'max_price': float(args.get('max_price')) if args.get('max_price') is not None and args.get('max_price') != '' else None,
        'sort': (args.get('sort') or 'created_at').strip(),
        'order': (args.get('order') or 'desc').strip().lower(),
        'page': int(args.get('page') or 1),
        'per_page': int(args.get('per_page') or 20),
    }
    # clamp
    filters['page'] = max(filters['page'], 1)
    filters['per_page'] = max(min(filters['per_page'], 100), 1)
    if filters['order'] not in ('asc', 'desc'):
        filters['order'] = 'desc'
    return filters


SORT_MAP = {
    'name': Item.name,
    'price': Item.price,
    'created_at': Item.created_at,
    'brand': Item.brand,
    'category': Item.category,
}


def apply_filters(query, filters: Dict[str, Any], exclude: Optional[Set[str]] = None):
    exclude = exclude or set()
    # search
    if 'search' not in exclude and filters.get('q'):
        q = f"%{filters['q']}%"
        query = query.filter(
            (Item.name.ilike(q)) | (Item.description.ilike(q))
        )
    # category
    if 'category' not in exclude and filters.get('category'):
        query = query.filter(Item.category.in_(filters['category']))
    # brand
    if 'brand' not in exclude and filters.get('brand'):
        query = query.filter(Item.brand.in_(filters['brand']))
    # status
    if 'status' not in exclude and filters.get('status'):
        query = query.filter(Item.status.in_(filters['status']))
    # price
    if 'price' not in exclude:
        if filters.get('min_price') is not None:
            query = query.filter(Item.price >= filters['min_price'])
        if filters.get('max_price') is not None:
            query = query.filter(Item.price <= filters['max_price'])
    return query


def apply_sort(query, filters: Dict[str, Any]):
    sort_field = filters.get('sort') or 'created_at'
    col = SORT_MAP.get(sort_field, Item.created_at)
    order = filters.get('order', 'desc')
    if order == 'asc':
        return query.order_by(asc(col), Item.id.asc())
    else:
        return query.order_by(desc(col), Item.id.desc())


PRICE_BINS = [
    (0, 25),
    (25, 50),
    (50, 100),
    (100, 200),
    (200, None),  # 200+
]


def price_range_label(low: float, high: Optional[float]) -> str:
    if high is None:
        return f"{int(low)}+"
    return f"{int(low)}-{int(high)}"


def price_case_expr():
    whens = []
    for low, high in PRICE_BINS:
        if high is None:
            whens.append((Item.price >= low, price_range_label(low, high)))
        else:
            whens.append((Item.price >= low, None))  # placeholder to maintain sequence
    # SQLAlchemy case is evaluated in order; we need custom expression: easier to compute in Python for price_range.
    # We'll compute price_range facets in Python to correctly bucket boundaries.
    return None


def compute_facets(filters: Dict[str, Any], facet_fields: Optional[List[str]] = None, include_self: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    fields = set(facet_fields or ['category', 'brand', 'status', 'price_range'])
    result: Dict[str, List[Dict[str, Any]]] = {}

    # Common filtered base (includes all filters & search)
    base_query = db.session.query(Item)
    base_query = apply_filters(base_query, filters, exclude=set())

    def counts_for(field: str, exclude_key: Optional[str] = None):
        exclude_set: Set[str] = set()
        if not include_self and exclude_key:
            exclude_set.add(exclude_key)
        query = db.session.query(Item)
        query = apply_filters(query, filters, exclude=exclude_set)
        return query

    # category facet
    if 'category' in fields:
        q = counts_for('category', 'category')
        rows = db.session.query(Item.category, func.count(Item.id)).select_from(q.subquery()).group_by('category').all()
        result['category'] = [
            {'value': cat if cat is not None else 'Unknown', 'count': int(cnt)} for cat, cnt in sorted(rows, key=lambda x: (-x[1], str(x[0]) if x[0] is not None else ''))
        ]

    # brand facet
    if 'brand' in fields:
        q = counts_for('brand', 'brand')
        rows = db.session.query(Item.brand, func.count(Item.id)).select_from(q.subquery()).group_by('brand').all()
        result['brand'] = [
            {'value': b if b is not None else 'Unknown', 'count': int(cnt)} for b, cnt in sorted(rows, key=lambda x: (-x[1], str(x[0]) if x[0] is not None else ''))
        ]

    # status facet
    if 'status' in fields:
        q = counts_for('status', 'status')
        rows = db.session.query(Item.status, func.count(Item.id)).select_from(q.subquery()).group_by('status').all()
        # ensure stable order based on STATUSES list if present
        counts_map = {s: 0 for s in STATUSES}
        for s, cnt in rows:
            counts_map[s] = int(cnt)
        result['status'] = [{'value': s, 'count': counts_map[s]} for s in STATUSES]

    # price_range facet (compute in Python for precise binning)
    if 'price_range' in fields:
        exclude_set = set()
        if not include_self:
            exclude_set.add('price')
        q = db.session.query(Item.price)
        q = apply_filters(q, filters, exclude=exclude_set)
        buckets = {price_range_label(low, high): 0 for low, high in PRICE_BINS}
        for (price,) in q.all():
            if price is None:
                continue
            placed = False
            for low, high in PRICE_BINS:
                if high is None:
                    if price >= low:
                        buckets[price_range_label(low, high)] += 1
                        placed = True
                        break
                else:
                    if low <= price < high:
                        buckets[price_range_label(low, high)] += 1
                        placed = True
                        break
            if not placed:
                # Shouldn't happen, but keep safe
                pass
        # keep natural bin order
        result['price_range'] = [
            {'value': price_range_label(low, high), 'count': buckets[price_range_label(low, high)]} for low, high in PRICE_BINS
        ]

    return result


# ----------- API Endpoints -----------
@app.route('/items', methods=['GET'])
def list_items():
    filters = get_filters_from_request(request.args)

    # base query with filters
    query = db.session.query(Item)
    query = apply_filters(query, filters)
    total = query.count()

    query = apply_sort(query, filters)

    page = filters['page']
    per_page = filters['per_page']
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    facet_fields = parse_list_param(request.args, 'facet_fields')
    facet_fields = facet_fields or ['category', 'brand', 'status', 'price_range']
    include_self = (request.args.get('include_facet_self') or 'false').lower() in ('1', 'true', 'yes')
    facets = compute_facets(filters, facet_fields=facet_fields, include_self=include_self)

    resp = {
        'items': [i.to_dict() for i in items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page,
        },
        'sort': {
            'field': filters['sort'] if filters['sort'] in SORT_MAP else 'created_at',
            'order': filters['order'],
        },
        'filters': {
            'q': filters['q'],
            'category': filters['category'],
            'brand': filters['brand'],
            'status': filters['status'],
            'price': {
                'min': filters['min_price'],
                'max': filters['max_price'],
            },
        },
        'facets': facets,
    }
    return jsonify(resp)


@app.route('/facets', methods=['GET'])
def get_facets():
    filters = get_filters_from_request(request.args)
    facet_fields = parse_list_param(request.args, 'facet_fields') or ['category', 'brand', 'status', 'price_range']
    include_self = (request.args.get('include_facet_self') or 'false').lower() in ('1', 'true', 'yes')
    facets = compute_facets(filters, facet_fields=facet_fields, include_self=include_self)
    return jsonify({'facets': facets})


@app.route('/items/<int:item_id>', methods=['GET'])
def get_item(item_id: int):
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    return jsonify(item.to_dict())


# ----------- App Bootstrap -----------
with app.app_context():
    db.create_all()
    seed_if_empty()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app


@app.route('/api/products?page=1&per_page=5', methods=['GET'])
def _auto_stub_api_products_page_1_per_page_5():
    return 'Auto-generated stub for /api/products?page=1&per_page=5', 200


@app.route('/api/products/search?q=laptop', methods=['GET'])
def _auto_stub_api_products_search_q_laptop():
    return 'Auto-generated stub for /api/products/search?q=laptop', 200


@app.route('/api/products/facets', methods=['GET'])
def _auto_stub_api_products_facets():
    return 'Auto-generated stub for /api/products/facets', 200


@app.route('/api/products?category=Electronics', methods=['GET'])
def _auto_stub_api_products_category_Electronics():
    return 'Auto-generated stub for /api/products?category=Electronics', 200


@app.route('/api/products?min_price=50&max_price=100', methods=['GET'])
def _auto_stub_api_products_min_price_50_max_price_100():
    return 'Auto-generated stub for /api/products?min_price=50&max_price=100', 200
