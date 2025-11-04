import random
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch

from src.config import get_es_client, INDEX_NAME
from src.index_manager import create_index, bulk_index

CATEGORIES = ["Electronics", "Home", "Books", "Toys", "Computers", "Audio"]
BRANDS = ["Acme", "Globex", "Umbrella", "Initech", "Soylent", "Aperture"]
TAGS = ["new", "sale", "popular", "refurbished", "premium", "budget"]

TITLES = [
    "4K Ultra HD TV",
    "Wireless Noise-Cancelling Headphones",
    "Gaming Laptop 15-inch",
    "Smartphone Pro Max",
    "Portable Bluetooth Speaker",
    "Mirrorless Camera 24MP",
    "External SSD 1TB",
    "Mechanical Keyboard RGB",
    "Smart Home Hub",
    "E-Reader with Backlight"
]

DESCRIPTIONS = [
    "High performance device with long battery life and crisp display.",
    "Experience immersive sound and deep bass in a compact form.",
    "Next-gen processing power with sleek aluminum chassis.",
    "Capture stunning photos with advanced AI processing.",
    "Perfect for streaming, gaming, and productivity.",
]


def rand_doc(i: int) -> dict:
    title = random.choice(TITLES)
    brand = random.choice(BRANDS)
    category = random.choice(CATEGORIES)
    tags = random.sample(TAGS, k=random.randint(1, 3))
    price = round(random.uniform(10, 2500), 2)
    created_at = datetime.utcnow() - timedelta(days=random.randint(0, 365))
    description = random.choice(DESCRIPTIONS)
    attributes = {
        "color": random.choice(["black", "white", "silver", "blue", "red"]),
        "warranty": random.choice(["1y", "2y", "3y"]),
    }
    return {
        "id": f"seed-{i}",
        "title": title,
        "description": description,
        "brand": brand,
        "category": category,
        "tags": tags,
        "price": price,
        "created_at": created_at.isoformat(),
        "attributes": attributes,
    }


def main():
    es: Elasticsearch = get_es_client()
    create_index(es, INDEX_NAME)
    docs = [rand_doc(i) for i in range(1, 501)]
    res = bulk_index(es, INDEX_NAME, docs)
    print(res)


if __name__ == "__main__":
    main()

