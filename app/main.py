"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app import __version__

app = FastAPI(
    title="DevOps Project - Online Shop API",
    version=__version__,
    description="REST API for DevOps course project",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint.

    Used by Docker healthcheck, monitoring, and load tests
    to verify the service is alive.
    """
    return {"status": "ok", "version": __version__}
