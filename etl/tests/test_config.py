from pathlib import Path

import pytest

from src.config import Settings
from src.domain.errors import ConfigurationError


def test_database_timeouts_use_valid_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ETL_DB_USERNAME", "kp_data_manager_etl")
    monkeypatch.setenv("ETL_IMPORT_STORAGE_ROOT", str(tmp_path))
    monkeypatch.delenv("ETL_DB_CONNECT_TIMEOUT", raising=False)
    monkeypatch.delenv("ETL_DB_READ_TIMEOUT", raising=False)
    monkeypatch.delenv("ETL_DB_WRITE_TIMEOUT", raising=False)

    settings = Settings.from_environment(tmp_path / "missing.env")

    assert settings.db_connect_timeout == 15
    assert settings.db_read_timeout == 600
    assert settings.db_write_timeout == 600


def test_database_timeouts_are_configurable_and_must_be_positive(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ETL_DB_USERNAME", "kp_data_manager_etl")
    monkeypatch.setenv("ETL_IMPORT_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("ETL_DB_CONNECT_TIMEOUT", "17")
    monkeypatch.setenv("ETL_DB_READ_TIMEOUT", "601")
    monkeypatch.setenv("ETL_DB_WRITE_TIMEOUT", "602")

    settings = Settings.from_environment(tmp_path / "missing.env")

    assert settings.db_connect_timeout == 17
    assert settings.db_read_timeout == 601
    assert settings.db_write_timeout == 602

    monkeypatch.setenv("ETL_DB_READ_TIMEOUT", "0")
    with pytest.raises(ConfigurationError, match="ETL_DB_READ_TIMEOUT"):
        Settings.from_environment(tmp_path / "missing.env")


@pytest.mark.parametrize("username", ["root", "JESUS_ADMIN", "kp_data_manager_app"])
def test_runtime_application_accounts_are_rejected(
    monkeypatch,
    tmp_path: Path,
    username: str,
) -> None:
    monkeypatch.setenv("ETL_DB_USERNAME", username)
    monkeypatch.setenv("ETL_IMPORT_STORAGE_ROOT", str(tmp_path))

    with pytest.raises(ConfigurationError, match="usuario ETL independiente"):
        Settings.from_environment(tmp_path / "missing.env")
