from pathlib import Path

from lotto_lab.config import AppSettings


def test_database_url_uses_configured_data_directory(tmp_path: Path) -> None:
    settings = AppSettings(data_dir=tmp_path)

    assert settings.database_path == tmp_path / "lotto_lab.sqlite3"
    assert settings.database_url.startswith("sqlite:///")


def test_ensure_directories_creates_data_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "data"

    AppSettings(target).ensure_directories()

    assert target.is_dir()

