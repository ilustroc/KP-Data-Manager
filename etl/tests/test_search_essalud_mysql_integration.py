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
        "control": f"kpdm_essalud_control_{suffix}",
        "bronze": f"kpdm_essalud_bronze_{suffix}",
        "silver": f"kpdm_essalud_silver_{suffix}",
        "gold": f"kpdm_essalud_gold_{suffix}",
    }
    options = {
        "host": os.getenv("KPDM_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("KPDM_MYSQL_PORT", "3306")),
        "user": os.getenv("KPDM_MYSQL_USER", "kpdm_test"),
        "password": os.getenv("KPDM_MYSQL_PASSWORD", "kpdm_test_password"),
        "charset": "utf8mb4",
        "autocommit": True,
    }
    administrative_connection = pymysql.connect(**options)

    try:
        with administrative_connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = str(cursor.fetchone()[0])
            if not (version.startswith("5.7.") or version.startswith("8.")):
                pytest.fail(f"Versión MySQL no soportada: {version}")
            for name in databases.values():
                cursor.execute(
                    f"CREATE DATABASE `{name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )

        settings = Settings(
            db_host=options["host"],
            db_port=options["port"],
            db_username=options["user"],
            db_password=options["password"],
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
            log_level="CRITICAL",
        )
        database = MySqlDatabase(settings)
        _create_schema(database)
        _seed_active_source(database)

        yield database, version
    finally:
        database_instance = locals().get("database")
        if isinstance(database_instance, MySqlDatabase):
            database_instance.close()
        with administrative_connection.cursor() as cursor:
            for name in reversed(tuple(databases.values())):
                cursor.execute(f"DROP DATABASE IF EXISTS `{name}`")
        administrative_connection.close()


def test_full_replace_uses_both_integrity_directions_and_a_sargable_document_index(
    mysql_database,
) -> None:
    database, _ = mysql_database
    _seed_gold(database, (("00000009", "202501", "old-9"),))
    _seed_batch(
        database,
        batch_id=201,
        refresh_mode="FULL_REPLACE",
        status="PROCESANDO",
        records=(
            ("00000001", "202610", "hash-1"),
            ("00000001", "202609", "hash-2"),
        ),
        scope_documents=("00000001",),
    )

    database.publish_search(
        _batch(201, "PROCESANDO", "FULL_REPLACE"),
        datetime(2026, 10, 21, 12, 0),
        ProcessingStats(file_rows=2, inserted_rows=2, scope_count=1),
    )

    assert _gold_keys(database) == {
        ("00000001", "202609", _record_hash("hash-2")),
        ("00000001", "202610", _record_hash("hash-1")),
    }
    assert _batch_state(database, 201) == ("COMPLETADO", 2)
    assert _index_exists(database, "idx_essalud_batch_document")
    assert _silver_to_scope_plan_index(database, 201) == "uq_batch_document"
    assert _scope_to_silver_plan_index(database, 201) == "idx_essalud_document_period"


def test_scope_replace_replaces_only_scoped_essalud_documents(mysql_database) -> None:
    database, _ = mysql_database
    _seed_gold(
        database,
        (
            ("00000001", "202501", "old-scoped"),
            ("00000002", "202501", "old-unrelated"),
        ),
    )
    _seed_batch(
        database,
        batch_id=202,
        refresh_mode="SCOPE_REPLACE",
        status="PROCESANDO",
        records=(("00000001", "202610", "new-scoped"),),
        scope_documents=("00000001",),
    )

    database.publish_search(
        _batch(202, "PROCESANDO", "SCOPE_REPLACE"),
        datetime(2026, 10, 21, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    assert _gold_keys(database) == {
        ("00000001", "202610", _record_hash("new-scoped")),
        ("00000002", "202501", _record_hash("old-unrelated")),
    }
    assert _batch_state(database, 202) == ("COMPLETADO", 1)


def test_publish_only_recovery_preserves_bronze_and_silver_history(mysql_database) -> None:
    database, _ = mysql_database
    _seed_gold(database, (("00000009", "202501", "old-9"),))
    _seed_batch(
        database,
        batch_id=203,
        refresh_mode="FULL_REPLACE",
        status="ERROR",
        records=(("00000003", "202610", "recovery-3"),),
        scope_documents=("00000003",),
    )
    historical_counts = _history_counts(database, 203)

    result = SearchLoader(
        database,
        database.settings,
        clock=lambda: datetime(2026, 10, 21, 12, 0),
    ).recover_publish(203)

    assert result.status == "COMPLETADO"
    assert _history_counts(database, 203) == historical_counts == (1, 1)
    assert _gold_keys(database) == {
        ("00000003", "202610", _record_hash("recovery-3"))
    }
    assert _batch_state(database, 203) == ("COMPLETADO", 1)


@pytest.mark.parametrize(
    ("records", "scope_documents"),
    [
        ((("00000004", "202610", "silver-without-scope"),), ()),
        (
            (("00000004", "202610", "scope-without-silver"),),
            ("00000004", "00000005"),
        ),
    ],
)
def test_bidirectional_integrity_mismatch_rolls_back_gold(
    mysql_database,
    records,
    scope_documents,
) -> None:
    database, _ = mysql_database
    _seed_gold(database, (("00000009", "202501", "old-9"),))
    _seed_batch(
        database,
        batch_id=204,
        refresh_mode="FULL_REPLACE",
        status="PROCESANDO",
        records=records,
        scope_documents=scope_documents,
    )
    before = _gold_keys(database)

    with pytest.raises(RuntimeError, match="scope oficial"):
        database.publish_search(
            _batch(204, "PROCESANDO", "FULL_REPLACE"),
            datetime(2026, 10, 21, 12, 0),
            ProcessingStats(
                file_rows=len(records),
                inserted_rows=len(records),
                scope_count=len(scope_documents),
            ),
        )

    assert _gold_keys(database) == before
    assert _batch_state(database, 204) == ("PROCESANDO", 0)


def _create_schema(database: MySqlDatabase) -> None:
    control = database.settings.control_database
    bronze = database.settings.bronze_database
    silver = database.settings.silver_database
    gold = database.settings.gold_database
    statements = (
        f"""CREATE TABLE `{control}`.`import_source` (
            source_code VARCHAR(64) NOT NULL PRIMARY KEY,
            is_active TINYINT(1) NOT NULL
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{control}`.`import_dataset_source` (
            dataset_code VARCHAR(50) NOT NULL,
            source_code VARCHAR(64) NOT NULL,
            allows_full_replace TINYINT(1) NOT NULL,
            allows_scope_replace TINYINT(1) NOT NULL,
            allows_upsert TINYINT(1) NOT NULL DEFAULT 0,
            is_active TINYINT(1) NOT NULL,
            PRIMARY KEY (dataset_code, source_code)
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{control}`.`import_batch` (
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
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{control}`.`import_scope_document` (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            batch_id BIGINT UNSIGNED NOT NULL,
            documento VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE KEY uq_batch_document (batch_id, documento)
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{bronze}`.`search_raw_row` (
            raw_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            batch_id BIGINT UNSIGNED NOT NULL,
            dataset_code VARCHAR(50) NOT NULL,
            source_code VARCHAR(64) NOT NULL,
            source_row BIGINT UNSIGNED NOT NULL,
            source_file VARCHAR(255) NOT NULL,
            raw_payload JSON NOT NULL,
            row_hash CHAR(64) NOT NULL,
            ingested_at DATETIME NOT NULL
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{silver}`.`search_laboral_essalud` (
            employment_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            documento VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            periodo CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            ruc CHAR(11) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            nombre_empresa VARCHAR(255) NULL,
            sueldo DECIMAL(18,2) NULL,
            situacion VARCHAR(20) NULL,
            source_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            batch_id BIGINT UNSIGNED NOT NULL,
            source_raw_id BIGINT UNSIGNED NOT NULL,
            record_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE KEY uq_essalud_batch_hash (batch_id, record_hash),
            KEY idx_essalud_document_period (documento, periodo),
            KEY idx_essalud_batch_document (batch_id, documento)
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{gold}`.`search_laboral_essalud` (
            gold_employment_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            documento VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            periodo CHAR(6) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            ruc CHAR(11) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            nombre_empresa VARCHAR(255) NULL,
            sueldo DECIMAL(18,2) NULL,
            situacion VARCHAR(20) NULL,
            record_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            source_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
            batch_id BIGINT UNSIGNED NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE KEY uq_gold_essalud_document_hash (documento, record_hash),
            KEY idx_gold_essalud_source_batch (source_code, batch_id)
        ) ENGINE=InnoDB""",
    )
    with database.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def _seed_active_source(database: MySqlDatabase) -> None:
    control = database.settings.control_database
    _execute(
        database,
        f"INSERT INTO `{control}`.`import_source` (source_code, is_active) VALUES ('BASE_ESSALUD', 1)",
    )
    _execute(
        database,
        f"""INSERT INTO `{control}`.`import_dataset_source`
            (dataset_code, source_code, allows_full_replace, allows_scope_replace,
             allows_upsert, is_active)
            VALUES ('LABORAL_ESSALUD', 'BASE_ESSALUD', 1, 1, 0, 1)""",
    )


def _seed_batch(
    database: MySqlDatabase,
    *,
    batch_id: int,
    refresh_mode: str,
    status: str,
    records: tuple[tuple[str, str, str], ...],
    scope_documents: tuple[str, ...],
) -> None:
    control = database.settings.control_database
    bronze = database.settings.bronze_database
    silver = database.settings.silver_database
    _execute(
        database,
        f"""INSERT INTO `{control}`.`import_batch`
            (batch_id, tipo, perfil_version, dataset_code, source_code, refresh_mode,
             mapping_version, estado, archivo, archivo_original, archivo_ruta,
             archivo_extension, filas_archivo, filas_insertadas, filas_duplicadas,
             filas_error, rows_valid, rows_invalid, rows_published, scope_count)
            VALUES (%s, 'SEARCH', '1', 'LABORAL_ESSALUD', 'BASE_ESSALUD', %s,
                    1, %s, 'essalud.csv', 'essalud.csv', '2026/10/essalud.csv',
                    'csv', %s, %s, 0, 0, %s, 0, 0, %s)""",
        (
            batch_id,
            refresh_mode,
            status,
            len(records),
            len(records),
            len(records),
            len(scope_documents),
        ),
    )
    with database.connection.cursor() as cursor:
        cursor.executemany(
            f"""INSERT INTO `{bronze}`.`search_raw_row`
                (batch_id, dataset_code, source_code, source_row, source_file,
                 raw_payload, row_hash, ingested_at)
                VALUES (%s, 'LABORAL_ESSALUD', 'BASE_ESSALUD', %s, 'essalud.csv',
                        %s, %s, '2026-10-21 00:00:00')""",
            [(batch_id, position, '{}', f"{position:064x}") for position, _ in enumerate(records, start=2)],
        )
        cursor.executemany(
            f"""INSERT INTO `{silver}`.`search_laboral_essalud`
                (documento, periodo, ruc, nombre_empresa, sueldo, situacion, source_code,
                 batch_id, source_raw_id, record_hash, created_at)
                VALUES (%s, %s, '20100070970', 'Empresa', 1000.00, 'A', 'BASE_ESSALUD',
                        %s, %s, %s, '2026-10-21 00:00:00')""",
            [
                (documento, periodo, batch_id, position, _record_hash(record_hash))
                for position, (documento, periodo, record_hash) in enumerate(records, start=1)
            ],
        )
        cursor.executemany(
            f"""INSERT INTO `{control}`.`import_scope_document`
                (batch_id, documento, created_at) VALUES (%s, %s, '2026-10-21 00:00:00')""",
            [(batch_id, documento) for documento in scope_documents],
        )


def _seed_gold(database: MySqlDatabase, records: tuple[tuple[str, str, str], ...]) -> None:
    gold = database.settings.gold_database
    with database.connection.cursor() as cursor:
        cursor.executemany(
            f"""INSERT INTO `{gold}`.`search_laboral_essalud`
                (documento, periodo, ruc, nombre_empresa, sueldo, situacion, record_hash,
                 source_code, batch_id, updated_at)
                VALUES (%s, %s, '20100070970', 'Empresa previa', 900.00, 'A', %s,
                        'BASE_ESSALUD', 1, '2026-01-01 00:00:00')""",
            [(documento, periodo, _record_hash(record_hash)) for documento, periodo, record_hash in records],
        )


def _batch(batch_id: int, status: str, refresh_mode: str) -> BatchRecord:
    return BatchRecord(
        batch_id=batch_id,
        tipo="SEARCH",
        estado=status,
        archivo_original="essalud.csv",
        archivo_ruta="2026/10/essalud.csv",
        archivo_extension="csv",
        archivo_sha256=None,
        perfil_version="1",
        dataset_code="LABORAL_ESSALUD",
        source_code="BASE_ESSALUD",
        refresh_mode=refresh_mode,
        mapping_version=1,
    )


def _gold_keys(database: MySqlDatabase) -> set[tuple[str, str, str]]:
    gold = database.settings.gold_database
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT documento, periodo, record_hash FROM `{gold}`.`search_laboral_essalud`"
        )
        rows = cursor.fetchall()
    return {
        (str(row["documento"]), str(row["periodo"]), str(row["record_hash"]))
        for row in rows
    }


def _history_counts(database: MySqlDatabase, batch_id: int) -> tuple[int, int]:
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) AS total FROM `{database.settings.bronze_database}`.`search_raw_row` WHERE batch_id = %s",
            (batch_id,),
        )
        bronze_count = int(cursor.fetchone()["total"])
        cursor.execute(
            f"SELECT COUNT(*) AS total FROM `{database.settings.silver_database}`.`search_laboral_essalud` WHERE batch_id = %s",
            (batch_id,),
        )
        silver_count = int(cursor.fetchone()["total"])
    return bronze_count, silver_count


def _batch_state(database: MySqlDatabase, batch_id: int) -> tuple[str, int]:
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT estado, rows_published FROM `{database.settings.control_database}`.`import_batch` WHERE batch_id = %s",
            (batch_id,),
        )
        row = cursor.fetchone()
    return str(row["estado"]), int(row["rows_published"] or 0)


def _index_exists(database: MySqlDatabase, index_name: str) -> bool:
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"SHOW INDEX FROM `{database.settings.silver_database}`.`search_laboral_essalud` WHERE Key_name = %s",
            (index_name,),
        )
        return cursor.fetchone() is not None


def _scope_to_silver_plan_index(database: MySqlDatabase, batch_id: int) -> str | None:
    control = database.settings.control_database
    silver = database.settings.silver_database
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"""EXPLAIN SELECT 1
                FROM `{control}`.`import_scope_document` AS scope
                LEFT JOIN `{silver}`.`search_laboral_essalud` AS silver
                  ON silver.batch_id = scope.batch_id
                 AND silver.documento = (CONVERT(scope.documento USING ascii) COLLATE ascii_bin)
                WHERE scope.batch_id = %s AND silver.employment_id IS NULL
                LIMIT 1""",
            (batch_id,),
        )
        plan = cursor.fetchall()
    return next((row["key"] for row in plan if row["table"] == "silver"), None)


def _silver_to_scope_plan_index(database: MySqlDatabase, batch_id: int) -> str | None:
    control = database.settings.control_database
    silver = database.settings.silver_database
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"""EXPLAIN SELECT 1
                FROM `{silver}`.`search_laboral_essalud` AS silver
                LEFT JOIN `{control}`.`import_scope_document` AS scope
                  ON scope.batch_id = silver.batch_id
                 AND scope.documento = (CONVERT(silver.documento USING utf8mb4) COLLATE utf8mb4_unicode_ci)
                WHERE silver.batch_id = %s AND scope.id IS NULL
                LIMIT 1""",
            (batch_id,),
        )
        plan = cursor.fetchall()
    return next((row["key"] for row in plan if row["table"] == "scope"), None)


def _record_hash(value: str) -> str:
    return value.encode("ascii").hex().ljust(64, "0")[:64]


def _execute(database: MySqlDatabase, sql: str, values: tuple[object, ...] = ()) -> None:
    with database.connection.cursor() as cursor:
        cursor.execute(sql, values)
