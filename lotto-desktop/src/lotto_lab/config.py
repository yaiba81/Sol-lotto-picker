"""Application configuration with environment-variable overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "Lotto Lab"
APP_ORGANIZATION = "Lotto Lab"
DATA_DIR_ENV = "LOTTO_LAB_DATA_DIR"


def default_data_dir() -> Path:
    """Return the platform-appropriate writable directory for local app data."""
    configured = os.getenv(DATA_DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "LottoLab"
    return Path.home() / ".lotto-lab"


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Immutable runtime settings supplied at the application's composition root."""

    data_dir: Path

    @classmethod
    def load(cls) -> "AppSettings":
        return cls(data_dir=default_data_dir())

    @property
    def database_path(self) -> Path:
        return self.data_dir / "lotto_lab.sqlite3"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

