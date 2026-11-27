"""Tests for order creation, payment, cancellation and listing."""

from fastapi.testclient import TestClient

from app.store import InMemoryStore


def test_create_order_returns_201_and_deducts_stock(
    client: TestClient, store: InMemoryStore
) -> None:
    response = client.post(
        "/orders", json={"items": [{"product_id": 1, "quantity": 2}]}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "created"
    assert body["total_cents"] == 19990 * 2
    assert body["items"][0]["subtotal_cents"] == 19990 * 2
    assert store.get_product(1).stock == 100 - 2


def test_create_order_with_duplicates_aggregates_quantities(
    client: TestClient, store: InMemoryStore
) -> None:
    """Two lines for the same product are merged; stock is deducted once by the total."""
    response = client.post(
        "/orders",
        json={
            "items": [
                {"product_id": 1, "quantity": 3},
                {"product_id": 1, "quantity": 3},
            ]
        },
    )
    assert response.status_code == 201
    assert store.get_product(1).stock == 100 - 6


def test_create_order_duplicate_lines_overselling_returns_409(
    client: TestClient, store: InMemoryStore
) -> None:
    """Even when each line passes independently, the merged total is validated."""
    stock_before = store.get_product(1).stock
    response = client.post(
        "/orders",
        json={
            "items": [
                {"product_id": 1, "quantity": stock_before + 1},
                {"product_id": 1, "quantity": 1},
            ]
        },
    )
    assert response.status_code == 409
    assert store.get_product(1).stock == stock_before


def test_create_order_missing_product_returns_404(client: TestClient) -> None:
    response = client.post(
        "/orders", json={"items": [{"product_id": 999, "quantity": 1}]}
    )
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_create_order_empty_items_returns_422(client: TestClient) -> None:
    assert client.post("/orders", json={"items": []}).status_code == 422


def test_create_order_zero_quantity_returns_422(client: TestClient) -> None:
    response = client.post(
        "/orders", json={"items": [{"product_id": 1, "quantity": 0}]}
    )
    assert response.status_code == 422


def test_create_order_negative_quantity_returns_422(client: TestClient) -> None:
    assert (
        client.post(
            "/orders", json={"items": [{"product_id": 1, "quantity": -1}]}
        ).status_code
        == 422
    )


def test_create_order_unknown_field_returns_422(client: TestClient) -> None:
    response = client.post(
        "/orders",
        json={"items": [{"product_id": 1, "quantity": 1}], "typo": "ignored?"},
    )
    assert response.status_code == 422


def test_create_order_too_many_items_returns_422(client: TestClient) -> None:
    too_many = [{"product_id": 1, "quantity": 1}] * 51
    assert client.post("/orders", json={"items": too_many}).status_code == 422


def test_create_order_atomic_rollback_on_failure(
    client: TestClient, store: InMemoryStore
) -> None:
    """If any line fails validation, previously valid lines must not deduct stock."""
    stock_before = store.get_product(1).stock
    response = client.post(
        "/orders",
        json={
            "items": [
                {"product_id": 1, "quantity": 1},
                {"product_id": 999, "quantity": 1},
            ]
        },
    )
    assert response.status_code == 404
    assert store.get_product(1).stock == stock_before


def test_get_order_existing(client: TestClient) -> None:
    created = client.post(
        "/orders", json={"items": [{"product_id": 1, "quantity": 1}]}
    ).json()
    response = client.get(f"/orders/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_order_missing_returns_404(client: TestClient) -> None:
    assert client.get("/orders/999").status_code == 404


def test_pay_order_returns_paid(client: TestClient) -> None:
    oid = client.post(
        "/orders", json={"items": [{"product_id": 1, "quantity": 1}]}
    ).json()["id"]
    response = client.post(f"/orders/{oid}/pay")
    assert response.status_code == 200
    assert response.json()["status"] == "paid"


def test_pay_order_twice_returns_409(client: TestClient) -> None:
    oid = client.post(
        "/orders", json={"items": [{"product_id": 1, "quantity": 1}]}
    ).json()["id"]
    assert client.post(f"/orders/{oid}/pay").status_code == 200
    assert client.post(f"/orders/{oid}/pay").status_code == 409


def test_pay_missing_order_returns_404(client: TestClient) -> None:
    assert client.post("/orders/999/pay").status_code == 404


def test_cancel_order_returns_stock(client: TestClient, store: InMemoryStore) -> None:
    oid = client.post(
        "/orders", json={"items": [{"product_id": 2, "quantity": 1}]}
    ).json()["id"]
    stock_after_buy = store.get_product(2).stock
    response = client.post(f"/orders/{oid}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert store.get_product(2).stock == stock_after_buy + 1


def test_cancel_after_pay_returns_409(client: TestClient) -> None:
    oid = client.post(
        "/orders", json={"items": [{"product_id": 1, "quantity": 1}]}
    ).json()["id"]
    client.post(f"/orders/{oid}/pay")
    response = client.post(f"/orders/{oid}/cancel")
    assert response.status_code == 409
    assert "paid" in response.json()["detail"]


def test_cancel_twice_returns_409(client: TestClient) -> None:
    oid = client.post(
        "/orders", json={"items": [{"product_id": 1, "quantity": 1}]}
    ).json()["id"]
    assert client.post(f"/orders/{oid}/cancel").status_code == 200
    assert client.post(f"/orders/{oid}/cancel").status_code == 409


def test_cancel_missing_order_returns_404(client: TestClient) -> None:
    assert client.post("/orders/999/cancel").status_code == 404


def test_list_orders_returns_created(client: TestClient) -> None:
    client.post("/orders", json={"items": [{"product_id": 1, "quantity": 1}]})
    client.post("/orders", json={"items": [{"product_id": 2, "quantity": 1}]})
    body = client.get("/orders").json()
    assert body["total"] == 2
    assert body["limit"] == 20


def test_list_orders_filter_by_status(client: TestClient) -> None:
    paid = client.post(
        "/orders", json={"items": [{"product_id": 1, "quantity": 1}]}
    ).json()["id"]
    cancelled = client.post(
        "/orders", json={"items": [{"product_id": 2, "quantity": 1}]}
    ).json()["id"]
    client.post("/orders", json={"items": [{"product_id": 3, "quantity": 1}]})

    client.post(f"/orders/{paid}/pay")
    client.post(f"/orders/{cancelled}/cancel")

    assert client.get("/orders", params={"status": "paid"}).json()["total"] == 1
    assert client.get("/orders", params={"status": "cancelled"}).json()["total"] == 1
    assert client.get("/orders", params={"status": "created"}).json()["total"] == 1


def test_list_orders_invalid_status_returns_422(client: TestClient) -> None:
    assert client.get("/orders", params={"status": "shipped"}).status_code == 422


def test_list_orders_limit_too_large_returns_422(client: TestClient) -> None:
    assert client.get("/orders", params={"limit": 1000}).status_code == 422
