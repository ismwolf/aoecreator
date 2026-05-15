"""FastAPI app factory + health endpoints.

Module-level ``app = create_app()`` so ``uvicorn aeogen.main:app`` works
out of the box. Tests construct fresh instances via ``create_app()``.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI

from aeogen import __version__
from aeogen.settings import get_settings

_STARTUP_TIME = datetime.now(UTC)


def create_app() -> FastAPI:
    """Construct a fresh FastAPI application instance.

    Factory pattern enables test isolation — each test can build its own
    app without the module-level singleton leaking state.
    """
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version or __version__,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )

    @app.get("/health/live", tags=["health"])
    async def health_live() -> dict[str, Any]:
        """Liveness probe — process is up and the event loop is responsive."""
        return {
            "status": "alive",
            "version": settings.app_version or __version__,
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": (datetime.now(UTC) - _STARTUP_TIME).total_seconds(),
        }

    @app.get("/health/ready", tags=["health"])
    async def health_ready() -> dict[str, Any]:
        """Readiness probe — all required dependencies are reachable.

        Scaffold version: no deps yet, so this always reports ready with
        an empty checks map. A.T7+ will add DB + Redis checks.
        """
        return {
            "status": "ready",
            "version": settings.app_version or __version__,
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": {},
        }

    return app


app = create_app()
