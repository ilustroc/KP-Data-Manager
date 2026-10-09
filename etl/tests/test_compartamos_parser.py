from pathlib import Path

import pytest
from openpyxl import Workbook

from src.domain.errors import StructuralFileError
from src.domain.models import COMPARTAMOS_SOURCE_COLUMNS
from src.parsers.cartera_parser import CsvCarteraParser, XlsxCarteraParser
from src.profiles.carteras.compartamos import CompartamosV1Profile


def test_csv_parser_preserves_text_identifiers(tmp_path: Path):
    path = tmp_path / "compartamos.csv"
    values = ["" for _ in COMPARTAMOS_SOURCE_COLUMNS]
    values[0] = "001234"
    values[1] = "000567"
    values[COMPARTAMOS_SOURCE_COLUMNS.index("NumDoc")] = "00112233"
    path.write_text(
        ";".join(COMPARTAMOS_SOURCE_COLUMNS) + "\n" + ";".join(values) + "\n",
        encoding="utf-8-sig",
    )

    row = next(CsvCarteraParser(CompartamosV1Profile()).rows(path))

    assert row.values["Ctacliente"].value == "001234"
    assert row.values["Operación"].value == "000567"
    assert row.values["NumDoc"].value == "00112233"


def test_xlsx_parser_accepts_nbsp_only_as_external_header_padding(tmp_path: Path):
    path = tmp_path / "compartamos.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append([f"\u00a0{header}\u00a0" for header in COMPARTAMOS_SOURCE_COLUMNS])
    values = [None for _ in COMPARTAMOS_SOURCE_COLUMNS]
    values[0] = "001234"
    values[1] = "000567"
    values[COMPARTAMOS_SOURCE_COLUMNS.index("NumDoc")] = "00112233"
    worksheet.append(values)
    workbook.save(path)

    row = next(XlsxCarteraParser(CompartamosV1Profile()).rows(path))

    assert row.values["Ctacliente"].value == "001234"
    assert row.values["NumDoc"].value == "00112233"


def test_parser_rejects_obsolete_sss_column(tmp_path: Path):
    path = tmp_path / "compartamos.csv"
    obsolete_headers = (
        *COMPARTAMOS_SOURCE_COLUMNS[:3],
        "SSS",
        *COMPARTAMOS_SOURCE_COLUMNS[3:],
    )
    path.write_text(
        ";".join(obsolete_headers) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(StructuralFileError, match="30 columnas"):
        next(CsvCarteraParser(CompartamosV1Profile()).rows(path))
