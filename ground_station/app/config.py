"""
Ground Station — Application Settings (Pydantic BaseSettings)
Reads values from environment variables / .env file automatically.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "climcam_db"
    telemetry_collection: str = "telemetry"
    alerts_collection: str = "alerts"

    # Security
    api_secret_key: str = "dev-insecure-key"
    sensor_api_key: str = "REDACTED_HISTORICAL_TOKEN"

    # Alert thresholds
    alert_desertification_warn_pct: float = 28.0
    alert_moisture_critical_ndwi: float = -0.10
    alert_hydration_critical_pct: float = 8.0

    # Server
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    log_level: str = "info"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton — settings are loaded once at startup."""
    return Settings()
