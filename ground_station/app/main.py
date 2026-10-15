"""
ClimCam Ground Station — FastAPI Application Entry Point
=========================================================
Wires together the router, database lifecycle, logging,
CORS middleware, and global exception handlers.
"""
from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import get_settings
from app.database import connect_db, close_db
from app.routers import telemetry_router

# ─────────────────────────────────────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────────────────────────────────────
settings = get_settings()

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)-8s %(name)-25s %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        }
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "default",
            "stream":    "ext://sys.stdout",
        }
    },
    "root": {
        "handlers": ["console"],
        "level":    settings.log_level.upper(),
    },
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("climcam.main")


# ─────────────────────────────────────────────────────────────────────────────
# Application Lifespan (startup / shutdown hooks)
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages DB connection pool across the application lifetime."""
    logger.info("[STARTING] ClimCam Ground Station starting ...")
    await connect_db()
    logger.info("[READY] Ready to receive ISS telemetry on http://%s:%d", settings.app_host, settings.app_port)
    yield
    logger.info("[SHUTDOWN] Shutting down -- closing DB connection ...")
    await close_db()
    logger.info("[STOPPED] Ground Station stopped.")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="ClimCam Ground Station API",
        description=(
            "REST API for the ISS-mounted ClimCam hyperspectral sensor. "
            "Ingests compressed telemetry JSON, validates with Pydantic, "
            "stores in MongoDB, and surfaces alerts for downstream dashboards."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS (allow dashboard & internal tooling from configured origins) ─
    cors_origins = settings.cors_origins if settings.cors_origins else ["http://localhost:5173", "http://127.0.0.1:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(telemetry_router)

    # ── Global Exception Handlers ─────────────────────────────────────────
    @app.exception_handler(ValidationError)
    async def pydantic_validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        logger.warning("Validation error on %s: %s", request.url, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "body": None},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception on %s: %r", request.url, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error. Please contact the operations team."},
        )

    return app


app = create_app()
