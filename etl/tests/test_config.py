from pathlib import Path

import pytest

from src.config import Settings
from src.domain.errors import ConfigurationError


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
