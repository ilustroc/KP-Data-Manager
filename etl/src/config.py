from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .domain.errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def _boolean(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} debe ser true o false.")


def _positive_integer(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exception:
        raise ConfigurationError(f"{name} debe ser un entero positivo.") from exception
    if value < 1:
        raise ConfigurationError(f"{name} debe ser un entero positivo.")
    return value


def _database_identifier(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ConfigurationError(f"{name} contiene un identificador MySQL inválido.")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    db_host: str
    db_port: int
    db_username: str
    db_password: str
    db_connect_timeout: int
    db_read_timeout: int
    db_write_timeout: int
    control_database: str
    bronze_database: str
    silver_database: str
    gold_database: str
    storage_root: Path
    insert_batch_size: int
    progress_update_every: int
    allow_zero_amount: bool
    error_value_max_length: int
    log_level: str

    @classmethod
    def from_environment(cls, env_file: Path | None = None) -> Settings:
        load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)

        username = os.getenv("ETL_DB_USERNAME", "").strip()
        if not username:
            raise ConfigurationError("ETL_DB_USERNAME es obligatorio.")
        if username.lower() in {"root", "jesus_admin", "kp_data_manager_app"}:
            raise ConfigurationError("ETL_DB_USERNAME debe ser un usuario ETL independiente.")

        storage_value = os.getenv(
            "ETL_IMPORT_STORAGE_ROOT",
            str(REPOSITORY_ROOT / "storage" / "app" / "private" / "imports"),
        )
        storage_root = Path(storage_value)
        if not storage_root.is_absolute():
            storage_root = (PROJECT_ROOT / storage_root).resolve()

        return cls(
            db_host=os.getenv("ETL_DB_HOST", "127.0.0.1").strip(),
            db_port=_positive_integer("ETL_DB_PORT", 3306),
            db_username=username,
            db_password=os.getenv("ETL_DB_PASSWORD", ""),
            db_connect_timeout=_positive_integer("ETL_DB_CONNECT_TIMEOUT", 15),
            db_read_timeout=_positive_integer("ETL_DB_READ_TIMEOUT", 600),
            db_write_timeout=_positive_integer("ETL_DB_WRITE_TIMEOUT", 600),
            control_database=_database_identifier("ETL_CONTROL_DATABASE", "kp_control"),
            bronze_database=_database_identifier("ETL_BRONZE_DATABASE", "kp_bronze"),
            silver_database=_database_identifier("ETL_SILVER_DATABASE", "kp_silver"),
            gold_database=_database_identifier("ETL_GOLD_DATABASE", "kp_gold"),
            storage_root=storage_root.resolve(),
            insert_batch_size=_positive_integer("ETL_INSERT_BATCH_SIZE", 5000),
            progress_update_every=_positive_integer("ETL_PROGRESS_UPDATE_EVERY", 5000),
            allow_zero_amount=_boolean("ETL_ALLOW_ZERO_AMOUNT", True),
            error_value_max_length=_positive_integer("ETL_ERROR_VALUE_MAX_LENGTH", 500),
            log_level=os.getenv("ETL_LOG_LEVEL", "INFO").upper(),
        )
