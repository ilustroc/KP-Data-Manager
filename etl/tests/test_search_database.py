from __future__ import annotations

from datetime import datetime

import pytest

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
    ) -> None:
        self.fail_gold_insert = fail_gold_insert
        self.other_gold_source = other_gold_source
        self.modes_allowed = modes_allowed
        self.active_source = active_source
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
                "estado": "PROCESANDO",
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
    ) -> None:
        self.publication_cursor = PublicationCursor(
            fail_gold_insert=fail_gold_insert,
            other_gold_source=other_gold_source,
            modes_allowed=modes_allowed,
            active_source=active_source,
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


def database_with_connection(settings, connection: PublicationConnection) -> MySqlDatabase:
    database = object.__new__(MySqlDatabase)
    database.settings = settings
    database.connection = connection
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
