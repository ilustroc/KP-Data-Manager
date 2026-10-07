from pathlib import Path

from openpyxl import Workbook

from src.domain.models import CAJA_AREQUIPA_SOURCE_HEADERS
from src.parsers.cartera_parser import CsvCarteraParser, XlsxCarteraParser
from src.profiles.carteras.caja_arequipa import CajaArequipaV1Profile


def test_csv_parser_preserves_both_duplicate_document_positions(tmp_path: Path):
    path = tmp_path / "caja.csv"
    values = ["" for _ in CAJA_AREQUIPA_SOURCE_HEADERS]
    values[0] = "00001234"
    values[4] = "001804548"
    values[5] = "002435410"
    values[30] = "00001234"
    path.write_text(
        ";".join(CAJA_AREQUIPA_SOURCE_HEADERS) + "\n" + ";".join(values) + "\n",
        encoding="utf-8-sig",
    )

    row = next(CsvCarteraParser(CajaArequipaV1Profile()).rows(path))

    assert row.values["NRO_DOC_TIT_1"].value == "00001234"
    assert row.values["NRO_DOC_TIT_2"].value == "00001234"


def test_xlsx_parser_carries_workbook_epoch_for_numeric_dates(tmp_path: Path):
    path = tmp_path / "caja.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(CAJA_AREQUIPA_SOURCE_HEADERS)
    values = [None for _ in CAJA_AREQUIPA_SOURCE_HEADERS]
    values[0] = "00001234"
    values[4] = 1804548
    values[5] = 2435410
    values[30] = "00001234"
    values[35] = 42668
    worksheet.append(values)
    workbook.save(path)

    row = next(XlsxCarteraParser(CajaArequipaV1Profile()).rows(path))

    assert row.values["CUENTA"].value == 1804548
    assert row.values["OPERACION"].value == 2435410
    assert row.values["FEC_DES"].workbook_epoch is not None
