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

pytestmark = pytest.mark.mysql_integration

if os.getenv("KPDM_RUN_MYSQL_INTEGRATION") != "1":
    pytest.skip(
        "Define KPDM_RUN_MYSQL_INTEGRATION=1 para ejecutar contra MySQL aislado.",
        allow_module_level=True,
    )


SQL_DIRECTORY = Path(__file__).resolve().parents[2] / "database" / "sql"


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
        _create_supporting_schema(database)
        _execute_contract_sql(database, "028_create_search_personas.sql")
        _execute_contract_sql(database, "029_create_search_person_index.sql")

        yield database, version
    finally:
        database_instance = locals().get("database")
        if isinstance(database_instance, MySqlDatabase):
            database_instance.close()
        with administrative_connection.cursor() as cursor:
            for database_name in reversed(tuple(databases.values())):
                cursor.execute(f"DROP DATABASE IF EXISTS `{database_name}`")
        administrative_connection.close()


def test_full_replace_publishes_and_updates_parents(mysql_database) -> None:
    database, _ = mysql_database
    _seed_active_source(database)
    _seed_gold_person(
        database,
        documento="73809323",
        batch_id=40,
        padre="PADRE ANTERIOR",
        madre="MADRE ANTERIOR",
    )
    _seed_personas_batch(
        database,
        batch_id=44,
        refresh_mode="FULL_REPLACE",
        people=(("73809323", "LUCAS", "PAULA PACIZA"),),
    )

    database.publish_search(
        _batch(44, "FULL_REPLACE"),
        datetime(2026, 10, 22, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    person = _gold_person(database, "73809323")
    assert person["padre"] == "LUCAS"
    assert person["madre"] == "PAULA PACIZA"
    assert person["batch_id"] == 44
    assert _batch_state(database, 44) == ("COMPLETADO", 1)


def test_scope_replace_publishes_parents_without_changing_outside_documents(
    mysql_database,
) -> None:
    database, _ = mysql_database
    _seed_active_source(database)
    _seed_gold_person(
        database,
        documento="73809323",
        batch_id=40,
        padre="PADRE ANTERIOR",
        madre="MADRE ANTERIOR",
    )
    _seed_gold_person(
        database,
        documento="87654321",
        batch_id=41,
        padre="PADRE EXTERNO",
        madre="MADRE EXTERNA",
    )
    _seed_personas_batch(
        database,
        batch_id=45,
        refresh_mode="SCOPE_REPLACE",
        people=(("73809323", "LUCAS NUEVO", "PAULA NUEVA"),),
    )
    before_outside_person = _gold_person(database, "87654321")

    database.publish_search(
        _batch(45, "SCOPE_REPLACE"),
        datetime(2026, 10, 22, 12, 30),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    scoped_person = _gold_person(database, "73809323")
    assert scoped_person["padre"] == "LUCAS NUEVO"
    assert scoped_person["madre"] == "PAULA NUEVA"
    assert scoped_person["batch_id"] == 45
    assert _gold_person(database, "87654321") == before_outside_person


def test_upgrade_and_backfill_require_exact_personas_lineage(mysql_database) -> None:
    database, _ = mysql_database
    _seed_active_source(database)
    gold = database.settings.gold_database

    _execute(database, f"ALTER TABLE `{gold}`.`search_person_index` DROP COLUMN madre")
    _execute(database, f"ALTER TABLE `{gold}`.`search_person_index` DROP COLUMN padre")
    _execute_contract_sql(database, "056_add_search_person_index_parent_columns.sql")
    _execute_contract_sql(database, "056_add_search_person_index_parent_columns.sql")
    assert _gold_parent_columns(database) == ("padre", "madre")

    _seed_gold_person(
        database,
        documento="73809323",
        batch_id=44,
        padre="VALOR ANTIGUO",
        madre="VALOR ANTIGUO",
    )
    _seed_silver_person(database, 44, "73809323", "LUCAS", "PAULA PACIZA")
    _seed_silver_person(database, 43, "73809323", "OTRO PADRE", "OTRA MADRE")

    _execute_contract_sql(database, "057_backfill_search_person_index_parents.sql")

    person = _gold_person(database, "73809323")
    assert person["padre"] == "LUCAS"
    assert person["madre"] == "PAULA PACIZA"
    assert person["batch_id"] == 44


def test_backfill_aborts_without_exact_personas_lineage(mysql_database) -> None:
    database, _ = mysql_database
    _seed_active_source(database)
    _seed_gold_person(
        database,
        documento="73809323",
        batch_id=44,
        padre="PADRE ANTERIOR",
        madre="MADRE ANTERIOR",
    )
    _seed_gold_person(
        database,
        documento="87654321",
        batch_id=45,
        padre="PADRE SIN SILVER",
        madre="MADRE SIN SILVER",
    )
    _seed_silver_person(database, 44, "73809323", "LUCAS", "PAULA PACIZA")

    _execute_contract_sql(database, "057_backfill_search_person_index_parents.sql")

    assert _gold_person(database, "73809323")["padre"] == "PADRE ANTERIOR"
    assert _gold_person(database, "87654321")["madre"] == "MADRE SIN SILVER"


def _create_supporting_schema(database: MySqlDatabase) -> None:
    control = database.settings.control_database
    bronze = database.settings.bronze_database
    statements = (
        f"""CREATE TABLE `{control}`.`import_source` (
            source_code VARCHAR(64) NOT NULL PRIMARY KEY,
            is_active TINYINT(1) NOT NULL
        ) ENGINE=InnoDB""",
        f"""CREATE TABLE `{control}`.`import_dataset_source` (
            dataset_code VARCHAR(50) NOT NULL,
            source_code VARCHAR(64) NOT NULL,
            allows_full_replace TINYINT(1) NOT NULL DEFAULT 0,
            allows_scope_replace TINYINT(1) NOT NULL DEFAULT 0,
            allows_upsert TINYINT(1) NOT NULL DEFAULT 0,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
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
            documento VARCHAR(100) NOT NULL,
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
    )
    with database.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def _seed_active_source(database: MySqlDatabase) -> None:
    control = database.settings.control_database
    _execute(
        database,
        f"INSERT INTO `{control}`.`import_source` (source_code, is_active) "
        "VALUES ('BASE_PERSONAS', 1)",
    )
    _execute(
        database,
        f"""INSERT INTO `{control}`.`import_dataset_source`
            (dataset_code, source_code, allows_full_replace, allows_scope_replace,
             allows_upsert, is_active)
            VALUES ('PERSONAS', 'BASE_PERSONAS', 1, 1, 0, 1)""",
    )


def _seed_personas_batch(
    database: MySqlDatabase,
    *,
    batch_id: int,
    refresh_mode: str,
    people: tuple[tuple[str, str, str], ...],
) -> None:
    control = database.settings.control_database
    bronze = database.settings.bronze_database
    documents = tuple(documento for documento, _, _ in people)
    _execute(
        database,
        f"""INSERT INTO `{control}`.`import_batch`
            (batch_id, tipo, perfil_version, dataset_code, source_code, refresh_mode,
             mapping_version, estado, archivo, archivo_original, archivo_ruta,
             archivo_extension, filas_archivo, filas_insertadas, filas_duplicadas,
             filas_error, rows_valid, rows_invalid, rows_published, scope_count)
            VALUES (%s, 'SEARCH', '1', 'PERSONAS', 'BASE_PERSONAS', %s, 1,
                    'PROCESANDO', 'personas.csv', 'personas.csv',
                    '2026/10/personas.csv', 'csv', %s, %s, 0, 0, %s, 0, 0, %s)""",
        (batch_id, refresh_mode, len(people), len(people), len(people), len(documents)),
    )
    with database.connection.cursor() as cursor:
        cursor.executemany(
            f"""INSERT INTO `{bronze}`.`search_raw_row`
                (batch_id, dataset_code, source_code, source_row, source_file,
                 raw_payload, row_hash, ingested_at)
                VALUES (%s, 'PERSONAS', 'BASE_PERSONAS', %s, 'personas.csv', %s, %s,
                        '2026-10-22 00:00:00')""",
            [
                (batch_id, index, '{}', f"{index:064x}")
                for index, _ in enumerate(people, start=1)
            ],
        )
    for index, (documento, padre, madre) in enumerate(people, start=1):
        _seed_silver_person(database, batch_id, documento, padre, madre, source_raw_id=index)
        _execute(
            database,
            f"""INSERT INTO `{control}`.`import_scope_document`
                (batch_id, documento, created_at)
                VALUES (%s, %s, '2026-10-22 00:00:00')""",
            (batch_id, documento),
        )


def _seed_silver_person(
    database: MySqlDatabase,
    batch_id: int,
    documento: str,
    padre: str,
    madre: str,
    *,
    source_raw_id: int = 1,
) -> None:
    silver = database.settings.silver_database
    _execute(
        database,
        f"""INSERT INTO `{silver}`.`search_personas`
            (documento, paterno, materno, nombres, nombre_completo, fecha_nacimiento,
             direccion_origen, sexo, estado_civil, padre, madre, source_code, batch_id,
             source_raw_id, record_hash, created_at)
            VALUES (%s, 'PATERNO', 'MATERNO', 'NOMBRES', 'NOMBRES PATERNO MATERNO',
                    '1990-01-01', 'DIRECCION', 'SIN DATO', 'SOLTERO', %s, %s,
                    'BASE_PERSONAS', %s, %s, %s, '2026-10-22 00:00:00')""",
        (documento, padre, madre, batch_id, source_raw_id, f"{batch_id:064x}"),
    )


def _seed_gold_person(
    database: MySqlDatabase,
    *,
    documento: str,
    batch_id: int,
    padre: str,
    madre: str,
) -> None:
    gold = database.settings.gold_database
    _execute(
        database,
        f"""INSERT INTO `{gold}`.`search_person_index`
            (documento, tipo_documento, nombre_completo, paterno, materno, nombres,
             fecha_nacimiento, sexo, estado_civil, direccion_origen, padre, madre,
             source_code, batch_id, updated_at)
            VALUES (%s, 'DNI', 'NOMBRES PATERNO MATERNO', 'PATERNO', 'MATERNO',
                    'NOMBRES', '1990-01-01', 'SIN DATO', 'SOLTERO', 'DIRECCION', %s,
                    %s, 'BASE_PERSONAS', %s, '2026-10-01 00:00:00')""",
        (documento, padre, madre, batch_id),
    )


def _batch(batch_id: int, refresh_mode: str) -> BatchRecord:
    return BatchRecord(
        batch_id=batch_id,
        tipo="SEARCH",
        estado="PROCESANDO",
        archivo_original="personas.csv",
        archivo_ruta="2026/10/personas.csv",
        archivo_extension="csv",
        archivo_sha256=None,
        perfil_version="1",
        dataset_code="PERSONAS",
        source_code="BASE_PERSONAS",
        refresh_mode=refresh_mode,
        mapping_version=1,
    )


def _gold_person(database: MySqlDatabase, documento: str) -> dict[str, object]:
    gold = database.settings.gold_database
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"""SELECT documento, padre, madre, source_code, batch_id, updated_at
                FROM `{gold}`.`search_person_index` WHERE documento = %s""",
            (documento,),
        )
        row = cursor.fetchone()

    assert row is not None
    return {
        "documento": str(row["documento"]),
        "padre": row["padre"],
        "madre": row["madre"],
        "source_code": str(row["source_code"]),
        "batch_id": int(row["batch_id"]),
        "updated_at": row["updated_at"],
    }


def _batch_state(database: MySqlDatabase, batch_id: int) -> tuple[str, int]:
    control = database.settings.control_database
    with database.connection.cursor() as cursor:
        cursor.execute(
            f"""SELECT estado, rows_published
                FROM `{control}`.`import_batch` WHERE batch_id = %s""",
            (batch_id,),
        )
        row = cursor.fetchone()

    assert row is not None
    return str(row["estado"]), int(row["rows_published"] or 0)


def _gold_parent_columns(database: MySqlDatabase) -> tuple[str, ...]:
    gold = database.settings.gold_database
    with database.connection.cursor() as cursor:
        cursor.execute(
            """SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'search_person_index'
                  AND column_name IN ('padre', 'madre')
                ORDER BY ordinal_position""",
            (gold,),
        )
        return tuple(str(row["column_name"]) for row in cursor.fetchall())


def _execute_contract_sql(database: MySqlDatabase, filename: str) -> None:
    sql = (SQL_DIRECTORY / filename).read_text(encoding="utf-8")
    sql = sql.replace("`kp_control`", f"`{database.settings.control_database}`")
    sql = sql.replace("`kp_silver`", f"`{database.settings.silver_database}`")
    sql = sql.replace("`kp_gold`", f"`{database.settings.gold_database}`")
    sql = sql.replace("'kp_control'", f"'{database.settings.control_database}'")
    sql = sql.replace("'kp_silver'", f"'{database.settings.silver_database}'")
    sql = sql.replace("'kp_gold'", f"'{database.settings.gold_database}'")
    statements = (
        "\n".join(
            line for line in statement.splitlines() if not line.lstrip().startswith("--")
        ).strip()
        for statement in sql.split(";")
    )
    with database.connection.cursor() as cursor:
        for statement in statements:
            if statement:
                cursor.execute(statement)


def _execute(database: MySqlDatabase, sql: str, values: tuple[object, ...] = ()) -> None:
    with database.connection.cursor() as cursor:
        cursor.execute(sql, values)
