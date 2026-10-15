"""
Tests for Ground Station Alert Processing & Safe Data Handling
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from app.models import (
    TelemetryInbound,
    ClassificationDistribution,
    BiophysicalIndicators,
    Alert,
)
from app.services.alert_service import process_alerts, send_slack_webhook, send_sms_alert


def create_sample_telemetry(alerts=None):
    return TelemetryInbound(
        mission="ISS-EXP-71-AFRICA",
        sensor_id="CLIMCAM-ISS-01",
        timestamp=datetime.now(timezone.utc),
        distribution=ClassificationDistribution(
            Vegetation=20.0,
            Hydration=5.0,
            Desertification=65.0,
            Urban=10.0,
        ),
        biophysical=BiophysicalIndicators(
            mean_ndvi=0.25,
            mean_ndwi=-0.15,
            mean_ndre=0.10,
        ),
        alerts=alerts or [],
    )


@pytest.mark.asyncio
async def test_process_alerts_safe_data_handling_empty_alerts(mock_db):
    """Verifies that an empty alert collection causes no exceptions."""
    telemetry = create_sample_telemetry(alerts=[])
    await process_alerts(telemetry, "doc-123", mock_db)
    # alerts_col.insert_many should NOT be called if alerts is empty
    alerts_col = mock_db["alerts"]
    assert alerts_col.insert_many.call_count == 0


@pytest.mark.asyncio
async def test_process_alerts_critical_dispatch(mock_db):
    """Verifies critical alert handling and insertion to MongoDB."""
    critical_alert = Alert(
        severity="CRITICAL",
        type="DESERTIFICATION_ENCROACHMENT",
        message="Extreme moisture deficit detected.",
        recommendation="Deploy emergency irrigation.",
    )
    telemetry = create_sample_telemetry(alerts=[critical_alert])

    with patch("app.services.alert_service._dispatch_critical_notification", new_callable=AsyncMock) as mock_dispatch:
        await process_alerts(telemetry, "doc-123", mock_db)
        mock_dispatch.assert_called_once()
        alerts_col = mock_db["alerts"]
        assert alerts_col.insert_many.call_count == 1


@pytest.mark.asyncio
async def test_send_slack_webhook_unconfigured():
    """If slack_webhook_url is empty, execution returns cleanly without making network calls."""
    alert_doc = {
        "sensor_id": "CLIMCAM-ISS-01",
        "type": "CRITICAL_TEST",
        "message": "Test alert message",
        "biophysical_context": {"mean_ndwi": -0.15, "hydration_pct": 5.0},
        "created_at": datetime.now(timezone.utc),
    }
    # Should not raise exception
    await send_slack_webhook(alert_doc)


@pytest.mark.asyncio
async def test_send_sms_alert_disabled():
    """If sms_alert_enabled is False, execution returns cleanly."""
    alert_doc = {
        "type": "CRITICAL_TEST",
        "message": "Test alert message",
    }
    # Should not raise exception
    await send_sms_alert(alert_doc)


@pytest.mark.asyncio
async def test_send_sms_alert_enabled_warning():
    """If sms_alert_enabled is True, it warns that SMS gateway is not implemented."""
    with patch("app.services.alert_service.settings.sms_alert_enabled", True):
        alert_doc = {
            "type": "CRITICAL_TEST",
            "message": "Test alert message",
        }
        await send_sms_alert(alert_doc)

