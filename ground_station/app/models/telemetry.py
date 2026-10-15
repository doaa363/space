"""
Ground Station — Pydantic Data Models (Schema)
Defines the strict validation contract between ISS sensor and ground station.
All models use Pydantic v2 syntax with Field constraints.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Sub-models
# ─────────────────────────────────────────────────────────────────────────────

class GeoPoint(BaseModel):
    """GeoJSON Point — enables MongoDB 2dsphere geospatial queries."""
    type: Literal["Point"] = "Point"
    coordinates: list[float] = Field(
        ...,
        description="[longitude, latitude] per GeoJSON spec",
        min_length=2,
        max_length=2,
    )

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: list[float]) -> list[float]:
        lon, lat = v
        if not (-180 <= lon <= 180):
            raise ValueError(f"Longitude {lon} out of range [-180, 180]")
        if not (-90 <= lat <= 90):
            raise ValueError(f"Latitude {lat} out of range [-90, 90]")
        return v


class SceneGeoreference(BaseModel):
    center_lat: float = Field(..., ge=-90, le=90)
    center_lon: float = Field(..., ge=-180, le=180)
    pixel_resolution_m: float = Field(..., gt=0)


class ClassificationDistribution(BaseModel):
    """Percentage breakdown of the 4 ClimCam semantic classes (must sum ~100%)."""
    vegetation_pct:      float = Field(..., ge=0, le=100, alias="Vegetation")
    hydration_pct:       float = Field(..., ge=0, le=100, alias="Hydration")
    desertification_pct: float = Field(..., ge=0, le=100, alias="Desertification")
    urban_pct:           float = Field(..., ge=0, le=100, alias="Urban")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def check_sum(self) -> ClassificationDistribution:
        total = self.vegetation_pct + self.hydration_pct + self.desertification_pct + self.urban_pct
        if not (85.0 <= total <= 115.0):
            raise ValueError(f"Class percentages sum to {total:.1f}% — expected ~100%")
        return self


class BiophysicalIndicators(BaseModel):
    mean_ndvi: float = Field(..., ge=-1, le=1)
    mean_ndwi: float = Field(..., ge=-1, le=1)
    mean_ndre: float = Field(..., ge=-1, le=1)


class Alert(BaseModel):
    severity:       Literal["INFO", "WARNING", "CRITICAL"]
    type:           str = Field(..., max_length=80)
    message:        str = Field(..., max_length=500)
    recommendation: str | None = None


class BandwidthInfo(BaseModel):
    raw_cube_mb:          float = Field(..., gt=0)
    payload_kb:           float = Field(..., gt=0)
    compression_ratio:    float = Field(..., gt=0)
    bandwidth_saving_pct: float = Field(alias="bandwidth_saving_%", default=0.0, ge=0, le=100)

    model_config = {"populate_by_name": True}


# ─────────────────────────────────────────────────────────────────────────────
# Primary Inbound Telemetry Payload (POST body)
# ─────────────────────────────────────────────────────────────────────────────

class TelemetryInbound(BaseModel):
    """
    Strict schema for JSON packets arriving from the ISS ClimCam unit.
    Mirrors the output of src/stage3_edge_inference.py SemanticEncoder.
    """
    mission:      str = Field(..., max_length=120)
    sensor_id:    str = Field(..., max_length=60)
    timestamp:    datetime

    # Optional scene geographic reference
    scene_georeference: SceneGeoreference | None = None

    distribution:   ClassificationDistribution
    biophysical:    BiophysicalIndicators
    alerts:         list[Alert] = Field(default_factory=list)
    bandwidth:      BandwidthInfo | None = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError("timestamp must be ISO-8601 string or datetime")
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ─────────────────────────────────────────────────────────────────────────────
# Database Document (stored internally — never exposed raw)
# ─────────────────────────────────────────────────────────────────────────────

class TelemetryDocument(BaseModel):
    """Shape of a document as it is persisted in MongoDB."""
    sensor_id:       str
    mission:         str
    captured_at:     datetime          # original ISS timestamp
    received_at:     datetime          # server receipt timestamp (UTC)
    distribution:    dict[str, float]
    biophysical:     dict[str, float]
    alerts:          list[dict]
    bandwidth:       dict | None
    has_critical:    bool              # pre-computed flag for fast filtering
    scene_location:  dict | None       # GeoJSON Point for 2dsphere queries


# ─────────────────────────────────────────────────────────────────────────────
# API Response Models
# ─────────────────────────────────────────────────────────────────────────────

class TelemetryResponse(BaseModel):
    """Outbound representation of a stored telemetry record."""
    id:           str = Field(alias="_id")
    sensor_id:    str
    mission:      str
    captured_at:  datetime
    received_at:  datetime
    distribution: dict[str, float]
    biophysical:  dict[str, float]
    alerts:       list[dict]
    has_critical: bool

    model_config = {"populate_by_name": True}


class TelemetryAck(BaseModel):
    """Minimal acknowledgement returned after a successful ingest."""
    status:      Literal["accepted"] = "accepted"
    document_id: str
    has_critical: bool
    alerts_count: int
    message:     str


class PaginatedTelemetry(BaseModel):
    total:   int
    page:    int
    limit:   int
    results: list[TelemetryResponse]
