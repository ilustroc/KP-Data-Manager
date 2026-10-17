from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest
import pymysql

from src.db import MySqlDatabase
from src.domain.models import ProcessingStats

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
    ) -> None:
        self.fail_gold_insert = fail_gold_insert
        self.other_gold_source = other_gold_source
        self.modes_allowed = modes_allowed
        self.active_source = active_source
        self.batch_status = batch_status
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
        if "SELECT estado, filas_archivo" in sql:
            return {
                "estado": self.batch_status,
                "filas_archivo": 1,
                "rows_valid": 1,
                "rows_invalid": 0,
                "scope_count": 1,
            }
        if "SELECT DISTINCT source_code" in sql:
            return {"source_code": "OTRA_FUENTE"} if self.other_gold_source else None
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
    ) -> None:
        self.publication_cursor = PublicationCursor(
            fail_gold_insert=fail_gold_insert,
            other_gold_source=other_gold_source,
            modes_allowed=modes_allowed,
            active_source=active_source,
            batch_status=batch_status,
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
            return {"source_code": "BASE_ESSALUD", "allows_full_replace": 1, "allows_scope_replace": 1}
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
    assert "WHERE batch_id <> %s" in sql
    assert "REPLACE INTO" not in sql
    assert "INSERT IGNORE" not in sql


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
    assert "DELETE FROM `kp_gold_test`.`search_telefonos` WHERE batch_id <> %s" in sql
    assert "TRUNCATE" not in sql and "REPLACE INTO" not in sql and "INSERT IGNORE" not in sql


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
