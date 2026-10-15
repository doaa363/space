"""
Ground Station Test Configuration & Fixtures
"""
import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

# Ensure ground_station is in sys.path
ground_station_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ground_station_dir not in sys.path:
    sys.path.insert(0, ground_station_dir)

from app.config import Settings, get_settings
from app.database import get_db
from app.main import app


class MockAsyncCursor:
    """Simulates Motor AsyncIOMotorCursor for find queries."""
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *args, **kwargs):
        return self

    def skip(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def __aiter__(self):
        self._iter = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def test_settings():
    return Settings(
        mongodb_url="mongodb://localhost:27017",
        database_name="climcam_test_db",
        telemetry_collection="telemetry",
        alerts_collection="alerts",
        api_secret_key="TEST-API-SECRET-KEY",
        sensor_api_key="TEST-SENSOR-KEY-12345",
        cors_origins=["http://localhost:5173", "http://localhost:3000"],
        slack_webhook_url="",
        sms_alert_enabled=False,
    )


@pytest.fixture
def mock_db():
    db = MagicMock()
    telemetry_col = MagicMock()
    alerts_col = MagicMock()

    # Async insert_one mock
    async def mock_insert_one(doc):
        res = MagicMock()
        res.inserted_id = ObjectId()
        return res

    # Async count_documents mock
    async def mock_count_documents(query=None):
        return 1

    # Async find mock
    def mock_find(query=None):
        sample_doc = {
            "_id": ObjectId(),
            "sensor_id": "CLIMCAM-ISS-01",
            "mission": "ISS-EXP-71-AFRICA",
            "captured_at": datetime.now(timezone.utc),
            "received_at": datetime.now(timezone.utc),
            "distribution": {
                "Vegetation": 50.0,
                "Hydration": 25.0,
                "Desertification": 15.0,
                "Urban": 10.0,
            },
            "biophysical": {
                "mean_ndvi": 0.65,
                "mean_ndwi": 0.20,
                "mean_ndre": 0.40,
            },
            "alerts": [],
            "bandwidth": None,
            "has_critical": False,
            "scene_location": {"type": "Point", "coordinates": [35.28, 0.51]},
        }
        return MockAsyncCursor([sample_doc])

    async def mock_find_one(query):
        if "_id" in query and isinstance(query["_id"], ObjectId):
            return {
                "_id": query["_id"],
                "sensor_id": "CLIMCAM-ISS-01",
                "mission": "ISS-EXP-71-AFRICA",
                "captured_at": datetime.now(timezone.utc),
                "received_at": datetime.now(timezone.utc),
                "distribution": {
                    "Vegetation": 50.0,
                    "Hydration": 25.0,
                    "Desertification": 15.0,
                    "Urban": 10.0,
                },
                "biophysical": {
                    "mean_ndvi": 0.65,
                    "mean_ndwi": 0.20,
                    "mean_ndre": 0.40,
                },
                "alerts": [],
                "bandwidth": None,
                "has_critical": False,
                "scene_location": {"type": "Point", "coordinates": [35.28, 0.51]},
            }
        return None

    async def mock_insert_many(docs):
        res = MagicMock()
        res.inserted_ids = [ObjectId() for _ in docs]
        return res

    async def mock_command(cmd):
        if cmd == "ping":
            return {"ok": 1}
        return {}

    telemetry_col.insert_one = AsyncMock(side_effect=mock_insert_one)
    telemetry_col.count_documents = AsyncMock(side_effect=mock_count_documents)
    telemetry_col.find = MagicMock(side_effect=mock_find)
    telemetry_col.find_one = AsyncMock(side_effect=mock_find_one)
    alerts_col.insert_many = AsyncMock(side_effect=mock_insert_many)

    db.__getitem__.side_effect = lambda key: telemetry_col if key == "telemetry" else alerts_col
    db.command = AsyncMock(side_effect=mock_command)
    return db


@pytest.fixture
def client(mock_db, test_settings):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def valid_telemetry_payload():
    return {
        "mission": "ISS-EXP-71-AFRICA",
        "sensor_id": "CLIMCAM-ISS-01",
        "timestamp": "2026-10-15T00:30:00Z",
        "scene_georeference": {
            "center_lat": 0.514,
            "center_lon": 35.283,
            "pixel_resolution_m": 30.0,
        },
        "distribution": {
            "Vegetation": 54.0,
            "Hydration": 26.0,
            "Desertification": 12.0,
            "Urban": 8.0,
        },
        "biophysical": {
            "mean_ndvi": 0.684,
            "mean_ndwi": 0.215,
            "mean_ndre": 0.432,
        },
        "alerts": [
            {
                "severity": "INFO",
                "type": "OPTIMAL_CANOPY",
                "message": "Canopy health is robust.",
                "recommendation": "Maintain scheduled monitoring.",
            }
        ],
        "bandwidth": {
            "raw_cube_mb": 485.2,
            "payload_kb": 2.8,
            "compression_ratio": 177445.0,
            "bandwidth_saving_%": 99.99,
        },
    }
