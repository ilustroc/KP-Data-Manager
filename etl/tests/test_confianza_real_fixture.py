from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl.utils.datetime import to_excel

from src.domain.models import CONFIANZA_SOURCE_COLUMNS, ConfianzaPortfolioRecord
from src.parsers.cartera_parser import XlsxCarteraParser
from src.profiles.carteras.confianza import ConfianzaV1Profile


def private_fixture_path() -> Path:
    configured_path = os.getenv("CONFIANZA_REAL_FIXTURE_PATH")
    if configured_path is None:
        pytest.skip("Configura CONFIANZA_REAL_FIXTURE_PATH para validar la muestra privada.")

    path = Path(configured_path)
    if not path.is_file():
        pytest.skip("La muestra privada de Confianza no está disponible en la ruta configurada.")
    return path


def test_real_confianza_sample_matches_v1_contract_without_persistence():
    path = private_fixture_path()
    profile = ConfianzaV1Profile()
    source_rows = list(XlsxCarteraParser(profile).rows(path))
    normalized = [
        profile.normalize(
            source_row,
            batch_id=1,
            source_file=path.name,
            ingested_at=datetime(2026, 10, 12, 12, 0, 0),
            error_value_max_length=100,
        )
        for source_row in source_rows
    ]
    errors = [error for _, row_errors in normalized for error in row_errors]
    records = [record for record, _ in normalized if record is not None]

    assert len(profile.expected_headers) == 27
    assert len(source_rows) == 12
    assert errors == []
    assert len(records) == 12

    by_document = {record.operation.documento_cliente: record for record in records}
    first_record = by_document["00003862"]
    second_record = by_document["00009743"]

    assert first_record.operation.documento_cliente == "00003862"
    assert second_record.operation.documento_cliente == "00009743"
    assert first_record.operation.cuenta == "3303632"
    assert first_record.operation.operacion == "6878399"
    assert first_record.operation.fecha_castigo == date(2017, 11, 23)
    first_source_row = next(
        row for row in source_rows if row.values["DNI"].value == "00003862"
    )
    cast_date_cell = first_source_row.values["Fecha Castigo"]
    assert to_excel(cast_date_cell.value, cast_date_cell.workbook_epoch) == 43062
    assert [contact.telefono for contact in first_record.contacts] == ["961931445"]
    assert first_record.operation.moneda is None
    assert first_record.detail.moneda_origen == "0"
    assert first_record.operation.saldo_capital == Decimal("337.55")
    assert first_record.operation.saldo_capital == first_record.detail.saldo_capital_mn
    assert first_record.operation.deuda_total is None
    assert first_record.operation.cosecha == "CONFIANZA"
    assert first_record.detail.nombre_modulo_origen == "INCLUSION"
    assert first_record.detail.estado_operacion == "PREJUDICIAL"

    invalid_phone_records = [
        record
        for record in records
        if record.source_values[CONFIANZA_SOURCE_COLUMNS.index("Telefono")] == "61577350"
    ]
    assert len(invalid_phone_records) == 1
    assert invalid_phone_records[0].contacts == ()
    assert all(record.operation.cosecha == "CONFIANZA" for record in records)
    assert all(record.operation.moneda is None for record in records)
    assert all(record.detail.moneda_origen == "0" for record in records)
    assert all(record.operation.deuda_total is None for record in records)
    assert all(isinstance(record, ConfianzaPortfolioRecord) for record in records)
