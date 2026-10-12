from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook

from src.domain.models import CONFIANZA_SOURCE_COLUMNS
from src.parsers.cartera_parser import CsvCarteraParser, XlsxCarteraParser
from src.profiles.carteras.confianza import ConfianzaV1Profile


def test_csv_parser_preserves_confianza_identifiers_with_leading_zeroes(tmp_path: Path):
    path = tmp_path / "confianza.csv"
    values = ["" for _ in CONFIANZA_SOURCE_COLUMNS]
    values[CONFIANZA_SOURCE_COLUMNS.index("DNI")] = "00003862"
    values[CONFIANZA_SOURCE_COLUMNS.index("Cuenta Cliente")] = "00001234"
    values[CONFIANZA_SOURCE_COLUMNS.index("Operacion")] = "00005678"
    path.write_text(
        ";".join(CONFIANZA_SOURCE_COLUMNS) + "\n" + ";".join(values) + "\n",
        encoding="utf-8-sig",
    )

    row = next(CsvCarteraParser(ConfianzaV1Profile()).rows(path))

    assert row.values["DNI"].value == "00003862"
    assert row.values["Cuenta Cliente"].value == "00001234"
    assert row.values["Operacion"].value == "00005678"


def test_xlsx_parser_keeps_epoch_for_excel_serial_cast_date(tmp_path: Path):
    path = tmp_path / "confianza.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(CONFIANZA_SOURCE_COLUMNS)
    values = [None for _ in CONFIANZA_SOURCE_COLUMNS]
    values[CONFIANZA_SOURCE_COLUMNS.index("DNI")] = "00003862"
    values[CONFIANZA_SOURCE_COLUMNS.index("Cuenta Cliente")] = "00001234"
    values[CONFIANZA_SOURCE_COLUMNS.index("Operacion")] = "00005678"
    values[CONFIANZA_SOURCE_COLUMNS.index("Fecha Castigo")] = 43062
    worksheet.append(values)
    workbook.save(path)

    row = next(XlsxCarteraParser(ConfianzaV1Profile()).rows(path))

    cast_date = row.values["Fecha Castigo"]
    assert cast_date.value == 43062
    assert cast_date.workbook_epoch == datetime(1899, 12, 30)

    record, errors = ConfianzaV1Profile().normalize(
        row,
        batch_id=77,
        source_file="confianza.xlsx",
        ingested_at=datetime(2026, 10, 12, 15, 0, 0),
        error_value_max_length=100,
    )
    assert errors == []
    assert record is not None
    assert record.operation.fecha_castigo == date(2017, 11, 23)
