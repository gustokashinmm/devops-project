"""Shared pytest fixtures.

Every test gets its own application instance and therefore its own store,
so tests never share catalog or order state.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store import InMemoryStore


@pytest.fixture
def settings() -> Settings:
    """Explicit values keep tests independent of the developer's environment."""
    return Settings(
        app_version="test",
        seed_products=10,
        seed_stock=100,
        default_page_limit=20,
        max_page_limit=100,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """A fresh application instance."""
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """TestClient as a context manager: lifespan runs and the catalog is seeded."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def store(app: FastAPI) -> InMemoryStore:
    """The store owned by the application under test."""
    return app.state.store
