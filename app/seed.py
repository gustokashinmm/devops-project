"""Deterministic seed data for the catalog.

The same catalog is created on every start: fixed titles, prices and ids.
That keeps tests, curl examples and load-test scenarios reproducible.
"""

from app.config import Settings
from app.store import InMemoryStore

# (title, price in kopecks, category)
CATALOG: tuple[tuple[str, int, str], ...] = (
    ("Wireless Mouse", 19990, "electronics"),
    ("Mechanical Keyboard", 54990, "electronics"),
    ("USB-C Hub", 32990, "electronics"),
    ("Monitor 27-inch", 249990, "electronics"),
    ("Laptop Stand", 12490, "accessories"),
    ("Notebook A5", 4990, "stationery"),
    ("Gel Pen Set", 8990, "stationery"),
    ("Desk Lamp", 34990, "home"),
    ("Coffee Mug", 7990, "home"),
    ("Water Bottle", 11990, "home"),
)


def seed_catalog(store: InMemoryStore, settings: Settings) -> int:
    """Fill an empty catalog. Idempotent: returns 0 if it is already filled."""
    if store.count_products() > 0:
        return 0

    for index in range(settings.seed_products):
        title, price_cents, category = CATALOG[index % len(CATALOG)]
        repeat = index // len(CATALOG)
        if repeat:
            title = f"{title} #{repeat + 1}"
        store.add_product(
            title=title,
            price_cents=price_cents,
            category=category,
            stock=settings.seed_stock,
        )
    return settings.seed_products
