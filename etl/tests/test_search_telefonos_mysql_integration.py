from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

import pymysql
import pytest

from src.config import Settings
from src.db import MySqlDatabase
from src.domain.models import BatchRecord, ProcessingStats
from src.loaders.search_loader import SearchLoader

pytestmark = pytest.mark.mysql_integration

if os.getenv("KPDM_RUN_MYSQL_INTEGRATION") != "1":
    pytest.skip(
        "Define KPDM_RUN_MYSQL_INTEGRATION=1 para ejecutar contra MySQL aislado.",
        allow_module_level=True,
    )


@pytest.fixture()
def mysql_database(tmp_path: Path):
    suffix = uuid.uuid4().hex[:10]
    databases = {
        "control": f"kpdm_it_control_{suffix}",
        "bronze": f"kpdm_it_bronze_{suffix}",
        "silver": f"kpdm_it_silver_{suffix}",
        "gold": f"kpdm_it_gold_{suffix}",
    }
    connection_options = {
        "host": os.getenv("KPDM_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("KPDM_MYSQL_PORT", "3306")),
        "user": os.getenv("KPDM_MYSQL_USER", "kpdm_test"),
        "password": os.getenv("KPDM_MYSQL_PASSWORD", "kpdm_test_password"),
        "charset": "utf8mb4",
        "autocommit": True,
    }
    administrative_connection = pymysql.connect(**connection_options)

    try:
        with administrative_connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = str(cursor.fetchone()[0])
            if not (version.startswith("8.") or version.startswith("5.7.")):
                pytest.fail(f"Versión MySQL no soportada por esta prueba: {version}")
            for database_name in databases.values():
                cursor.execute(
                    f"CREATE DATABASE `{database_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )

        settings = Settings(
            db_host=connection_options["host"],
            db_port=connection_options["port"],
            db_username=connection_options["user"],
            db_password=connection_options["password"],
            db_connect_timeout=15,
            db_read_timeout=60,
            db_write_timeout=60,
            search_publication_lock_timeout=5,
            control_database=databases["control"],
            bronze_database=databases["bronze"],
            silver_database=databases["silver"],
            gold_database=databases["gold"],
            storage_root=tmp_path,
            insert_batch_size=100,
            progress_update_every=100,
            allow_zero_amount=True,
            error_value_max_length=500,
            log_level="INFO",
        )
        database = MySqlDatabase(settings)
        _create_schema(database)

        yield database, version
    finally:
        database_instance = locals().get("database")
        if isinstance(database_instance, MySqlDatabase):
            database_instance.close()
        with administrative_connection.cursor() as cursor:
            for database_name in reversed(tuple(databases.values())):
                cursor.execute(f"DROP DATABASE IF EXISTS `{database_name}`")
        administrative_connection.close()


def test_upsert_inserts_updates_preserves_and_is_idempotent(mysql_database) -> None:
    database, _ = mysql_database
    _seed_source(database, allows_upsert=True)
    _seed_gold(database)
    _seed_phone_batch(
        database,
        batch_id=101,
        status="PROCESANDO",
        phones=(
            ("00000001", "900000001", "CLARO", "2026-10-20"),
            ("00000001", "900000004", "ENTEL", "2026-10-20"),
        ),
    )
    before = _gold_rows(database)

    database.publish_search(
        _batch(101, "PROCESANDO"),
        datetime(2026, 10, 20, 12, 0),
        ProcessingStats(file_rows=2, inserted_rows=2, scope_count=1),
    )

    after = _gold_rows(database)
    assert set(before) <= set(after)
    assert set(after) == {
        ("00000001", "900000001"),
        ("00000001", "900000002"),
        ("00000001", "900000004"),
        ("00000002", "900000003"),
    }
    assert after[("00000001", "900000001")]["operador"] == "CLARO"
    assert str(after[("00000001", "900000001")]["fecha_data"]) == "2026-10-20"
    assert after[("00000001", "900000001")]["batch_id"] == 101
    assert after[("00000001", "900000002")] == before[("00000001", "900000002")]
    assert after[("00000002", "900000003")] == before[("00000002", "900000003")]
    assert _batch_state(database, 101) == ("COMPLETADO", 2)

    _execute(
        database,
        f"UPDATE `{database.settings.control_database}`.`import_batch` "
        "SET estado = 'ERROR', rows_published = 0 WHERE batch_id = 101",
    )
    SearchLoader(
        database,
        database.settings,
        clock=lambda: datetime(2026, 10, 20, 12, 0),
    ).recover_publish(101)

    repeated = _gold_rows(database)
    assert repeated == after
    assert _batch_state(database, 101) == ("COMPLETADO", 2)


def test_upsert_rolls_back_gold_when_final_integrity_check_fails(mysql_database) -> None:
    database, _ = mysql_database
    _seed_source(database, allows_upsert=True)
    _seed_gold(database)
    _seed_phone_batch(
        database,
        batch_id=102,
        status="PROCESANDO",
        phones=(("00000001", "900000005", "BITEL", "2026-10-20"),),
        persisted_valid_rows=2,
    )
    before = _gold_rows(database)

    with pytest.raises(RuntimeError, match="contadores persistidos"):
        database.publish_search(
            _batch(102, "PROCESANDO"),
            datetime(2026, 10, 20, 12, 30),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert _gold_rows(database) == before
    assert _batch_state(database, 102) == ("PROCESANDO", 0)


def test_upsert_rejects_other_datasets_and_unauthorized_sources(mysql_database) -> None:
    database, _ = mysql_database
    _seed_source(database, allows_upsert=False)
    _seed_gold(database)
    _seed_phone_batch(
        database,
        batch_id=103,
        status="PROCESANDO",
        phones=(("00000001", "900000005", "BITEL", "2026-10-20"),),
    )
    before = _gold_rows(database)

    with pytest.raises(RuntimeError, match="dejó de estar autorizado"):
        database.publish_search(
            _batch(103, "PROCESANDO"),
            datetime(2026, 10, 20, 13, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    with pytest.raises(RuntimeError, match="únicamente para TELEFONOS"):
        database.publish_search(
            BatchRecord(
                batch_id=999,
                tipo="SEARCH",
                estado="PROCESANDO",
                archivo_original="personas.csv",
                archivo_ruta="2026/10/personas.csv",
                archivo_extension="csv",
                archivo_sha256=None,
                perfil_version="1",
                dataset_code="PERSONAS",
                source_code="BASE_PERSONAS",
                refresh_mode="UPSERT",
                mapping_version=1,
            ),
            datetime(2026, 10, 20, 13, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert _gold_rows(database) == before

    _execute(
        database,
        f"UPDATE `{database.settings.control_database}`.`import_dataset_source` "
        "SET allows_upsert = 1 WHERE dataset_code = 'TELEFONOS'",
    )
    _execute(
        database,
        f"INSERT INTO `{database.settings.control_database}`.`import_source` "
        "(source_code, is_active) VALUES ('BASE_TELEFONOS_2', 1)",
    )
    _execute(
        database,
        f"INSERT INTO `{database.settings.control_database}`.`import_dataset_source` "
        "(dataset_code, source_code, allows_full_replace, allows_scope_replace, "
        "allows_upsert, is_active) VALUES "
        "('TELEFONOS', 'BASE_TELEFONOS_2', 1, 1, 1, 1)",
    )

    with pytest.raises(RuntimeError, match="exactamente una fuente activa"):
        database.publish_search(
            _batch(103, "PROCESANDO"),
            datetime(2026, 10, 20, 13, 30),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert _gold_rows(database) == before


def test_failed_batch_before_publication_recovers_without_losing_existing_keys(
    mysql_database,
) -> None:
    database, _ = mysql_database
    _seed_source(database, allows_upsert=True)
    _seed_gold(database)
    _seed_phone_batch(
        database,
        batch_id=104,
        status="ERROR",
        phones=(("00000003", "900000006", "CLARO", "2026-10-20"),),
    )
    before = _gold_rows(database)

    result = SearchLoader(
        database,
        database.settings,
        clock=lambda: datetime(2026, 10, 20, 14, 0),
    ).recover_publish(104)

    after = _gold_rows(database)
    assert result.status == "COMPLETADO"
    assert set(before) <= set(after)
    assert ("00000003", "900000006") in after
    assert _batch_state(database, 104) == ("COMPLETADO", 1)


def _create_schema(database: MySqlDatabase) -> None:
    control = database.settings.control_database
    bronze = database.settings.bronze_database
    silver = database.settings.silver_database
    gold = database.settings.gold_database
    statements = (
        f"""
        CREATE TABLE `{control}`.`import_source` (
            source_code VARCHAR(64) NOT NULL PRIMARY KEY,
            is_active TINYINT(1) NOT NULL
        ) ENGINE=InnoDB
        """,
        f"""
        CREATE TABLE `{control}`.`import_dataset_source` (
            dataset_code VARCHAR(50) NOT NULL,
            source_code VARCHAR(64) NOT NULL,
            allows_full_replace TINYINT(1) NOT NULL DEFAULT 0,
            allows_scope_replace TINYINT(1) NOT NULL DEFAULT 0,
            allows_upsert TINYINT(1) NOT NULL DEFAULT 0,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            PRIMARY KEY (dataset_code, source_code)
        ) ENGINE=InnoDB
        """,
        f"""
        CREATE TABLE `{control}`.`import_batch` (
            batch_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
            tipo VARCHAR(50) NOT NULL,
            entidad VARCHAR(50) NULL,
            perfil_version VARCHAR(20) NULL,
            dataset_code VARCHAR(50) NULL,
            source_code VARCHAR(64) NULL,
            refresh_mode VARCHAR(20) NULL,
            mapping_version INT UNSIGNED NULL,
            estado VARCHAR(30) NOT NULL,
            archivo VARCHAR(255) NOT NULL,
            archivo_original VARCHAR(255) NULL,
            archivo_ruta VARCHAR(500) NULL,
            archivo_extension VARCHAR(20) NULL,
            archivo_sha256 CHAR(64) NULL,
            fecha_inicio DATETIME NULL,
            fecha_fin DATETIME NULL,
            filas_archivo BIGINT UNSIGNED NOT NULL DEFAULT 0,
            filas_insertadas BIGINT UNSIGNED NOT NULL DEFAULT 0,
            filas_duplicadas BIGINT UNSIGNED NOT NULL DEFAULT 0,
            filas_error BIGINT UNSIGNED NOT NULL DEFAULT 0,
            rows_valid BIGINT UNSIGNED NULL,
            rows_invalid BIGINT UNSIGNED NULL,
            rows_published BIGINT UNSIGNED NULL,
            scope_count BIGINT UNSIGNED NULL,
            validated_at DATETIME NULL,
            published_at DATETIME NULL,
            mensaje_error TEXT NULL
        ) ENGINE=InnoDB
        """,
        f"""
        CREATE TABLE `{control}`.`import_scope_document` (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            batch_id BIGINT UNSIGNED NOT NULL,
            documento VARCHAR(100) NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE KEY uq_batch_document (batch_id, documento)
        ) ENGINE=InnoDB
        """,
        f"""
        CREATE TABLE `{bronze}`.`search_raw_row` (
            raw_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            batch_id BIGINT UNSIGNED NOT NULL,
            dataset_code VARCHAR(50) NOT NULL,
            source_code VARCHAR(64) NOT NULL,
            source_row BIGINT UNSIGNED NOT NULL,
            source_file VARCHAR(255) NOT NULL,
            raw_payload JSON NOT NULL,
            row_hash CHAR(64) NOT NULL,
            ingested_at DATETIME NOT NULL
        ) ENGINE=InnoDB
        """,
        f"""
        CREATE TABLE `{silver}`.`search_telefonos` (
            phone_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            documento VARCHAR(20) NOT NULL,
            telefono CHAR(9) NOT NULL,
            operador VARCHAR(32) NOT NULL,
            operador_raw VARCHAR(150) NULL,
            fecha_data DATE NOT NULL,
            source_code VARCHAR(64) NOT NULL,
            batch_id BIGINT UNSIGNED NOT NULL,
            source_raw_id BIGINT UNSIGNED NOT NULL,
            record_hash CHAR(64) NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE KEY uq_batch_document_phone (batch_id, documento, telefono)
        ) ENGINE=InnoDB
        """,
        f"""
        CREATE TABLE `{gold}`.`search_telefonos` (
            documento VARCHAR(20) NOT NULL,
            telefono CHAR(9) NOT NULL,
            operador VARCHAR(32) NOT NULL,
            fecha_data DATE NOT NULL,
            source_code VARCHAR(64) NOT NULL,
            batch_id BIGINT UNSIGNED NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (documento, telefono),
            KEY idx_source_batch (source_code, batch_id)
        ) ENGINE=InnoDB
        """,
    )
    with database.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def _seed_source(database: MySqlDatabase, *, allows_upsert: bool) -> None:
    control = database.settings.control_database
    _execute(
        database,
        f"INSERT INTO `{control}`.`import_source` (source_code, is_active) "
        "VALUES ('BASE_TELEFONOS', 1)",
    )
    _execute(
        database,
        f"INSERT INTO `{control}`.`import_dataset_source` "
        "(dataset_code, source_code, allows_full_replace, allows_scope_replace, "
        "allows_upsert, is_active) VALUES ('TELEFONOS', 'BASE_TELEFONOS', 1, 1, %s, 1)",
        (int(allows_upsert),),
    )


def _seed_gold(database: MySqlDatabase) -> None:
    gold = database.settings.gold_database
    rows = (
        ("00000001", "900000001", "MOVISTAR", "2025-01-01", 10),
        ("00000001", "900000002", "ENTEL", "2025-01-02", 10),
        ("00000002", "900000003", "BITEL", "2025-01-03", 11),
    )
    with database.connection.cursor() as cursor:
        cursor.executemany(
            f"INSERT INTO `{gold}`.`search_telefonos` "
            "(documento, telefono, operador, fecha_data, source_code, batch_id, updated_at) "
            "VALUES (%s, %s, %s, %s, 'BASE_TELEFONOS', %s, '2025-01-10 00:00:00')",
            rows,
        )


def _seed_phone_batch(
    database: MySqlDatabase,
    *,
    batch_id: int,
    status: str,
    phones: tuple[tuple[str, str, str, str], ...],
    persisted_valid_rows: int | None = None,
) -> None:
    control = database.settings.control_database
    bronze = database.settings.bronze_database
    silver = database.settings.silver_database
    valid_rows = len(phones) if persisted_valid_rows is None else persisted_valid_rows
    documents = tuple(dict.fromkeys(phone[0] for phone in phones))
    _execute(
        database,
        f"INSERT INTO `{control}`.`import_batch` "
        "(batch_id, tipo, perfil_version, dataset_code, source_code, refresh_mode, "
        "mapping_version, estado, archivo, archivo_original, archivo_ruta, "
        "archivo_extension, filas_archivo, filas_insertadas, filas_duplicadas, "
        "filas_error, rows_valid, rows_invalid, rows_published, scope_count) VALUES "
        "(%s, 'SEARCH', '1', 'TELEFONOS', 'BASE_TELEFONOS', 'UPSERT', 1, %s, "
        "'telefonos.csv', 'telefonos.csv', '2026/10/telefonos.csv', 'csv', %s, %s, "
        "0, 0, %s, 0, 0, %s)",
        (batch_id, status, len(phones), len(phones), valid_rows, len(documents)),
    )
    with database.connection.cursor() as cursor:
        cursor.executemany(
            f"INSERT INTO `{bronze}`.`search_raw_row` "
            "(batch_id, dataset_code, source_code, source_row, source_file, raw_payload, "
            "row_hash, ingested_at) VALUES "
            "(%s, 'TELEFONOS', 'BASE_TELEFONOS', %s, 'telefonos.csv', %s, %s, "
            "'2026-10-20 00:00:00')",
            [
                (batch_id, index, '{}', f"{index:064x}")
                for index, _ in enumerate(phones, start=2)
            ],
        )
        cursor.executemany(
            f"INSERT INTO `{silver}`.`search_telefonos` "
            "(documento, telefono, operador, operador_raw, fecha_data, source_code, "
            "batch_id, source_raw_id, record_hash, created_at) VALUES "
            "(%s, %s, %s, %s, %s, 'BASE_TELEFONOS', %s, %s, %s, "
            "'2026-10-20 00:00:00')",
            [
                (
                    document,
                    phone,
                    operator,
                    operator,
                    data_date,
                    batch_id,
                    index,
                    f"{index:064x}",
                )
                for index, (document, phone, operator, data_date) in enumerate(
                    phones,
                    start=1,
                )
            ],
        )
        cursor.executemany(
            f"INSERT INTO `{control}`.`import_scope_document` "
            "(batch_id, documento, created_at) VALUES "
            "(%s, %s, '2026-10-20 00:00:00')",
            [(batch_id, document) for document in documents],
        )


def _batch(batch_id: int, status: str) -> BatchRecord:
    return BatchRecord(
        batch_id=batch_id,
        tipo="SEARCH",
        estado=status,
        archivo_original="telefonos.csv",
        archivo_ruta="2026/10/telefonos.csv",
        archivo_extension="csv",
        archivo_sha256=None,
        perfil_version="1",
        dataset_code="TELEFONOS",
        source_code="BASE_TELEFONOS",
        refresh_mode="UPSERT",
        mapping_version=1,
    )


def _gold_rows(database: MySqlDatabase) -> dict[tuple[str, str], dict[str, object]]:
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT documento, telefono, operador, fecha_data, source_code, batch_id, "
            f"updated_at FROM `{database.settings.gold_database}`.`search_telefonos` "
            "ORDER BY documento, telefono"
        )
        rows = cursor.fetchall()

    return {
        (str(row["documento"]), str(row["telefono"])): {
            "operador": str(row["operador"]),
            "fecha_data": row["fecha_data"],
            "source_code": str(row["source_code"]),
            "batch_id": int(row["batch_id"]),
            "updated_at": row["updated_at"],
        }
        for row in rows
    }


def _batch_state(database: MySqlDatabase, batch_id: int) -> tuple[str, int]:
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT estado, rows_published FROM "
            f"`{database.settings.control_database}`.`import_batch` WHERE batch_id = %s",
            (batch_id,),
        )
        row = cursor.fetchone()

    return str(row["estado"]), int(row["rows_published"] or 0)


def _execute(
    database: MySqlDatabase,
    sql: str,
    values: tuple[object, ...] = (),
) -> None:
    with database.connection.cursor() as cursor:
        cursor.execute(sql, values)
