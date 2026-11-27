"""Tests for catalog endpoints: listing, filtering, pagination and single read."""

import pytest
from fastapi.testclient import TestClient


def test_list_products_returns_200(client: TestClient) -> None:
    assert client.get("/products").status_code == 200


def test_list_products_returns_full_catalog(client: TestClient) -> None:
    data = client.get("/products").json()
    assert data["total"] == 10
    assert len(data["items"]) == 10
    assert data["offset"] == 0
    assert data["limit"] == 20


def test_list_products_default_limit_from_settings(client: TestClient) -> None:
    data = client.get("/products").json()
    assert data["limit"] == 20  # settings.default_page_limit


def test_list_products_custom_limit(client: TestClient) -> None:
    data = client.get("/products", params={"limit": 3}).json()
    assert len(data["items"]) == 3
    assert data["limit"] == 3
    assert data["total"] == 10


def test_list_products_offset(client: TestClient) -> None:
    data = client.get("/products", params={"limit": 3, "offset": 7}).json()
    assert len(data["items"]) == 3
    assert data["offset"] == 7
    assert data["total"] == 10


def test_list_products_offset_beyond_total(client: TestClient) -> None:
    data = client.get("/products", params={"offset": 100}).json()
    assert data["items"] == []
    assert data["total"] == 10


def test_list_products_filter_existing_category(client: TestClient) -> None:
    data = client.get("/products", params={"category": "electronics"}).json()
    assert data["total"] == 4
    assert all(p["category"] == "electronics" for p in data["items"])


def test_list_products_filter_missing_category(client: TestClient) -> None:
    data = client.get("/products", params={"category": "nope"}).json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_products_deterministic_ids(client: TestClient) -> None:
    data = client.get("/products").json()
    first = data["items"][0]
    assert first == {
        "id": 1,
        "title": "Wireless Mouse",
        "price_cents": 19990,
        "category": "electronics",
        "stock": 100,
    }


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": -1},
        {"limit": 1000},  # above settings.max_page_limit
        {"offset": -1},
        {"category": ""},
    ],
)
def test_list_products_rejects_invalid_params(client: TestClient, params: dict) -> None:
    assert client.get("/products", params=params).status_code == 422


def test_get_product_existing(client: TestClient) -> None:
    response = client.get("/products/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "Wireless Mouse"
    assert data["price_cents"] == 19990


def test_get_product_missing(client: TestClient) -> None:
    response = client.get("/products/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Product 999 not found"


@pytest.mark.parametrize("product_id", [0, -5, 999999])
def test_get_product_invalid_or_missing_id(client: TestClient, product_id: int) -> None:
    response = client.get(f"/products/{product_id}")
    expected = 422 if product_id < 1 else 404
    assert response.status_code == expected
