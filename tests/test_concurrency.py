"""Concurrency tests: the store must never oversell under parallel requests.

FastAPI executes sync endpoints in a thread pool, so these tests produce real
contention for the lock instead of a simulated one.
"""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.store import InMemoryStore, InsufficientStock


def test_parallel_orders_never_oversell(
    client: TestClient, store: InMemoryStore
) -> None:
    """50 parallel buyers, 5 units in stock: exactly 5 succeed, stock ends at 0."""
    product = store.add_product("Last item", 10000, "test", 5)

    def buy(_: int) -> int:
        response = client.post(
            "/orders", json={"items": [{"product_id": product.id, "quantity": 1}]}
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=20) as pool:
        statuses = list(pool.map(buy, range(50)))

    assert statuses.count(201) == 5
    assert statuses.count(409) == 45
    assert store.get_product(product.id).stock == 0


def test_parallel_cancel_restores_stock_once(
    client: TestClient, store: InMemoryStore
) -> None:
    """Only one parallel cancellation succeeds, stock is returned exactly once."""
    created = client.post("/orders", json={"items": [{"product_id": 1, "quantity": 2}]})
    order_id = created.json()["id"]
    assert store.get_product(1).stock == 98

    def cancel(_: int) -> int:
        return client.post(f"/orders/{order_id}/cancel").status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(cancel, range(10)))

    assert statuses.count(200) == 1
    assert statuses.count(409) == 9
    assert store.get_product(1).stock == 100


def test_parallel_orders_at_store_level_never_oversell(store: InMemoryStore) -> None:
    """The same invariant without HTTP: the lock protects the store itself."""
    product = store.add_product("Bulk item", 5000, "test", 7)

    def buy(_: int) -> bool:
        try:
            store.create_order([(product.id, 1)])
            return True
        except InsufficientStock:
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(buy, range(40)))

    assert sum(results) == 7
    assert store.get_product(product.id).stock == 0
