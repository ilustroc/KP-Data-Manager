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

SQL_DIRECTORY = Path(__file__).resolve().parents[2] / "database" / "sql"
PERSONAS_PUBLICATION_LOCK = "kpdm:search:211b99d4f10049ef0aef57e46bf9fb957b7d8ab3"


@pytest.fixture()
def mysql_database(tmp_path: Path):
    if os.getenv("KPDM_RUN_MYSQL_INTEGRATION") != "1":
        pytest.skip(
            "Define KPDM_RUN_MYSQL_INTEGRATION=1 para ejecutar contra MySQL aislado."
        )

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
    assert _gold_parent_column_definitions(database) == {
        "padre": ("varchar(500)", "YES", "utf8mb4", "utf8mb4_unicode_ci"),
        "madre": ("varchar(500)", "YES", "utf8mb4", "utf8mb4_unicode_ci"),
    }

    _seed_gold_person(
        database,
        documento="73809323",
        batch_id=44,
        padre="VALOR ANTIGUO",
        madre="VALOR ANTIGUO",
    )
    _seed_silver_person(database, 44, "73809323", "LUCAS", "PAULA PACIZA")
    _seed_silver_person(database, 43, "73809323", "OTRO PADRE", "OTRA MADRE")

    diagnostics = _backfill_diagnostics(
        _execute_contract_sql(database, "057_backfill_search_person_index_parents.sql"),
    )

    person = _gold_person(database, "73809323")
    assert person["padre"] == "LUCAS"
    assert person["madre"] == "PAULA PACIZA"
    assert person["batch_id"] == 44
    assert diagnostics == {
        "publication_lock_acquired": 1,
        "publication_lock_released": 1,
        "gold_without_exact_silver_lineage": 0,
        "rows_updated": 1,
    }


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

    with pytest.raises(pymysql.MySQLError) as exception_info:
        _execute_contract_sql(database, "057_backfill_search_person_index_parents.sql")

    assert exception_info.value.args[0] == 30003
    assert _gold_person(database, "73809323")["padre"] == "PADRE ANTERIOR"
    assert _gold_person(database, "87654321")["madre"] == "MADRE SIN SILVER"
    assert _is_personas_publication_lock_free(database)


def test_backfill_aborts_when_personas_publication_lock_is_busy(mysql_database) -> None:
    database, _ = mysql_database
    _seed_active_source(database)
    _seed_gold_person(
        database,
        documento="73809323",
        batch_id=44,
        padre="PADRE ANTERIOR",
        madre="MADRE ANTERIOR",
    )
    _seed_silver_person(database, 44, "73809323", "LUCAS", "PAULA PACIZA")
    lock_connection = _open_lock_connection(database)

    try:
        with lock_connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0) AS lock_acquired", (PERSONAS_PUBLICATION_LOCK,))
            assert cursor.fetchone()["lock_acquired"] == 1

        with pytest.raises(pymysql.MySQLError) as exception_info:
            _execute_contract_sql(database, "057_backfill_search_person_index_parents.sql")

        assert exception_info.value.args[0] == 30002
        assert _gold_person(database, "73809323")["padre"] == "PADRE ANTERIOR"
    finally:
        with lock_connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s) AS lock_released", (PERSONAS_PUBLICATION_LOCK,))
            assert cursor.fetchone()["lock_released"] == 1
        lock_connection.close()

    assert _is_personas_publication_lock_free(database)


def test_backfill_is_idempotent_preserves_updated_at_and_null_parent_values(mysql_database) -> None:
    database, _ = mysql_database
    _seed_active_source(database)
    _seed_gold_person(
        database,
        documento="73809323",
        batch_id=44,
        padre="PADRE ANTERIOR",
        madre="MADRE ANTERIOR",
    )
    _seed_silver_person(database, 44, "73809323", None, None)
    updated_at_before = _gold_person(database, "73809323")["updated_at"]

    first_diagnostics = _backfill_diagnostics(
        _execute_contract_sql(database, "057_backfill_search_person_index_parents.sql"),
    )
    first_person = _gold_person(database, "73809323")
    second_diagnostics = _backfill_diagnostics(
        _execute_contract_sql(database, "057_backfill_search_person_index_parents.sql"),
    )
    second_person = _gold_person(database, "73809323")

    assert first_diagnostics["rows_updated"] == 1
    assert second_diagnostics["rows_updated"] == 0
    assert first_person["padre"] is None
    assert first_person["madre"] is None
    assert first_person["updated_at"] == updated_at_before
    assert second_person == first_person


def test_upgrade_aborts_before_ddl_when_existing_parent_column_is_incompatible(mysql_database) -> None:
    database, _ = mysql_database
    gold = database.settings.gold_database

    _execute(database, f"ALTER TABLE `{gold}`.`search_person_index` DROP COLUMN madre")
    _execute(
        database,
        f"ALTER TABLE `{gold}`.`search_person_index` MODIFY COLUMN padre VARCHAR(255) NULL",
    )

    with pytest.raises(pymysql.MySQLError) as exception_info:
        _execute_contract_sql(database, "056_add_search_person_index_parent_columns.sql")

    assert exception_info.value.args[0] == 30010
    assert _gold_parent_columns(database) == ("padre",)
    assert _gold_parent_column_definitions(database)["padre"][0] == "varchar(255)"


def test_contract_sql_parser_supports_delimiter_wrapped_procedures() -> None:
    upgrade_statements = _split_sql_statements(
        (SQL_DIRECTORY / "056_add_search_person_index_parent_columns.sql").read_text(
            encoding="utf-8"
        )
    )
    backfill_statements = _split_sql_statements(
        (SQL_DIRECTORY / "057_backfill_search_person_index_parents.sql").read_text(
            encoding="utf-8"
        )
    )

    assert len(upgrade_statements) == 5
    assert len(backfill_statements) == 4
    assert "DROP PROCEDURE IF EXISTS" in upgrade_statements[0]
    assert "CREATE PROCEDURE" in upgrade_statements[1]
    assert "SIGNAL SQLSTATE '45000'" in upgrade_statements[1]
    assert "END IF;" in upgrade_statements[1]
    assert "DROP PROCEDURE IF EXISTS" in backfill_statements[0]
    assert "CREATE PROCEDURE" in backfill_statements[1]
    assert "ROLLBACK;" in backfill_statements[1]
    assert "RESIGNAL;" in backfill_statements[1]
    assert "DROP PROCEDURE" in backfill_statements[-1]
    assert all(
        "DELIMITER" not in statement.upper()
        for statement in (*upgrade_statements, *backfill_statements)
    )


def test_information_schema_values_accept_mysql_column_key_capitalization() -> None:
    row = {
        "PARENT_COLUMN_NAME": "padre",
        "PARENT_COLUMN_TYPE": "varchar(500)",
        "PARENT_IS_NULLABLE": "YES",
        "PARENT_CHARACTER_SET_NAME": "utf8mb4",
        "PARENT_COLLATION_NAME": None,
    }

    assert _information_schema_value(row, "parent_column_name") == "padre"
    assert _information_schema_value(row, "parent_column_type") == "varchar(500)"
    assert _information_schema_value(row, "parent_is_nullable") == "YES"
    assert _nullable_information_schema_value(row, "parent_character_set_name") == "utf8mb4"
    assert _nullable_information_schema_value(row, "parent_collation_name") is None


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
    padre: str | None,
    madre: str | None,
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
    padre: str | None,
    madre: str | None,
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
            """SELECT column_name AS parent_column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'search_person_index'
                  AND column_name IN ('padre', 'madre')
                ORDER BY ordinal_position""",
            (gold,),
        )
        return tuple(
            str(_information_schema_value(row, "parent_column_name"))
            for row in cursor.fetchall()
        )


def _gold_parent_column_definitions(
    database: MySqlDatabase,
) -> dict[str, tuple[str, str, str | None, str | None]]:
    gold = database.settings.gold_database
    with database.connection.cursor() as cursor:
        cursor.execute(
            """SELECT
                    column_name AS parent_column_name,
                    column_type AS parent_column_type,
                    is_nullable AS parent_is_nullable,
                    character_set_name AS parent_character_set_name,
                    collation_name AS parent_collation_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'search_person_index'
                  AND column_name IN ('padre', 'madre')
                ORDER BY ordinal_position""",
            (gold,),
        )
        rows = cursor.fetchall()

    return {
        str(_information_schema_value(row, "parent_column_name")): (
            str(_information_schema_value(row, "parent_column_type")),
            str(_information_schema_value(row, "parent_is_nullable")),
            _nullable_information_schema_value(row, "parent_character_set_name"),
            _nullable_information_schema_value(row, "parent_collation_name"),
        )
        for row in rows
    }


def _information_schema_value(row: dict[str, object], key: str) -> object:
    for actual_key, value in row.items():
        if actual_key.casefold() == key.casefold():
            return value

    raise KeyError(key)


def _nullable_information_schema_value(row: dict[str, object], key: str) -> str | None:
    value = _information_schema_value(row, key)

    return None if value is None else str(value)


def _is_personas_publication_lock_free(database: MySqlDatabase) -> bool:
    with database.connection.cursor() as cursor:
        cursor.execute("SELECT IS_FREE_LOCK(%s) AS lock_is_free", (PERSONAS_PUBLICATION_LOCK,))
        row = cursor.fetchone()

    assert row is not None

    return row["lock_is_free"] == 1


def _open_lock_connection(database: MySqlDatabase) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=database.settings.db_host,
        port=database.settings.db_port,
        user=database.settings.db_username,
        password=database.settings.db_password,
        database=database.settings.gold_database,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _backfill_diagnostics(
    result_sets: list[list[dict[str, object]]],
) -> dict[str, int]:
    for result_set in reversed(result_sets):
        if result_set and "rows_updated" in result_set[0]:
            return {
                key: int(value)
                for key, value in result_set[0].items()
                if key in {
                    "publication_lock_acquired",
                    "publication_lock_released",
                    "gold_without_exact_silver_lineage",
                    "rows_updated",
                }
            }

    raise AssertionError("El backfill no devolvió sus diagnósticos esperados.")


def _execute_contract_sql(
    database: MySqlDatabase,
    filename: str,
) -> list[list[dict[str, object]]]:
    sql = (SQL_DIRECTORY / filename).read_text(encoding="utf-8")
    sql = sql.replace("`kp_control`", f"`{database.settings.control_database}`")
    sql = sql.replace("`kp_silver`", f"`{database.settings.silver_database}`")
    sql = sql.replace("`kp_gold`", f"`{database.settings.gold_database}`")
    sql = sql.replace("'kp_control'", f"'{database.settings.control_database}'")
    sql = sql.replace("'kp_silver'", f"'{database.settings.silver_database}'")
    sql = sql.replace("'kp_gold'", f"'{database.settings.gold_database}'")
    result_sets: list[list[dict[str, object]]] = []

    with database.connection.cursor() as cursor:
        for statement in _split_sql_statements(sql):
            cursor.execute(statement)

            if cursor.description is not None:
                result_sets.append(list(cursor.fetchall()))

            while cursor.nextset():
                if cursor.description is not None:
                    result_sets.append(list(cursor.fetchall()))

    return result_sets


def _split_sql_statements(sql: str) -> tuple[str, ...]:
    delimiter = ";"
    statements: list[str] = []
    current_lines: list[str] = []

    for line in sql.splitlines():
        stripped = line.strip()

        if stripped.upper().startswith("DELIMITER "):
            if _sql_content(current_lines):
                raise AssertionError("DELIMITER no puede aparecer dentro de una sentencia SQL.")
            delimiter = stripped.split(maxsplit=1)[1]
            continue

        current_lines.append(line)
        current_statement = "\n".join(current_lines).rstrip()

        if current_statement.endswith(delimiter):
            statement = current_statement[: -len(delimiter)].strip()
            if statement:
                statements.append(statement)
            current_lines = []

    if _sql_content(current_lines):
        raise AssertionError("El script SQL terminó sin su delimitador final.")

    return tuple(statements)


def _sql_content(lines: list[str]) -> str:
    return "\n".join(
        line for line in lines if not line.lstrip().startswith("--")
    ).strip()


def _execute(database: MySqlDatabase, sql: str, values: tuple[object, ...] = ()) -> None:
    with database.connection.cursor() as cursor:
        cursor.execute(sql, values)
