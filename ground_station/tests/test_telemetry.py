"""
Tests for Ground Station Telemetry Retrieval & Health Probes
"""
from bson import ObjectId


def test_health_check_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "timestamp_utc" in data


def test_list_telemetry(client):
    res = client.get("/api/telemetry?page=1&limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert data["total"] >= 1
    assert data["page"] == 1
    assert data["limit"] == 10


def test_get_telemetry_valid_id(client):
    valid_id = str(ObjectId())
    res = client.get(f"/api/telemetry/{valid_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["_id"] == valid_id
    assert data["sensor_id"] == "CLIMCAM-ISS-01"


def test_get_telemetry_invalid_object_id(client):
    res = client.get("/api/telemetry/not-a-valid-id")
    assert res.status_code == 422
    assert "not a valid ObjectId" in res.json()["detail"]
