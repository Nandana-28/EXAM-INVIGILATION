from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ProctorX"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/proctorx"

    model_weights: str = "yolo26n.pt"
    fallback_model_weights: str = "yolo11n.pt"
    device: str = "cpu"

    detection_confidence: float = Field(default=0.45, ge=0.0, le=1.0)
    alert_confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    tracker_high_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    tracker_low_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    tracker_match_threshold: float = Field(default=0.38, ge=0.0, le=1.0)
    tracker_max_missing_frames: int = Field(default=360, ge=1)

    upload_dir: Path = Path("backend/uploads")
    run_dir: Path = Path("backend/runs")
    frame_width: int = Field(default=960, ge=320)
    frame_skip: int = Field(default=0, ge=0)
    live_camera_index: int = Field(default=0, ge=0)
    alert_cooldown_seconds: int = Field(default=8, ge=0)
    max_recent_alerts: int = Field(default=30, ge=1)

    frontend_dir: Path = Path("frontend")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def person_names(self) -> set[str]:
        return {"person"}

    @property
    def phone_names(self) -> set[str]:
        return {"phone", "cell phone", "mobile phone", "smartphone"}

    @property
    def paper_names(self) -> set[str]:
        return {"paper", "document", "answer sheet", "sheet", "book", "notebook"}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.run_dir.mkdir(parents=True, exist_ok=True)
    return settings
