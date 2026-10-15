"""
Ground Station — Application Settings (Pydantic BaseSettings)
Reads values from environment variables / .env file automatically.
"""
from functools import lru_cache
from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "climcam_db"
    telemetry_collection: str = "telemetry"
    alerts_collection: str = "alerts"

    # Security (Secrets MUST be set via environment / .env in production)
    api_secret_key: str = ""   # Set via API_SECRET_KEY in .env
    sensor_api_key: str = ""   # Set via SENSOR_API_KEY in .env; empty = ingestion disabled (fail-closed)

    # CORS Configuration
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # External Notifications
    slack_webhook_url: str = ""
    sms_alert_enabled: bool = False

    # Alert thresholds
    alert_desertification_warn_pct: float = 28.0
    alert_moisture_critical_ndwi: float = -0.10
    alert_hydration_critical_pct: float = 8.0

    # Server
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    log_level: str = "info"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            # Supports comma-separated strings like "http://localhost:5173,http://localhost:3000"
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton — settings are loaded once at startup."""
    return Settings()

