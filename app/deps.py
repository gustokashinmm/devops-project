"""FastAPI dependencies.

The store lives in app.state, so every application instance (including each
test instance) owns its own isolated data.
"""

from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.store import InMemoryStore


def get_store(request: Request) -> InMemoryStore:
    """Return the store bound to this application instance."""
    store: InMemoryStore = request.app.state.store
    return store


StoreDep = Annotated[InMemoryStore, Depends(get_store)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
