"""FastAPI application factory.

Responsibility split: this module wires the app together. Business logic lives
in `app.geography`, HTTP shape lives in `app.routers`, and configuration lives
in `app.config`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import Settings, get_settings
from app.dependencies import create_geography_service
from app.errors import GeographyError
from app.geography.google_maps import GoogleMapsAdapter
from app.logging_config import configure_logging, redact_tokens
from app.routers import geography, system

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build shared resources once, and release them on shutdown."""
    settings: Settings = app.state.settings
    app.state.geography_service = create_geography_service(settings)
    app.state.google_maps_adapter = GoogleMapsAdapter(
        api_key=settings.google_maps_api_key
    )
    logger.info(
        "Geography providers ready (primary=%s, fallback=%s)",
        getattr(app.state.geography_service.primary, "name", None),
        getattr(app.state.geography_service.fallback, "name", None),
    )
    try:
        yield
    finally:
        for provider in (
            app.state.geography_service.primary,
            app.state.geography_service.fallback,
        ):
            aclose = getattr(provider, "aclose", None)
            if aclose is not None:
                await aclose()


def _error_payload(code: str, detail: str) -> dict:
    return {"error": {"code": code, "detail": detail}}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.secret_values())

    app = FastAPI(
        title="Travel Companion API",
        version=__version__,
        description=(
            "Geography browsing for a travel companion app. "
            "See /docs for the interactive contract."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # --- exception handlers ------------------------------------------------

    @app.exception_handler(GeographyError)
    async def _geography_error(_: Request, exc: GeographyError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_payload(exc.code, redact_tokens(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Normalise FastAPI's validation errors into the same envelope, and do
        # not echo the submitted value back (it could be attacker-controlled).
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        detail = first.get("msg", "Invalid request.")
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "validation_error",
                f"Invalid request parameter '{location}': {detail}",
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log the real cause; return an opaque message. No traceback, no
        # upstream text, nothing that could carry a credential.
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                "internal_error", "An unexpected error occurred."
            ),
        )

    # --- routes ------------------------------------------------------------

    app.include_router(system.router, prefix="/api/v1")
    app.include_router(geography.router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "name": "Travel Companion API",
            "version": __version__,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()
