"""FastAPI application factory and system endpoints."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import APIRouter, FastAPI, Request

from app.config import Settings, get_settings
from app.deps import SettingsDep
from app.models import HealthResponse
from app.routers import orders, products
from app.seed import seed_catalog
from app.store import InMemoryStore

logger = logging.getLogger("app")

system_router = APIRouter(tags=["system"])


@system_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe with version and uptime",
)
def health(request: Request, settings: SettingsDep) -> HealthResponse:
    """Report that the service is alive, its version and uptime."""
    uptime = monotonic() - request.app.state.started_at
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        uptime_seconds=round(uptime, 3),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an application instance owning an isolated in-memory store."""
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        added = seed_catalog(application.state.store, settings)
        logger.info(
            "startup: version=%s, seeded=%s products", settings.app_version, added
        )
        yield
        logger.info("shutdown: in-memory state discarded")

    application = FastAPI(
        title="DevOps Project - Online Shop API",
        version=settings.app_version,
        description="REST API for the DevOps course project: catalog and orders.",
        lifespan=lifespan,
    )
    application.state.store = InMemoryStore()
    application.state.started_at = monotonic()
    # Dependencies must use this instance's settings, not the global cache.
    application.dependency_overrides[get_settings] = lambda: settings
    application.include_router(system_router)
    application.include_router(products.router)
    application.include_router(orders.router)
    return application


app = create_app()
