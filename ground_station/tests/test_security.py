"""
Unit and Integration Tests for Ground Station Security & Authentication
"""
import pytest
from fastapi import HTTPException
from app.config import Settings
from app.routers.telemetry import verify_sensor_key


def test_verify_sensor_key_success():
    settings = Settings(sensor_api_key="CORRECT-KEY-XYZ")
    assert verify_sensor_key("CORRECT-KEY-XYZ", current_settings=settings) == "CORRECT-KEY-XYZ"


def test_verify_sensor_key_missing_header():
    settings = Settings(sensor_api_key="CORRECT-KEY-XYZ")
    with pytest.raises(HTTPException) as exc_info:
        verify_sensor_key(None, current_settings=settings)
    assert exc_info.value.status_code == 401
    assert "Invalid or missing" in exc_info.value.detail


def test_verify_sensor_key_invalid_header():
    settings = Settings(sensor_api_key="CORRECT-KEY-XYZ")
    with pytest.raises(HTTPException) as exc_info:
        verify_sensor_key("WRONG-KEY", current_settings=settings)
    assert exc_info.value.status_code == 401
    assert "Invalid or missing" in exc_info.value.detail


def test_verify_sensor_key_fail_closed_when_unconfigured():
    """
    CRITICAL: When the server has no sensor_api_key configured (empty string),
    all ingestion attempts MUST be rejected with HTTP 503 instead of passing or crashing.
    """
    settings = Settings(sensor_api_key="")
    with pytest.raises(HTTPException) as exc_info:
        verify_sensor_key("ANY-KEY", current_settings=settings)
    assert exc_info.value.status_code == 503
    assert "not configured" in exc_info.value.detail


def test_api_ingest_endpoint_fail_closed(client, valid_telemetry_payload):
    """
    Simulates request when sensor_api_key is unconfigured.
    """
    unconfigured_settings = Settings(sensor_api_key="")
    from app.config import get_settings
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: unconfigured_settings

    res = client.post(
        "/api/telemetry",
        json=valid_telemetry_payload,
        headers={"X-Sensor-Key": "SOME-KEY"},
    )
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"]


def test_api_ingest_endpoint_missing_key(client, valid_telemetry_payload):
    res = client.post(
        "/api/telemetry",
        json=valid_telemetry_payload,
    )
    assert res.status_code == 401


def test_api_ingest_endpoint_valid_key(client, valid_telemetry_payload, test_settings):
    res = client.post(
        "/api/telemetry",
        json=valid_telemetry_payload,
        headers={"X-Sensor-Key": test_settings.sensor_api_key},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "accepted"
    assert "document_id" in data


def test_cors_settings_parsing():
    settings_comma = Settings(cors_origins="https://dashboard.climcam.space, http://localhost:5173")
    assert settings_comma.cors_origins == ["https://dashboard.climcam.space", "http://localhost:5173"]

    settings_list = Settings(cors_origins=["http://localhost:3000"])
    assert settings_list.cors_origins == ["http://localhost:3000"]
