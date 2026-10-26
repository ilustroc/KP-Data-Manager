from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.db import MySqlDatabase
from src.domain.models import (
    CAJA_AREQUIPA_BRONZE_COLUMNS,
    CAJA_AREQUIPA_SOURCE_COLUMNS,
    COMPARTAMOS_BRONZE_COLUMNS,
    COMPARTAMOS_SOURCE_COLUMNS,
    CONFIANZA_BRONZE_COLUMNS,
    CONFIANZA_SOURCE_COLUMNS,
    WANDOO_BRONZE_COLUMNS,
    WANDOO_SOURCE_COLUMNS,
    CellValue,
    SourceRow,
)
from src.profiles.carteras.caja_arequipa import CajaArequipaV1Profile
from src.profiles.carteras.compartamos import CompartamosV1Profile
from src.profiles.carteras.confianza import ConfianzaV1Profile
from src.profiles.carteras.wandoo import WandooV1Profile


class RecordingCursor:
    def __init__(self, *, fail_table: str | None = None) -> None:
        self.fail_table = fail_table
        self.last_sql = ""
        self.last_values: tuple[object, ...] = ()
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
        self.last_values = tuple(values)

    def fetchall(self):
        if (
            "raw_cartera_caja_arequipa" in self.last_sql
            or "raw_cartera_compartamos" in self.last_sql
            or "raw_cartera_confianza" in self.last_sql
            or "raw_cartera_wandoo" in self.last_sql
        ):
            return [
                {"raw_id": 77 + index, "source_row": source_row}
                for index, source_row in enumerate(self.last_values[1:])
            ]
        if "cartera_operaciones" in self.last_sql:
            return [
                {"id": 88 + index, "source_raw_id": source_raw_id}
                for index, source_raw_id in enumerate(self.last_values[1:])
            ]
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


def compartamos_record(disbursement: object = "2004"):
    values = {column: CellValue(None) for column in COMPARTAMOS_SOURCE_COLUMNS}
    values.update(
        {
            "Ctacliente": CellValue("001"),
            "Operación": CellValue("002"),
            "NumDoc": CellValue("00001234"),
            "Skapital": CellValue("100.00"),
            "Telefono1": CellValue("#900111222"),
            "Direccion Cliente": CellValue("Dirección sintética"),
            "Documento": CellValue("AUX-1"),
            "TipCambio": CellValue("0"),
            "FecDesembolso": CellValue(disbursement),
        }
    )
    record, errors = CompartamosV1Profile().normalize(
        SourceRow(2, values),
        batch_id=55,
        source_file="compartamos.xlsx",
        ingested_at=datetime(2026, 10, 6, 21, 0, 0),
        error_value_max_length=100,
    )
    assert errors == [] and record is not None
    return record


def confianza_record():
    values = {column: CellValue(None) for column in CONFIANZA_SOURCE_COLUMNS}
    values.update(
        {
            "DNI": CellValue("00003862"),
            "Cuenta Cliente": CellValue("001"),
            "Operacion": CellValue("002"),
            "Saldo Capital MN": CellValue("100.00"),
            "Interés Compensatorio": CellValue("10.00"),
            "Interés Moratorio": CellValue("1.00"),
            "Telefono": CellValue("934043966"),
            "Calle y Numero": CellValue("Dirección sintética"),
            "Moneda": CellValue("0"),
            "Estado de la Operación": CellValue("CASTIGADO"),
        }
    )
    record, errors = ConfianzaV1Profile().normalize(
        SourceRow(2, values),
        batch_id=66,
        source_file="confianza.xlsx",
        ingested_at=datetime(2026, 10, 12, 15, 0, 0),
        error_value_max_length=100,
    )
    assert errors == [] and record is not None
    return record


def wandoo_record(
    *,
    source_row: int = 2,
    saldo_deudor: str = "337.55",
    dias_mora: str = "18",
):
    values = {column: CellValue(None) for column in WANDOO_SOURCE_COLUMNS}
    values.update(
        {
            "DNI": CellValue("00003862"),
            "Numero de Prestamo": CellValue("7277-1292-001"),
            "Saldo deudor": CellValue(saldo_deudor),
            "Departamento": CellValue("Loreto"),
            "Provincia": CellValue("Maynas"),
            "Distrito": CellValue("Iquitos"),
            "Días de mora": CellValue(dias_mora),
            "Producto crediticio": CellValue("Micropréstamo"),
            "Estado Cobranza Actual": CellValue("Prejudicial externa"),
            "Fecha otorgamiento crédito": CellValue(date(2025, 9, 5)),
            "Cosecha": CellValue("WANDOO_1"),
        }
    )
    record, errors = WandooV1Profile().normalize(
        SourceRow(source_row, values),
        batch_id=77,
        source_file="wandoo.xlsx",
        ingested_at=datetime(2026, 10, 13, 15, 0, 0),
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
    assert len(raw_rows[0]) == 71


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
    source_columns = declared_columns[:66]
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
    assert len(source_columns) == 66
    assert source_columns[-1] == "COSECHA"
    assert "CADENA" not in source_columns
    assert declared_columns[66:] == [
        "raw_id",
        "batch_id",
        "source_row",
        "source_file",
        "row_hash",
        "ingested_at",
    ]
    for field in long_text_fields:
        assert re.search(rf"^\s+`{field}` TEXT NULL,$", ddl, flags=re.MULTILINE)


def test_compartamos_chunk_persists_bronze_common_and_detail_rows_in_one_transaction(settings):
    connection = RecordingConnection()
    database = database_with_connection(settings, connection)

    database.insert_cartera_chunk([compartamos_record()], [])

    statements = {sql: rows for sql, rows in connection.recording_cursor.executed_many}
    sql_text = "\n".join(statements)
    assert connection.began and connection.committed and not connection.rolled_back
    assert "raw_cartera_compartamos" in sql_text
    assert "cartera_operaciones" in sql_text
    assert "cartera_contactos" in sql_text
    assert "cartera_direcciones" in sql_text
    assert "cartera_compartamos_detalle" in sql_text
    raw_rows = next(rows for sql, rows in statements.items() if "raw_cartera_compartamos" in sql)
    detail_rows = next(
        rows for sql, rows in statements.items() if "cartera_compartamos_detalle" in sql
    )
    assert len(raw_rows[0]) == 35
    assert detail_rows[0][7] == 2004


def test_compartamos_chunk_rolls_back_when_detail_insert_fails(settings):
    connection = RecordingConnection(fail_table="cartera_compartamos_detalle")
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        database.insert_cartera_chunk([compartamos_record()], [])

    assert connection.began
    assert connection.rolled_back
    assert not connection.committed


def test_compartamos_full_disbursement_date_reaches_common_date_and_detail_year(settings):
    connection = RecordingConnection()
    database = database_with_connection(settings, connection)

    database.insert_cartera_chunk([compartamos_record(date(2024, 3, 30))], [])

    statements = {sql: rows for sql, rows in connection.recording_cursor.executed_many}
    operation_rows = next(
        rows for sql, rows in statements.items() if "cartera_operaciones" in sql
    )
    detail_rows = next(
        rows for sql, rows in statements.items() if "cartera_compartamos_detalle" in sql
    )
    assert operation_rows[0][14] == date(2024, 3, 30)
    assert detail_rows[0][7] == 2024


def test_compartamos_ddl_preserves_exact_source_order_and_expected_types():
    root = Path(__file__).parents[2]
    bronze_ddl = (root / "database/sql/017_create_raw_cartera_compartamos.sql").read_text(
        encoding="utf-8"
    )
    detail_ddl = (
        root / "database/sql/018_create_cartera_compartamos_detalle.sql"
    ).read_text(encoding="utf-8")
    declared_columns = re.findall(r"^\s+`([^`]+)`\s+", bronze_ddl, flags=re.MULTILINE)

    assert declared_columns[:30] == list(COMPARTAMOS_BRONZE_COLUMNS)
    assert len(COMPARTAMOS_SOURCE_COLUMNS) == 30
    assert len(COMPARTAMOS_BRONZE_COLUMNS) == 30
    assert "SSS" not in declared_columns[:30]
    assert declared_columns[30:] == [
        "raw_id",
        "batch_id",
        "source_row",
        "source_file",
        "row_hash",
        "ingested_at",
    ]
    assert re.search(r"^\s+`Direccion Cliente` TEXT NULL,$", bronze_ddl, flags=re.MULTILINE)
    assert re.search(r"^\s+`Direccion Negocio` TEXT NULL,$", bronze_ddl, flags=re.MULTILINE)
    assert not re.search(r"^\s*UNIQUE\s", bronze_ddl, flags=re.MULTILINE | re.IGNORECASE)
    assert "`tipo_cambio` DECIMAL(18,6) NULL" in detail_ddl
    assert "`anio_desembolso` SMALLINT UNSIGNED NULL" in detail_ddl
    assert "`fecha_desembolso`" not in detail_ddl
    assert not re.search(r"^\s+`sss`\s+", detail_ddl, flags=re.MULTILINE | re.IGNORECASE)
    assert "FOREIGN KEY" not in detail_ddl.upper()


def test_confianza_chunk_persists_bronze_common_and_detail_rows_in_one_transaction(settings):
    connection = RecordingConnection()
    database = database_with_connection(settings, connection)

    database.insert_cartera_chunk([confianza_record()], [])

    statements = {sql: rows for sql, rows in connection.recording_cursor.executed_many}
    sql_text = "\n".join(statements)
    assert connection.began and connection.committed and not connection.rolled_back
    assert "raw_cartera_confianza" in sql_text
    assert "`interes_vencido`" in sql_text
    assert "`codigo_sucursal_credito`" in sql_text
    assert "`estado_operacion`" in sql_text
    assert "`Interés Vencido`" not in sql_text
    assert "`Código de Sucursal de Crédito`" not in sql_text
    assert "`Estado de la Operación`" not in sql_text
    assert "cartera_operaciones" in sql_text
    assert "cartera_contactos" in sql_text
    assert "cartera_direcciones" in sql_text
    assert "cartera_confianza_detalle" in sql_text
    raw_rows = next(rows for sql, rows in statements.items() if "raw_cartera_confianza" in sql)
    detail_rows = next(
        rows for sql, rows in statements.items() if "cartera_confianza_detalle" in sql
    )
    operation_rows = next(
        rows for sql, rows in statements.items() if "cartera_operaciones" in sql
    )
    assert len(raw_rows[0]) == 32
    assert operation_rows[0][8] == "PEN"
    assert operation_rows[0][9] == Decimal("100.00")
    assert operation_rows[0][10] == Decimal("111.00")
    assert detail_rows[0][1] == "00003862"
    assert detail_rows[0][10] == "0"
    assert detail_rows[0][15] == "CASTIGADO"


def test_confianza_chunk_rolls_back_when_detail_insert_fails(settings):
    connection = RecordingConnection(fail_table="cartera_confianza_detalle")
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        database.insert_cartera_chunk([confianza_record()], [])

    assert connection.began
    assert connection.rolled_back
    assert not connection.committed


def test_confianza_ddl_preserves_exact_source_order_metadata_and_detail_types():
    root = Path(__file__).parents[2]
    bronze_ddl = (root / "database/sql/020_create_raw_cartera_confianza.sql").read_text(
        encoding="utf-8"
    )
    detail_ddl = (
        root / "database/sql/021_create_cartera_confianza_detalle.sql"
    ).read_text(encoding="utf-8")
    declared_columns = re.findall(r"^\s+`([^`]+)`\s+", bronze_ddl, flags=re.MULTILINE)
    detail_columns = re.findall(r"^\s+`([^`]+)`\s+", detail_ddl, flags=re.MULTILINE)

    assert declared_columns[:27] == list(CONFIANZA_BRONZE_COLUMNS)
    assert len(CONFIANZA_SOURCE_COLUMNS) == 27
    assert len(CONFIANZA_BRONZE_COLUMNS) == 27
    assert declared_columns[27:] == [
        "raw_id",
        "batch_id",
        "source_row",
        "source_file",
        "row_hash",
        "ingested_at",
    ]
    assert all(column.isascii() for column in declared_columns)
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", column) for column in declared_columns)
    assert re.search(r"^\s+`calle_numero` TEXT NULL,$", bronze_ddl, flags=re.MULTILINE)
    assert not re.search(r"^\s*UNIQUE\s", bronze_ddl, flags=re.MULTILINE | re.IGNORECASE)
    for field in (
        "saldo_capital_mo",
        "saldo_capital_mn",
        "interes_vencido",
        "interes_compensatorio",
        "interes_moratorio",
        "seguros",
        "comisiones",
        "gastos_judiciales",
    ):
        assert re.search(
            rf"`{field}` DECIMAL\(15,\s*2\) NULL",
            detail_ddl,
        )
    assert detail_columns == [
        "id",
        "operacion_id",
        "documento_cliente",
        "saldo_capital_mo",
        "saldo_capital_mn",
        "interes_vencido",
        "interes_compensatorio",
        "interes_moratorio",
        "seguros",
        "comisiones",
        "gastos_judiciales",
        "moneda_origen",
        "codigo_sucursal_credito",
        "nombre_sucursal_credito",
        "corredor",
        "nombre_modulo_origen",
        "estado_operacion",
        "batch_id",
        "source_raw_id",
        "created_at",
    ]
    assert "FOREIGN KEY" not in bronze_ddl.upper()
    assert "FOREIGN KEY" not in detail_ddl.upper()


def test_wandoo_chunk_persists_bronze_common_address_and_detail_in_one_transaction(settings):
    connection = RecordingConnection()
    database = database_with_connection(settings, connection)

    database.insert_cartera_chunk([wandoo_record()], [])

    statements = {sql: rows for sql, rows in connection.recording_cursor.executed_many}
    sql_text = "\n".join(statements)
    assert connection.began and connection.committed and not connection.rolled_back
    assert "raw_cartera_wandoo" in sql_text
    assert "cartera_operaciones" in sql_text
    assert "cartera_direcciones" in sql_text
    assert "cartera_wandoo_detalle" in sql_text
    assert "cartera_contactos" not in sql_text
    raw_rows = next(rows for sql, rows in statements.items() if "raw_cartera_wandoo" in sql)
    operation_rows = next(rows for sql, rows in statements.items() if "cartera_operaciones" in sql)
    detail_rows = next(rows for sql, rows in statements.items() if "cartera_wandoo_detalle" in sql)
    assert len(raw_rows[0]) == 24
    assert operation_rows[0][2] == "00003862"
    assert operation_rows[0][4] == "000003862"
    assert operation_rows[0][5] == "7277-1292-001"
    assert operation_rows[0][6] == wandoo_record().operation.identificador_origen
    assert operation_rows[0][8] is None
    assert operation_rows[0][9] == Decimal("337.55")
    assert operation_rows[0][10] == Decimal("337.55")
    assert operation_rows[0][12] is None
    assert operation_rows[0][16] == 18
    assert detail_rows[0][1] == "00003862"
    assert detail_rows[0][4] == Decimal("337.55")
    assert operation_rows[0][9] == operation_rows[0][10] == detail_rows[0][4]
    assert detail_rows[0][8] == 18


def test_wandoo_equal_loan_instances_keep_distinct_bronze_and_silver_rows(settings):
    connection = RecordingConnection()
    database = database_with_connection(settings, connection)
    first = wandoo_record()
    second = wandoo_record(source_row=3, saldo_deudor="500.00", dias_mora="19")

    database.insert_cartera_chunk([first, second], [])

    statements = {sql: rows for sql, rows in connection.recording_cursor.executed_many}
    raw_rows = next(rows for sql, rows in statements.items() if "raw_cartera_wandoo" in sql)
    operation_rows = next(
        rows for sql, rows in statements.items() if "cartera_operaciones" in sql
    )

    assert connection.committed and not connection.rolled_back
    assert [row[20] for row in raw_rows] == [2, 3]
    assert [row[27] for row in operation_rows] == [77, 78]
    assert [row[6] for row in operation_rows] == [
        first.operation.identificador_origen,
        second.operation.identificador_origen,
    ]
    assert operation_rows[0][6] == operation_rows[1][6]
    assert [row[9] for row in operation_rows] == [Decimal("337.55"), Decimal("500.00")]


def test_wandoo_chunk_rolls_back_when_detail_insert_fails(settings):
    connection = RecordingConnection(fail_table="cartera_wandoo_detalle")
    database = database_with_connection(settings, connection)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        database.insert_cartera_chunk([wandoo_record()], [])

    assert connection.began
    assert connection.rolled_back
    assert not connection.committed


def test_wandoo_ddl_preserves_exact_source_order_metadata_and_detail_types():
    root = Path(__file__).parents[2]
    bronze_ddl = (root / "database/sql/022_create_raw_cartera_wandoo.sql").read_text(
        encoding="utf-8"
    )
    detail_ddl = (
        root / "database/sql/023_create_cartera_wandoo_detalle.sql"
    ).read_text(encoding="utf-8")
    declared_columns = re.findall(r"^\s+`([^`]+)`\s+", bronze_ddl, flags=re.MULTILINE)
    detail_columns = re.findall(r"^\s+`([^`]+)`\s+", detail_ddl, flags=re.MULTILINE)

    assert declared_columns[:19] == list(WANDOO_BRONZE_COLUMNS)
    assert len(WANDOO_SOURCE_COLUMNS) == 19
    assert len(WANDOO_BRONZE_COLUMNS) == 19
    assert declared_columns[19:] == [
        "raw_id",
        "batch_id",
        "source_row",
        "source_file",
        "row_hash",
        "ingested_at",
    ]
    assert all(column.isascii() for column in declared_columns)
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", column) for column in declared_columns)
    assert not re.search(r"^\s*UNIQUE\s", bronze_ddl, flags=re.MULTILINE | re.IGNORECASE)
    assert "`saldo_deudor` DECIMAL(15,2) NULL" in detail_ddl
    assert "`total_soles_pagados` DECIMAL(15,2) NULL" in detail_ddl
    assert "`fecha_ultimo_pago` DATE NULL" in detail_ddl
    assert "`fecha_otorgamiento_credito` DATE NULL" in detail_ddl
    assert detail_columns == [
        "id",
        "operacion_id",
        "documento_cliente",
        "recuento_prestamos_pagados",
        "nacionalidad",
        "saldo_deudor",
        "fecha_ultimo_pago",
        "total_soles_pagados",
        "edad",
        "dias_mora",
        "producto_crediticio",
        "fuente_ingreso",
        "estado_cobranza_actual",
        "contactabilidad_interna",
        "fecha_otorgamiento_credito",
        "actividad_laboral",
        "batch_id",
        "source_raw_id",
        "created_at",
    ]
    assert "FOREIGN KEY" not in bronze_ddl.upper()
    assert "FOREIGN KEY" not in detail_ddl.upper()
