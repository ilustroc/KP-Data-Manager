from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from src.domain.models import BBVA_SOURCE_COLUMNS
from src.parsers.cartera_parser import CsvCarteraParser, XlsxCarteraParser
from src.profiles.carteras.bbva import BbvaV1Profile


def test_bbva_csv_parser_streams_semicolon_rows_and_preserves_leading_zeroes(tmp_path: Path):
    path = tmp_path / "bbva.csv"
    values = ["" for _ in BBVA_SOURCE_COLUMNS]
    values[BBVA_SOURCE_COLUMNS.index("CODCENTRAL")] = "014898140"
    values[BBVA_SOURCE_COLUMNS.index("CONTRATO")] = "00110310039600774622"
    values[BBVA_SOURCE_COLUMNS.index("numdoc")] = "01116950"
    path.write_text(
        ";".join(BBVA_SOURCE_COLUMNS) + "\n" + ";".join(values) + "\n",
        encoding="utf-8-sig",
    )

    row = next(CsvCarteraParser(BbvaV1Profile()).rows(path))

    assert row.values["CODCENTRAL"].value == "014898140"
    assert row.values["CONTRATO"].value == "00110310039600774622"
    assert row.values["numdoc"].value == "01116950"


def test_bbva_xlsx_parser_uses_read_only_cells_and_preserves_text_identifiers(tmp_path: Path):
    path = tmp_path / "bbva.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(BBVA_SOURCE_COLUMNS)
    values = [None for _ in BBVA_SOURCE_COLUMNS]
    values[BBVA_SOURCE_COLUMNS.index("CODCENTRAL")] = "014898140"
    values[BBVA_SOURCE_COLUMNS.index("CONTRATO")] = "00110310039600774622"
    values[BBVA_SOURCE_COLUMNS.index("numdoc")] = "01116950"
    worksheet.append(values)
    workbook.save(path)

    row = next(XlsxCarteraParser(BbvaV1Profile()).rows(path))

    assert row.values["CODCENTRAL"].value == "014898140"
    assert row.values["CONTRATO"].value == "00110310039600774622"
    assert row.values["numdoc"].value == "01116950"
