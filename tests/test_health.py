"""Tests for the health endpoint and application wiring."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_200(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_health_reports_version_and_uptime(client: TestClient) -> None:
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["version"] == "test"
    assert data["uptime_seconds"] >= 0


def test_catalog_is_seeded_on_startup(client: TestClient) -> None:
    data = client.get("/products").json()
    assert data["total"] == 10
    assert data["items"][0]["title"] == "Wireless Mouse"


def test_each_application_has_its_own_store(settings: Settings) -> None:
    first, second = create_app(settings), create_app(settings)
    with TestClient(first) as client_a, TestClient(second) as client_b:
        client_a.post("/orders", json={"items": [{"product_id": 1, "quantity": 1}]})
        assert client_a.get("/orders").json()["total"] == 1
        assert client_b.get("/orders").json()["total"] == 0
