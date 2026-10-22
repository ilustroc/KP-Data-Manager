from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime

import pytest
import pymysql

from src.db import MySqlDatabase
from src.domain.models import ProcessingStats
from src.metrics import SearchMetrics

from .conftest import make_batch


class PublicationCursor:
    def __init__(
        self,
        *,
        fail_gold_insert: bool = False,
        other_gold_source: bool = False,
        modes_allowed: bool = True,
        active_source: str = "BASE_PERSONAS",
        batch_status: str = "PROCESANDO",
        lock_acquired: bool = True,
    ) -> None:
        self.fail_gold_insert = fail_gold_insert
        self.other_gold_source = other_gold_source
        self.modes_allowed = modes_allowed
        self.active_source = active_source
        self.batch_status = batch_status
        self.lock_acquired = lock_acquired
        self.last_sql = ""
        self.executed: list[str] = []
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def execute(self, sql: str, values=()) -> int:
        self.last_sql = " ".join(sql.split())
        self.executed.append(self.last_sql)
        if self.fail_gold_insert and "INSERT INTO `kp_gold_test`.`search_person_index`" in sql:
            raise RuntimeError("simulated Gold failure")
        self.rowcount = 1
        return 1

    def fetchone(self):
        sql = self.last_sql
        if "GET_LOCK" in sql:
            return {"lock_acquired": int(self.lock_acquired)}
        if "RELEASE_LOCK" in sql:
            return {"lock_released": 1}
        if "SELECT estado, filas_archivo" in sql:
            return {
                "estado": self.batch_status,
                "filas_archivo": 1,
                "rows_valid": 1,
                "rows_invalid": 0,
                "scope_count": 1,
            }
        if "source_code <> %s" in sql:
            return {"found": 1} if self.other_gold_source else None
        if "SELECT 1 AS found" in sql:
            return None
        if "COUNT(*) AS total" in sql:
            if "IS NULL" in sql:
                return {"total": 0}
            return {"total": 1}
        return None

    def fetchall(self):
        if "FROM `kp_control_test`.`import_dataset_source`" in self.last_sql:
            return [
                {
                    "source_code": self.active_source,
                    "allows_full_replace": int(self.modes_allowed),
                    "allows_scope_replace": int(self.modes_allowed),
                    "allows_upsert": int(self.modes_allowed),
                }
            ]
        return []


class PublicationConnection:
    def __init__(
        self,
        *,
        fail_gold_insert: bool = False,
        other_gold_source: bool = False,
        modes_allowed: bool = True,
        active_source: str = "BASE_PERSONAS",
        batch_status: str = "PROCESANDO",
        lock_acquired: bool = True,
    ) -> None:
        self.publication_cursor = PublicationCursor(
            fail_gold_insert=fail_gold_insert,
            other_gold_source=other_gold_source,
            modes_allowed=modes_allowed,
            active_source=active_source,
            batch_status=batch_status,
            lock_acquired=lock_acquired,
        )
        self.began = False
        self.committed = False
        self.rolled_back = False

    def begin(self) -> None:
        self.began = True

    def cursor(self):
        return self.publication_cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class RecoveryPreflightCursor:
    def __init__(
        self,
        *,
        rows_invalid: int = 0,
        bronze_count: int = 2,
        silver_count: int = 2,
        scope_count: int = 1,
        source_active: bool = True,
    ) -> None:
        self.rows_invalid = rows_invalid
        self.bronze_count = bronze_count
        self.silver_count = silver_count
        self.scope_count = scope_count
        self.source_active = source_active
        self.last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def execute(self, sql: str, values=()) -> int:
        self.last_sql = " ".join(sql.split())
        return 1

    def fetchone(self):
        if "filas_duplicadas" in self.last_sql:
            return {
                "estado": "PROCESANDO",
                "filas_archivo": 2,
                "filas_duplicadas": 0,
                "rows_valid": 2,
                "rows_invalid": self.rows_invalid,
                "scope_count": 1,
            }
        if "search_raw_row" in self.last_sql:
            return {"total": self.bronze_count}
        if "import_scope_document" in self.last_sql:
            return {"total": self.scope_count}
        if "search_laboral_essalud" in self.last_sql:
            return {"total": self.silver_count}
        if "import_dataset_source" in self.last_sql:
            if not self.source_active:
                return None
            return {
                "source_code": "BASE_ESSALUD",
                "allows_full_replace": 1,
                "allows_scope_replace": 1,
                "allows_upsert": 0,
            }
        return None


class RecoveryPreflightConnection:
    def __init__(self, cursor: RecoveryPreflightCursor) -> None:
        self.recovery_cursor = cursor

    def cursor(self):
        return self.recovery_cursor


class FailingRecoveryPreflightCursor:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        self.closed = True

        return False

    def execute(self, sql: str, values=()) -> int:
        raise pymysql.err.InterfaceError(0, "sensitive driver message")


class RecoveryCleanupConnection:
    def __init__(self, *, fail_rollback: bool = False, fail_close: bool = False) -> None:
        self.recovery_cursor = FailingRecoveryPreflightCursor()
        self.fail_rollback = fail_rollback
        self.fail_close = fail_close
        self.begin_calls = 0
        self.rollback_calls = 0
        self.closed = False

    def begin(self) -> None:
        self.begin_calls += 1

    def cursor(self):
        return self.recovery_cursor

    def rollback(self) -> None:
        self.rollback_calls += 1
        if self.fail_rollback:
            raise RuntimeError("rollback unavailable")

    def close(self) -> None:
        self.closed = True
        if self.fail_close:
            raise RuntimeError("close unavailable")


class SessionSetupFailureConnection:
    def __init__(self) -> None:
        self.recovery_cursor = FailingRecoveryPreflightCursor()
        self.closed = False

    def cursor(self):
        return self.recovery_cursor

    def close(self) -> None:
        self.closed = True


def database_with_connection(settings, connection: object) -> MySqlDatabase:
    database = object.__new__(MySqlDatabase)
    database.settings = settings
    database.connection = connection
    database.connection_phase = "ready"
    database._transaction_active = False
    database.last_cleanup_error_type = None

    return database


def batch(refresh_mode: str):
    return make_batch(
        tipo="SEARCH",
        perfil_version="1",
        dataset_code="PERSONAS",
        source_code="BASE_PERSONAS",
        refresh_mode=refresh_mode,
        mapping_version=1,
    )


def phone_batch(refresh_mode: str):
    return make_batch(
        tipo="SEARCH",
        perfil_version="1",
        dataset_code="TELEFONOS",
        source_code="BASE_TELEFONOS",
        refresh_mode=refresh_mode,
        mapping_version=1,
    )


def family_batch(refresh_mode: str):
    return make_batch(
        tipo="SEARCH",
        perfil_version="1",
        dataset_code="FAMILIA",
        source_code="BASE_FAMILIA",
        refresh_mode=refresh_mode,
        mapping_version=1,
    )


def essalud_batch(refresh_mode: str):
    return make_batch(
        tipo="SEARCH",
        perfil_version="1",
        dataset_code="LABORAL_ESSALUD",
        source_code="BASE_ESSALUD",
        refresh_mode=refresh_mode,
        mapping_version=1,
    )


def test_scope_replace_uses_official_scope_and_single_transaction(settings):
    connection = PublicationConnection()
    database = database_with_connection(settings, connection)

    database.publish_search(
        batch("SCOPE_REPLACE"),
        datetime(2026, 10, 14, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    sql = "\n".join(connection.publication_cursor.executed)
    assert connection.began and connection.committed and not connection.rolled_back
    assert "INNER JOIN `kp_control_test`.`import_scope_document`" in sql
    assert "WHERE scope.batch_id = %s" in sql
    assert "FOR UPDATE" in sql


def test_search_gold_is_applied_before_import_batch_is_locked(settings):
    connection = PublicationConnection()
    database = database_with_connection(settings, connection)

    database.publish_search(
        batch("FULL_REPLACE"),
        datetime(2026, 10, 14, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    executed = connection.publication_cursor.executed
    gold_insert_index = next(
        index
        for index, sql in enumerate(executed)
        if "INSERT INTO `kp_gold_test`.`search_person_index`" in sql
    )
    batch_lock_index = next(
        index
        for index, sql in enumerate(executed)
        if "FROM `kp_control_test`.`import_batch`" in sql and "FOR UPDATE" in sql
    )
    metadata_update_index = next(
        index
        for index, sql in enumerate(executed)
        if "UPDATE `kp_control_test`.`import_batch`" in sql
    )

    assert gold_insert_index < batch_lock_index < metadata_update_index
    assert connection.committed and not connection.rolled_back


def test_heavy_integrity_validation_finishes_before_import_batch_lock(settings):
    connection = PublicationConnection(active_source="BASE_FAMILIA")
    database = database_with_connection(settings, connection)

    database.publish_search(
        family_batch("FULL_REPLACE"),
        datetime(2026, 10, 16, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    executed = connection.publication_cursor.executed
    lock_index = next(
        index
        for index, sql in enumerate(executed)
        if "FROM `kp_control_test`.`import_batch`" in sql and "FOR UPDATE" in sql
    )
    integrity_indexes = [
        index
        for index, sql in enumerate(executed)
        if "COUNT(*) AS total" in sql or "SELECT 1 AS found" in sql
    ]

    assert integrity_indexes
    assert max(integrity_indexes) < lock_index


def test_publication_is_serialized_by_dataset_source_advisory_lock(settings):
    connection = PublicationConnection(active_source="BASE_FAMILIA")
    database = database_with_connection(settings, connection)

    database.publish_search(
        family_batch("FULL_REPLACE"),
        datetime(2026, 10, 16, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    executed = connection.publication_cursor.executed

    assert "GET_LOCK" in executed[0]
    assert "RELEASE_LOCK" in executed[-1]
    assert connection.began and connection.committed and not connection.rolled_back


def test_publication_stops_before_transaction_when_dataset_source_lock_is_busy(settings):
    connection = PublicationConnection(
        active_source="BASE_FAMILIA",
        lock_acquired=False,
    )
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="Otra publicación SEARCH"):
        database.publish_search(
            family_batch("FULL_REPLACE"),
            datetime(2026, 10, 16, 12, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert connection.began is False
    assert connection.committed is False
    assert connection.rolled_back is False
    assert all("RELEASE_LOCK" not in sql for sql in connection.publication_cursor.executed)


def test_publication_queries_use_existing_source_batch_indexes(settings):
    connection = PublicationConnection(active_source="BASE_FAMILIA")
    database = database_with_connection(settings, connection)

    database.publish_search(
        family_batch("FULL_REPLACE"),
        datetime(2026, 10, 16, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    sql = "\n".join(connection.publication_cursor.executed)

    assert "WHERE source_code = %s AND batch_id <> %s" in sql
    assert "WHERE source_code = %s AND batch_id = %s" in sql
    assert "WHERE dataset_code = %s AND source_code = %s AND batch_id = %s" in sql
    assert "SELECT DISTINCT source_code" not in sql
    assert "SELECT 1 AS found" in sql
    assert "LIMIT 1" in sql


def test_completed_batch_detected_at_final_lock_rolls_back_duplicate_recovery_work(settings):
    connection = PublicationConnection(batch_status="COMPLETADO")
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="dejó de estar publicable"):
        database.publish_search(
            batch("FULL_REPLACE"),
            datetime(2026, 10, 14, 12, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
            recovery=True,
        )

    sql = "\n".join(connection.publication_cursor.executed)
    assert "INSERT INTO `kp_gold_test`.`search_person_index`" in sql
    assert connection.committed is False
    assert connection.rolled_back is True


def test_database_connection_uses_configured_client_timeouts(settings, monkeypatch):
    captured: dict[str, object] = {}

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exception_type, exception, traceback):
            return False

        def execute(self, sql: str, values=()) -> int:
            return 1

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self) -> None:
            return None

    def connect(**kwargs):
        captured.update(kwargs)

        return Connection()

    monkeypatch.setattr("src.db.pymysql.connect", connect)
    database = MySqlDatabase(
        replace(
            settings,
            db_connect_timeout=17,
            db_read_timeout=600,
            db_write_timeout=601,
        )
    )

    assert captured["connect_timeout"] == 17
    assert captured["read_timeout"] == 600
    assert captured["write_timeout"] == 601
    assert database.close() is True


def test_full_replace_uses_upsert_then_removes_only_stale_batch_rows(settings):
    connection = PublicationConnection()
    database = database_with_connection(settings, connection)

    database.publish_search(
        batch("FULL_REPLACE"),
        datetime(2026, 10, 14, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    sql = "\n".join(connection.publication_cursor.executed)
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert "WHERE source_code = %s AND batch_id <> %s" in sql
    assert "REPLACE INTO" not in sql
    assert "INSERT IGNORE" not in sql


def test_personas_gold_publication_includes_and_updates_parents(settings):
    connection = PublicationConnection()
    database = database_with_connection(settings, connection)

    database.publish_search(
        batch("FULL_REPLACE"),
        datetime(2026, 10, 22, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    publication_sql = next(
        sql
        for sql in connection.publication_cursor.executed
        if "INSERT INTO `kp_gold_test`.`search_person_index`" in sql
    )

    assert "`padre`, `madre`, `source_code`" in publication_sql
    assert "padre, madre, source_code, batch_id" in publication_sql
    assert "padre = VALUES(padre)" in publication_sql
    assert "madre = VALUES(madre)" in publication_sql


def test_gold_delete_metric_uses_affected_row_count(settings, caplog):
    connection = PublicationConnection()
    database = database_with_connection(settings, connection)
    metrics = SearchMetrics(
        123,
        "PERSONAS",
        "FULL_REPLACE",
        memory_probe=lambda: None,
    )

    database.publish_search(
        batch("FULL_REPLACE"),
        datetime(2026, 10, 14, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        metrics=metrics,
    )
    with caplog.at_level("INFO", logger="kpdm.etl.search"):
        metrics.emit(logging.getLogger("kpdm.etl.search"), successful=True)

    delete_metric = next(
        record.context
        for record in caplog.records
        if record.message == "search_phase_metric"
        and record.context["phase"] == "gold_delete"
    )

    assert delete_metric["rows_processed"] == 1


def test_gold_failure_rolls_back_cross_schema_publication(settings):
    connection = PublicationConnection(fail_gold_insert=True)
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="simulated Gold failure"):
        database.publish_search(
            batch("SCOPE_REPLACE"),
            datetime(2026, 10, 14, 12, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert connection.began is True
    assert connection.committed is False
    assert connection.rolled_back is True


def test_second_personas_source_in_gold_is_blocked_without_implicit_precedence(settings):
    connection = PublicationConnection(other_gold_source=True)
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="otra fuente"):
        database.publish_search(
            batch("SCOPE_REPLACE"),
            datetime(2026, 10, 14, 12, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert connection.committed is False
    assert connection.rolled_back is True


def test_publication_rolls_back_when_refresh_mode_is_no_longer_authorized(settings):
    connection = PublicationConnection(modes_allowed=False)
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="dejó de estar autorizado"):
        database.publish_search(
            batch("FULL_REPLACE"),
            datetime(2026, 10, 14, 12, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert connection.committed is False
    assert connection.rolled_back is True


def test_phone_scope_replace_deletes_only_documents_in_official_scope(settings):
    connection = PublicationConnection(active_source="BASE_TELEFONOS")
    database = database_with_connection(settings, connection)

    database.publish_search(
        phone_batch("SCOPE_REPLACE"),
        datetime(2026, 10, 15, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    sql = "\n".join(connection.publication_cursor.executed)
    assert "DELETE gold FROM `kp_gold_test`.`search_telefonos` AS gold" in sql
    assert "INNER JOIN `kp_control_test`.`import_scope_document` AS scope" in sql
    assert "INSERT INTO `kp_gold_test`.`search_telefonos`" in sql
    assert connection.committed and not connection.rolled_back


def test_phone_full_replace_is_set_based_and_removes_stale_gold_in_same_transaction(settings):
    connection = PublicationConnection(active_source="BASE_TELEFONOS")
    database = database_with_connection(settings, connection)

    database.publish_search(
        phone_batch("FULL_REPLACE"),
        datetime(2026, 10, 15, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    sql = "\n".join(connection.publication_cursor.executed)
    assert "INSERT INTO `kp_gold_test`.`search_telefonos`" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert "DELETE FROM `kp_gold_test`.`search_telefonos` WHERE source_code = %s AND batch_id <> %s" in sql
    assert "TRUNCATE" not in sql and "REPLACE INTO" not in sql and "INSERT IGNORE" not in sql


def test_phone_upsert_inserts_new_pairs_and_updates_existing_pair_metadata_set_based(settings):
    connection = PublicationConnection(active_source="BASE_TELEFONOS")
    database = database_with_connection(settings, connection)

    database.publish_search(
        phone_batch("UPSERT"),
        datetime(2026, 10, 20, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    sql = "\n".join(connection.publication_cursor.executed)
    assert "INSERT INTO `kp_gold_test`.`search_telefonos`" in sql
    assert "FROM `kp_silver_test`.`search_telefonos`" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert "operador = VALUES(operador)" in sql
    assert "fecha_data = VALUES(fecha_data)" in sql
    assert "source_code = VALUES(source_code)" in sql
    assert "batch_id = VALUES(batch_id)" in sql
    assert "updated_at = VALUES(updated_at)" in sql
    assert connection.committed and not connection.rolled_back


def test_phone_upsert_preserves_phones_missing_from_file_and_other_documents(settings):
    connection = PublicationConnection(active_source="BASE_TELEFONOS")
    database = database_with_connection(settings, connection)

    database.publish_search(
        phone_batch("UPSERT"),
        datetime(2026, 10, 20, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    sql = "\n".join(connection.publication_cursor.executed)
    assert "DELETE FROM `kp_gold_test`.`search_telefonos`" not in sql
    assert "DELETE gold FROM `kp_gold_test`.`search_telefonos`" not in sql
    assert "TRUNCATE" not in sql


def test_phone_upsert_is_idempotent_when_the_same_batch_is_published_again(settings):
    connection = PublicationConnection(active_source="BASE_TELEFONOS")
    database = database_with_connection(settings, connection)
    current_batch = phone_batch("UPSERT")
    stats = ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1)

    database.publish_search(current_batch, datetime(2026, 10, 20, 12, 0), stats)
    database.publish_search(current_batch, datetime(2026, 10, 20, 12, 1), stats)

    inserts = [
        sql
        for sql in connection.publication_cursor.executed
        if "INSERT INTO `kp_gold_test`.`search_telefonos`" in sql
    ]
    assert len(inserts) == 2
    assert all("ON DUPLICATE KEY UPDATE" in sql for sql in inserts)
    assert all("DELETE" not in sql for sql in inserts)


def test_upsert_is_rejected_for_non_phone_dataset_before_transaction(settings):
    connection = PublicationConnection()
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="únicamente para TELEFONOS"):
        database.publish_search(
            batch("UPSERT"),
            datetime(2026, 10, 20, 12, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert connection.began is False
    assert connection.committed is False
    assert connection.rolled_back is False


def test_phone_gold_failure_rolls_back_without_partial_publication(settings):
    connection = PublicationConnection(
        fail_gold_insert=True,
        active_source="BASE_TELEFONOS",
    )
    connection.publication_cursor.fail_gold_insert = False
    database = database_with_connection(settings, connection)
    original_execute = connection.publication_cursor.execute

    def fail_phone_insert(sql, values=()):
        if "INSERT INTO `kp_gold_test`.`search_telefonos`" in sql:
            raise RuntimeError("simulated Gold failure")
        return original_execute(sql, values)

    connection.publication_cursor.execute = fail_phone_insert
    with pytest.raises(RuntimeError, match="simulated Gold failure"):
        database.publish_search(
            phone_batch("SCOPE_REPLACE"),
            datetime(2026, 10, 15, 12, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert connection.committed is False
    assert connection.rolled_back is True


def test_phone_upsert_failure_rolls_back_without_partial_publication(settings):
    connection = PublicationConnection(active_source="BASE_TELEFONOS")
    database = database_with_connection(settings, connection)
    original_execute = connection.publication_cursor.execute

    def fail_phone_insert(sql, values=()):
        if "INSERT INTO `kp_gold_test`.`search_telefonos`" in sql:
            raise RuntimeError("simulated Gold failure")
        return original_execute(sql, values)

    connection.publication_cursor.execute = fail_phone_insert

    with pytest.raises(RuntimeError, match="simulated Gold failure"):
        database.publish_search(
            phone_batch("UPSERT"),
            datetime(2026, 10, 20, 12, 0),
            ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        )

    assert connection.committed is False
    assert connection.rolled_back is True


@pytest.mark.parametrize("refresh_mode", ["FULL_REPLACE", "SCOPE_REPLACE"])
def test_essalud_integrity_validation_converts_only_the_non_indexed_document_side(
    settings,
    refresh_mode,
):
    connection = PublicationConnection(active_source="BASE_ESSALUD")
    database = database_with_connection(settings, connection)

    database.publish_search(
        essalud_batch(refresh_mode),
        datetime(2026, 10, 21, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    integrity_queries = [
        statement
        for statement in connection.publication_cursor.executed
        if "scope.id IS NULL" in statement or "silver.employment_id IS NULL" in statement
    ]
    sql = "\n".join(integrity_queries)

    assert "scope.documento = (CONVERT(silver.documento USING utf8mb4) COLLATE utf8mb4_unicode_ci)" in sql
    assert "silver.documento = (CONVERT(scope.documento USING ascii) COLLATE ascii_bin)" in sql
    assert len(integrity_queries) == 2
    assert connection.committed and not connection.rolled_back


def test_non_essalud_integrity_validation_keeps_the_existing_document_comparisons(settings):
    connection = PublicationConnection(active_source="BASE_TELEFONOS")
    database = database_with_connection(settings, connection)

    database.publish_search(
        phone_batch("FULL_REPLACE"),
        datetime(2026, 10, 21, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    sql = "\n".join(connection.publication_cursor.executed)

    assert "scope.documento = silver.documento" in sql
    assert "silver.documento = scope.documento" in sql
    assert "CONVERT(scope.documento USING ascii)" not in sql
    assert "CONVERT(silver.documento USING utf8mb4)" not in sql


def test_essalud_publish_only_recovery_uses_the_optimized_integrity_validation(settings):
    connection = PublicationConnection(active_source="BASE_ESSALUD", batch_status="ERROR")
    database = database_with_connection(settings, connection)

    database.publish_search(
        essalud_batch("FULL_REPLACE"),
        datetime(2026, 10, 21, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        recovery=True,
    )

    sql = "\n".join(connection.publication_cursor.executed)

    assert "estado IN ('PROCESANDO', 'ERROR')" in sql
    assert "silver.documento = (CONVERT(scope.documento USING ascii) COLLATE ascii_bin)" in sql
    assert connection.committed and not connection.rolled_back


@pytest.mark.parametrize("refresh_mode", ["FULL_REPLACE", "SCOPE_REPLACE"])
def test_family_publication_preserves_source_row_identity_and_uses_the_transactional_publisher(settings, refresh_mode):
    connection = PublicationConnection(active_source="BASE_FAMILIA")
    database = database_with_connection(settings, connection)

    database.publish_search(
        family_batch(refresh_mode),
        datetime(2026, 10, 16, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
    )

    sql = "\n".join(connection.publication_cursor.executed)
    assert "INSERT INTO `kp_gold_test`.`search_familiares`" in sql
    assert "source_row_number" in sql
    if refresh_mode == "FULL_REPLACE":
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert "DELETE FROM `kp_gold_test`.`search_familiares` WHERE source_code = %s AND batch_id <> %s" in sql
    else:
        assert "DELETE gold FROM `kp_gold_test`.`search_familiares` AS gold" in sql
        assert "INNER JOIN `kp_control_test`.`import_scope_document` AS scope" in sql
    assert connection.committed and not connection.rolled_back


def test_publish_only_recovery_allows_error_batch_and_uses_the_same_transactional_publisher(settings):
    connection = PublicationConnection(active_source="BASE_TELEFONOS", batch_status="ERROR")
    database = database_with_connection(settings, connection)

    database.publish_search(
        phone_batch("FULL_REPLACE"),
        datetime(2026, 10, 15, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        recovery=True,
    )

    sql = "\n".join(connection.publication_cursor.executed)
    assert "estado IN ('PROCESANDO', 'ERROR')" in sql
    assert "INSERT INTO `kp_gold_test`.`search_telefonos`" in sql
    assert connection.committed and not connection.rolled_back


def test_phone_upsert_recovery_is_idempotent_and_never_deletes_gold(settings):
    connection = PublicationConnection(
        active_source="BASE_TELEFONOS",
        batch_status="ERROR",
    )
    database = database_with_connection(settings, connection)

    database.publish_search(
        phone_batch("UPSERT"),
        datetime(2026, 10, 20, 12, 0),
        ProcessingStats(file_rows=1, inserted_rows=1, scope_count=1),
        recovery=True,
    )

    sql = "\n".join(connection.publication_cursor.executed)
    assert "estado IN ('PROCESANDO', 'ERROR')" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert "DELETE FROM `kp_gold_test`.`search_telefonos`" not in sql
    assert "DELETE gold FROM `kp_gold_test`.`search_telefonos`" not in sql
    assert connection.committed and not connection.rolled_back


def recovery_batch():
    return make_batch(
        tipo="SEARCH",
        status="PROCESANDO",
        perfil_version="1",
        dataset_code="LABORAL_ESSALUD",
        source_code="BASE_ESSALUD",
        refresh_mode="FULL_REPLACE",
        mapping_version=1,
    )


def test_recovery_preflight_uses_persisted_counts_without_writing_history(settings):
    cursor = RecoveryPreflightCursor()
    database = database_with_connection(settings, RecoveryPreflightConnection(cursor))

    stats = database.preflight_search_recovery(recovery_batch())

    assert stats == ProcessingStats(file_rows=2, inserted_rows=2, scope_count=1)
    assert "INSERT" not in cursor.last_sql and "UPDATE" not in cursor.last_sql


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"rows_invalid": 1}, "filas inválidas"),
        ({"bronze_count": 1}, "Bronze no coincide"),
        ({"silver_count": 1}, "Silver no coincide"),
        ({"scope_count": 0}, "scope no coincide"),
        ({"source_active": False}, "fuente SEARCH no está activa"),
    ],
)
def test_recovery_preflight_rejects_inconsistent_or_unauthorized_batches(settings, kwargs, message):
    cursor = RecoveryPreflightCursor(**kwargs)
    database = database_with_connection(settings, RecoveryPreflightConnection(cursor))

    with pytest.raises(RuntimeError, match=message):
        database.preflight_search_recovery(recovery_batch())


def test_recovery_preflight_interface_error_closes_cursor_and_cleans_active_transaction(settings):
    connection = RecoveryCleanupConnection()
    database = database_with_connection(settings, connection)
    database._transaction_active = True

    with pytest.raises(pymysql.err.InterfaceError) as exception:
        database.preflight_search_recovery(recovery_batch())

    assert exception.value.args[0] == 0
    assert connection.recovery_cursor.closed is True
    assert connection.begin_calls == 0
    assert database.close() is True
    assert connection.rollback_calls == 1
    assert connection.closed is True
    assert database._transaction_active is False


def test_failed_rollback_does_not_replace_the_original_recovery_preflight_error(settings):
    connection = RecoveryCleanupConnection(fail_rollback=True)
    database = database_with_connection(settings, connection)
    database._transaction_active = True

    with pytest.raises(pymysql.err.InterfaceError) as exception:
        database.preflight_search_recovery(recovery_batch())

    assert exception.value.args[0] == 0
    assert database.close() is True
    assert connection.rollback_calls == 1
    assert connection.closed is True
    assert database.last_cleanup_error_type == "RuntimeError"


def test_connection_close_failure_is_contained_after_recovery_preflight_error(settings):
    connection = RecoveryCleanupConnection(fail_close=True)
    database = database_with_connection(settings, connection)

    with pytest.raises(pymysql.err.InterfaceError):
        database.preflight_search_recovery(recovery_batch())

    assert database.close() is False
    assert connection.closed is True
    assert database.last_cleanup_error_type == "RuntimeError"


def test_connection_is_closed_when_session_setup_raises_interface_error(settings, monkeypatch):
    connection = SessionSetupFailureConnection()
    monkeypatch.setattr("src.db.pymysql.connect", lambda **kwargs: connection)

    with pytest.raises(pymysql.err.InterfaceError):
        MySqlDatabase(settings)

    assert connection.recovery_cursor.closed is True
    assert connection.closed is True
