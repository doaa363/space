"""
Ground Station — Alert Processing Service
Background task that intercepts incoming telemetry and fires
CRITICAL / WARNING notifications without blocking the HTTP response.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config import get_settings
from app.models import TelemetryInbound

logger = logging.getLogger("climcam.alerts")
settings = get_settings()


async def process_alerts(
    telemetry: TelemetryInbound,
    doc_id: str,
    db: AsyncIOMotorDatabase,
) -> None:
    """
    Background task called after a telemetry document is stored.
    Evaluates alert severity, logs critical events, and persists
    alert records to the dedicated alerts collection.
    """
    alert_docs = []

    # Safe Data Handling: verify telemetry.alerts is not None or empty before looping
    if telemetry.alerts:
        for alert in telemetry.alerts:
            alert_doc = {
                "telemetry_id":  doc_id,
                "sensor_id":     telemetry.sensor_id,
                "severity":      alert.severity,
                "type":          alert.type,
                "message":       alert.message,
                "recommendation": alert.recommendation,
                "created_at":    datetime.now(timezone.utc),
                "biophysical_context": {
                    "mean_ndwi": telemetry.biophysical.mean_ndwi,
                    "mean_ndre": telemetry.biophysical.mean_ndre,
                    "desertification_pct": telemetry.distribution.desertification_pct,
                    "hydration_pct":       telemetry.distribution.hydration_pct,
                },
            }
            alert_docs.append(alert_doc)

            # ── Critical path: elevated logging + threshold evaluation ──────────
            if alert.severity == "CRITICAL":
                logger.critical(
                    "🔴 CRITICAL ALERT | sensor=%s | type=%s | ndwi=%.3f | hydration=%.1f%% | msg=%s",
                    telemetry.sensor_id,
                    alert.type,
                    telemetry.biophysical.mean_ndwi,
                    telemetry.distribution.hydration_pct,
                    alert.message,
                )
                await _dispatch_critical_notification(alert_doc)

            elif alert.severity == "WARNING":
                logger.warning(
                    "⚠️  WARNING | sensor=%s | type=%s | desertification=%.1f%% | msg=%s",
                    telemetry.sensor_id,
                    alert.type,
                    telemetry.distribution.desertification_pct,
                    alert.message,
                )

            else:
                logger.info(
                    "ℹ️  INFO | sensor=%s | %s",
                    telemetry.sensor_id,
                    alert.message,
                )

    # Bulk-insert all alert records
    if alert_docs:
        col = db[settings.alerts_collection]
        await col.insert_many(alert_docs)
        logger.debug("Inserted %d alert record(s) to DB", len(alert_docs))


async def send_slack_webhook(alert_doc: dict) -> None:
    """
    Dispatches a formatted alert payload to Slack webhook if configured.
    """
    webhook_url = settings.slack_webhook_url
    if not webhook_url:
        logger.debug("Slack webhook URL not configured; skipping external notification.")
        return

    payload = {
        "text": f"🚨 *CLIMCAM CRITICAL ALERT* [{alert_doc['sensor_id']}]",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*⛔ Sensor:* `{alert_doc['sensor_id']}`\n"
                        f"*Type:* *{alert_doc['type']}*\n"
                        f"*Message:* {alert_doc['message']}\n"
                        f"*NDWI:* `{alert_doc['biophysical_context']['mean_ndwi']:.4f}` | "
                        f"*Hydration:* `{alert_doc['biophysical_context']['hydration_pct']:.1f}%`\n"
                        f"*Time:* {alert_doc['created_at'].isoformat()}"
                    ),
                },
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code == 200:
                logger.info("Successfully dispatched critical alert to Slack webhook.")
            else:
                logger.warning("Slack webhook returned HTTP %d: %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.error("Failed to dispatch Slack webhook alert: %s", exc)


async def send_sms_alert(alert_doc: dict) -> None:
    """
    Dispatches SMS alert to operations roster if enabled.
    Note: SMS provider integration is not configured — logs clear warning.
    """
    if not settings.sms_alert_enabled:
        logger.debug("SMS alert dispatch is disabled; skipping.")
        return

    logger.warning(
        "SMS alert triggered for [%s] %s, but SMS gateway provider integration is not implemented.",
        alert_doc["type"],
        alert_doc["message"],
    )


async def _dispatch_critical_notification(alert_doc: dict) -> None:
    """
    Real-world critical notification dispatch.
    Emits prominent console banner, triggers Slack webhook if configured,
    and forwards to emergency SMS roster if enabled.
    """
    banner = (
        "\n" + "!" * 78 + "\n"
        f"  ⛔  CLIMCAM CRITICAL ALERT RECEIVED\n"
        f"  Sensor  : {alert_doc['sensor_id']}\n"
        f"  Type    : {alert_doc['type']}\n"
        f"  Message : {alert_doc['message']}\n"
        f"  NDWI    : {alert_doc['biophysical_context']['mean_ndwi']:.4f}\n"
        f"  Hydration: {alert_doc['biophysical_context']['hydration_pct']:.1f}%\n"
        f"  Time    : {alert_doc['created_at'].isoformat()}\n"
        + "!" * 78
    )
    logger.critical(banner)
    await send_slack_webhook(alert_doc)
    await send_sms_alert(alert_doc)
