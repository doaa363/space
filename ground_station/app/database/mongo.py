"""
Ground Station — MongoDB Async Client (Motor)
Manages the database lifecycle: connect on startup, close on shutdown.
Uses Motor (async MongoDB driver) with connection pooling for production throughput.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, GEOSPHERE
from pymongo.errors import ConnectionFailure
import logging

from app.config import get_settings

logger = logging.getLogger("climcam.database")

# Module-level client (one connection pool per process)
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """
    Opens the Motor async client and verifies the connection.
    Creates indexes on first run (idempotent).
    Called from FastAPI lifespan context.
    """
    global _client, _db
    settings = get_settings()

    logger.info("Connecting to MongoDB at %s …", settings.mongodb_url.split("@")[-1])
    _client = AsyncIOMotorClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=5_000,
        maxPoolSize=20,
        minPoolSize=2,
    )

    # Verify connection is reachable
    try:
        await _client.admin.command("ping")
    except ConnectionFailure as exc:
        logger.error("MongoDB connection failed: %s", exc)
        raise

    _db = _client[settings.database_name]
    logger.info("Connected to database '%s'", settings.database_name)

    await _create_indexes()


async def close_db() -> None:
    """Gracefully closes the Motor client. Called on application shutdown."""
    global _client
    if _client is not None:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    """Dependency-injectable getter — returns the active database handle."""
    if _db is None:
        raise RuntimeError("Database not initialised. Call connect_db() first.")
    return _db


async def _create_indexes() -> None:
    """
    Creates performance and geospatial indexes.
    Idempotent — safe to call on every startup.
    """
    settings = get_settings()
    tel_col = _db[settings.telemetry_collection]
    alr_col = _db[settings.alerts_collection]

    # Telemetry indexes
    await tel_col.create_index([("received_at", ASCENDING)],  name="idx_received_at")
    await tel_col.create_index([("sensor_id",   ASCENDING)],  name="idx_sensor_id")
    await tel_col.create_index([("has_critical", ASCENDING)], name="idx_has_critical")
    # 2dsphere index for geospatial queries on scene centre coordinate
    await tel_col.create_index([("scene_location", GEOSPHERE)], name="idx_scene_geo")

    # Alerts index
    await alr_col.create_index([("severity",   ASCENDING)], name="idx_alert_severity")
    await alr_col.create_index([("created_at", ASCENDING)], name="idx_alert_time")

    logger.info("MongoDB indexes verified / created.")
