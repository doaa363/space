"""
Ground Station — Telemetry Router
POST /api/telemetry  — Ingest a single ISS ClimCam telemetry packet.
GET  /api/telemetry  — Retrieve historical records with filtering & pagination.
GET  /api/telemetry/{id} — Retrieve one record by MongoDB ObjectId.
GET  /api/health     — Liveness / readiness probe.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Header
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.database import get_db
from app.models import (
    TelemetryInbound,
    TelemetryAck,
    TelemetryResponse,
    PaginatedTelemetry,
)
from app.services.alert_service import process_alerts

logger = logging.getLogger("climcam.router")
router = APIRouter(prefix="/api", tags=["Telemetry"])
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Security Dependency
# ─────────────────────────────────────────────────────────────────────────────

def verify_sensor_key(x_sensor_key: Annotated[str | None, Header()] = None) -> str:
    """
    Validates the X-Sensor-Key header sent by the ISS unit.
    Raises HTTP 401 if missing or invalid.
    """
    if x_sensor_key is None or x_sensor_key != settings.sensor_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Sensor-Key header.")
    return x_sensor_key


# ─────────────────────────────────────────────────────────────────────────────
# Helper: document → response model
# ─────────────────────────────────────────────────────────────────────────────

def _doc_to_response(doc: dict) -> dict:
    """Converts a raw MongoDB document to a JSON-serialisable dict."""
    doc["_id"] = str(doc["_id"])
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/telemetry — Ingest
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/telemetry",
    response_model=TelemetryAck,
    status_code=201,
    summary="Ingest ISS telemetry packet",
    description=(
        "Accepts a validated JSON telemetry payload from the ClimCam ISS sensor. "
        "Stores it in MongoDB and schedules background alert processing. "
        "Requires **X-Sensor-Key** header authentication."
    ),
)
async def ingest_telemetry(
    payload: TelemetryInbound,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    _key: Annotated[str, Depends(verify_sensor_key)],
) -> TelemetryAck:
    """Store one telemetry packet and queue background alert processing."""

    has_critical = any(a.severity == "CRITICAL" for a in payload.alerts) if payload.alerts else False
    received_at  = datetime.now(timezone.utc)

    # Build GeoJSON Point from scene georeference (if provided)
    geo_point = None
    if payload.scene_georeference:
        geo_point = {
            "type": "Point",
            "coordinates": [
                payload.scene_georeference.center_lon,
                payload.scene_georeference.center_lat,
            ],
        }

    # Flatten models to plain dicts for MongoDB storage (safe handling for optional/empty collections)
    alerts_serialized = [a.model_dump() for a in payload.alerts] if payload.alerts else []

    document = {
        "sensor_id":      payload.sensor_id,
        "mission":        payload.mission,
        "captured_at":    payload.timestamp,
        "received_at":    received_at,
        "distribution":   payload.distribution.model_dump(by_alias=False),
        "biophysical":    payload.biophysical.model_dump(),
        "alerts":         alerts_serialized,
        "bandwidth":      payload.bandwidth.model_dump(by_alias=False) if payload.bandwidth else None,
        "has_critical":   has_critical,
        "scene_location": geo_point,
    }

    col = db[settings.telemetry_collection]
    result = await col.insert_one(document)
    doc_id = str(result.inserted_id)

    logger.info(
        "Telemetry stored | id=%s | sensor=%s | critical=%s",
        doc_id, payload.sensor_id, has_critical
    )

    # Fire alert processing in background (non-blocking)
    background_tasks.add_task(process_alerts, payload, doc_id, db)

    alerts_count = len(payload.alerts) if payload.alerts else 0

    return TelemetryAck(
        status="accepted",
        document_id=doc_id,
        has_critical=has_critical,
        alerts_count=alerts_count,
        message=f"Telemetry ingested. {'⚠️ CRITICAL alerts queued.' if has_critical else 'No critical alerts.'}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/telemetry — List with filtering & pagination
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/telemetry",
    response_model=PaginatedTelemetry,
    summary="List historical telemetry records",
)
async def list_telemetry(
    db:           Annotated[AsyncIOMotorDatabase, Depends(get_db)],
    sensor_id:    str | None = Query(None,  description="Filter by sensor ID"),
    status:       Literal["all", "critical", "normal"] = Query("all", description="Filter by alert status"),
    date_from:    datetime | None = Query(None, description="ISO-8601 UTC start date"),
    date_to:      datetime | None = Query(None, description="ISO-8601 UTC end date"),
    page:         int = Query(1, ge=1),
    limit:        int = Query(20, ge=1, le=100),
) -> PaginatedTelemetry:
    """
    Returns paginated telemetry records with optional filters:
    - **sensor_id**: exact match
    - **status**: `all` | `critical` | `normal`
    - **date_from / date_to**: ISO-8601 UTC datetime range on `received_at`
    """
    query: dict = {}

    if sensor_id:
        query["sensor_id"] = sensor_id

    if status == "critical":
        query["has_critical"] = True
    elif status == "normal":
        query["has_critical"] = False

    if date_from or date_to:
        date_filter: dict = {}
        if date_from:
            date_filter["$gte"] = date_from.replace(tzinfo=timezone.utc) if date_from.tzinfo is None else date_from
        if date_to:
            date_filter["$lte"] = date_to.replace(tzinfo=timezone.utc) if date_to.tzinfo is None else date_to
        if date_filter:
            query["received_at"] = date_filter

    col   = db[settings.telemetry_collection]
    total = await col.count_documents(query)
    skip  = (page - 1) * limit

    cursor = col.find(query).sort("received_at", -1).skip(skip).limit(limit)
    docs   = [_doc_to_response(d) async for d in cursor]

    return PaginatedTelemetry(total=total, page=page, limit=limit, results=docs)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/telemetry/{id} — Single record
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/telemetry/{record_id}",
    response_model=TelemetryResponse,
    summary="Retrieve single telemetry record by ID",
)
async def get_telemetry(
    record_id: str,
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> TelemetryResponse:
    try:
        oid = ObjectId(record_id)
    except InvalidId:
        raise HTTPException(status_code=422, detail=f"'{record_id}' is not a valid ObjectId.")

    col = db[settings.telemetry_collection]
    doc = await col.find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Telemetry record '{record_id}' not found.")

    return _doc_to_response(doc)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/health — Liveness probe
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health", summary="Liveness & readiness probe", tags=["System"])
async def health_check(db: Annotated[AsyncIOMotorDatabase, Depends(get_db)]) -> dict:
    """Used by Docker, Kubernetes, and AWS ALB health checks."""
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        db_status = "unreachable"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "service": "ClimCam Ground Station API",
        "database": db_status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
