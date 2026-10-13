from __future__ import annotations

from datetime import date, datetime

from openpyxl import Workbook

from src.domain.models import WANDOO_SOURCE_COLUMNS
from src.parsers.cartera_parser import CsvCarteraParser, XlsxCarteraParser
from src.profiles.carteras.wandoo import WandooV1Profile


def test_csv_parser_preserves_textual_identifiers(tmp_path):
    path = tmp_path / "wandoo.csv"
    values = ["" for _ in WANDOO_SOURCE_COLUMNS]
    values[WANDOO_SOURCE_COLUMNS.index("DNI")] = "00003862"
    values[WANDOO_SOURCE_COLUMNS.index("Numero de Prestamo")] = "7277-1292-001"
    path.write_text(
        ";".join(WANDOO_SOURCE_COLUMNS) + "\n" + ";".join(values) + "\n",
        encoding="utf-8",
    )

    row = next(CsvCarteraParser(WandooV1Profile()).rows(path))

    assert row.values["DNI"].value == "00003862"
    assert row.values["Numero de Prestamo"].value == "7277-1292-001"


def test_xlsx_parser_uses_real_epoch_for_numeric_dates(tmp_path):
    path = tmp_path / "wandoo.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(WANDOO_SOURCE_COLUMNS)
    values = [None for _ in WANDOO_SOURCE_COLUMNS]
    values[WANDOO_SOURCE_COLUMNS.index("DNI")] = "00003862"
    values[WANDOO_SOURCE_COLUMNS.index("Numero de Prestamo")] = "7277-1292-001"
    values[WANDOO_SOURCE_COLUMNS.index("Fecha otorgamiento crédito")] = 45905
    worksheet.append(values)
    workbook.save(path)

    row = next(XlsxCarteraParser(WandooV1Profile()).rows(path))
    record, errors = WandooV1Profile().normalize(
        row,
        batch_id=1,
        source_file=path.name,
        ingested_at=datetime(2026, 10, 13, 12, 0, 0),
        error_value_max_length=100,
    )

    assert errors == []
    assert record is not None
    assert record.detail.fecha_otorgamiento_credito == date(2025, 9, 5)
