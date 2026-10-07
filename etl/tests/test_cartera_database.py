from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from src.db import MySqlDatabase
from src.domain.models import (
    CAJA_AREQUIPA_BRONZE_COLUMNS,
    CAJA_AREQUIPA_SOURCE_COLUMNS,
    CellValue,
    SourceRow,
)
from src.profiles.carteras.caja_arequipa import CajaArequipaV1Profile


class RecordingCursor:
    def __init__(self, *, fail_table: str | None = None) -> None:
        self.fail_table = fail_table
        self.last_sql = ""
        self.executed_many: list[tuple[str, list[tuple[object, ...]]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False

    def executemany(self, sql: str, values) -> None:
        rows = list(values)
        if self.fail_table is not None and self.fail_table in sql:
            raise RuntimeError("simulated database failure")
        self.executed_many.append((sql, rows))

    def execute(self, sql: str, values) -> None:
        self.last_sql = sql

    def fetchall(self):
        if "raw_cartera_caja_arequipa" in self.last_sql:
            return [{"raw_id": 77, "source_row": 2}]
        if "cartera_operaciones" in self.last_sql:
            return [{"id": 88, "source_raw_id": 77}]
        return []


class RecordingConnection:
    def __init__(self, *, fail_table: str | None = None) -> None:
        self.recording_cursor = RecordingCursor(fail_table=fail_table)
        self.began = False
        self.committed = False
        self.rolled_back = False

    def begin(self) -> None:
        self.began = True

    def cursor(self) -> RecordingCursor:
        return self.recording_cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def caja_record():
    values = {column: CellValue(None) for column in CAJA_AREQUIPA_SOURCE_COLUMNS}
    values.update(
        {
            "NRO_DOC_TIT_1": CellValue("00001234"),
            "NRO_DOC_TIT_2": CellValue("00001234"),
            "CUENTA": CellValue("001"),
            "OPERACION": CellValue("002"),
            "TEL_TIT": CellValue("900111222"),
            "DIR_LEGAL": CellValue("Dirección sintética"),
            "NOM_AVAL": CellValue("Aval sintético"),
            "TIP_GAR1": CellValue("HIPOTECA"),
            "MTO_GAR1": CellValue("1000.00"),
        }
    )
    record, errors = CajaArequipaV1Profile().normalize(
        SourceRow(2, values),
        batch_id=44,
        source_file="caja.xlsx",
        ingested_at=datetime(2026, 10, 6, 20, 0, 0),
        error_value_max_length=100,
    )
    assert errors == [] and record is not None
    return record


def database_with_connection(settings, connection: RecordingConnection) -> MySqlDatabase:
    database = MySqlDatabase.__new__(MySqlDatabase)
    database.settings = settings
    database.connection = connection
    return database


def test_caja_chunk_persists_bronze_common_and_specific_rows_in_one_transaction(settings):
    connection = RecordingConnection()
    database = database_with_connection(settings, connection)

    database.insert_cartera_chunk([caja_record()], [])

    statements = {sql: rows for sql, rows in connection.recording_cursor.executed_many}
    sql_text = "\n".join(statements)
    assert connection.began and connection.committed and not connection.rolled_back
    assert "raw_cartera_caja_arequipa" in sql_text
    assert "`NRO_DOC_TIT`" in sql_text and "`NRO_DOC_TIT_2`" in sql_text
    assert "cartera_operaciones" in sql_text
    assert "cartera_contactos" in sql_text
    assert "cartera_direcciones" in sql_text
    assert "cartera_caja_arequipa_detalle" in sql_text
    assert "cartera_avales" in sql_text
    assert "cartera_garantias" in sql_text
    raw_rows = next(rows for sql, rows in statements.items() if "raw_cartera_caja_arequipa" in sql)
    assert len(raw_rows[0]) == 72


def test_caja_chunk_rolls_back_when_a_specific_child_insert_fails(settings):
    connection = RecordingConnection(fail_table="cartera_garantias")
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        database.insert_cartera_chunk([caja_record()], [])

    assert connection.began
    assert connection.rolled_back
    assert not connection.committed


def test_caja_bronze_ddl_uses_text_for_long_fields_and_preserves_source_order():
    ddl_path = Path(__file__).parents[2] / "database/sql/013_create_raw_cartera_caja_arequipa.sql"
    ddl = ddl_path.read_text(encoding="utf-8")
    declared_columns = re.findall(r"^\s+`([^`]+)`\s+", ddl, flags=re.MULTILINE)
    source_columns = declared_columns[:67]
    long_text_fields = {
        "DIR_LEGAL",
        "REF_LEGAL",
        "DIR_GES",
        "REF_GES",
        "ACTIVIDAD",
        "DIR_NEG",
        "DIR_AVAL",
        "REF_AVAL",
    }

    assert source_columns == list(CAJA_AREQUIPA_BRONZE_COLUMNS)
    assert len(source_columns) == 67
    for field in long_text_fields:
        assert re.search(rf"^\s+`{field}` TEXT NULL,$", ddl, flags=re.MULTILINE)
