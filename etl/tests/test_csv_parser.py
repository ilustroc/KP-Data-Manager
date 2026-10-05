from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.errors import StructuralFileError
from src.parsers.csv_parser import CsvPaymentParser


@pytest.mark.parametrize("delimiter", [";", ","])
def test_csv_streams_supported_delimiters(tmp_path: Path, delimiter: str) -> None:
    path = tmp_path / "pagos.csv"
    path.write_text(
        delimiter.join(["FECHA", "MONTO", "RECAUDO", "OPERACION"])
        + "\n"
        + delimiter.join(["2026-10-01", "200", "BCP", "0060814"])
        + "\n",
        encoding="utf-8",
    )

    rows = CsvPaymentParser().rows(path)
    row = next(rows)

    assert iter(rows) is rows
    assert row.values["OPERACION"].value == "0060814"


def test_csv_accepts_utf8_bom_and_trimmed_headers(tmp_path: Path) -> None:
    path = tmp_path / "pagos.csv"
    path.write_text("\ufeff Fecha ; Monto ; Recaudo \n01/10/2026;200;BCP\n", encoding="utf-8")

    row = next(CsvPaymentParser().rows(path))

    assert row.values["FECHA"].value == "01/10/2026"
    assert row.values["DOCUMENTO"].value is None
    assert row.values["HORA"].value is None


def test_missing_required_header_is_structural_error(tmp_path: Path) -> None:
    path = tmp_path / "pagos.csv"
    path.write_text("FECHA;RECAUDO\n2026-10-01;BCP\n", encoding="utf-8")

    with pytest.raises(StructuralFileError, match="MONTO"):
        next(CsvPaymentParser().rows(path))


def test_invalid_utf8_is_diagnosed_as_structural_error(tmp_path: Path) -> None:
    path = tmp_path / "pagos.csv"
    path.write_bytes(b"FECHA;MONTO;RECAUDO\n2026-10-01;200;BCP\xff\n")

    with pytest.raises(StructuralFileError, match="UTF-8"):
        list(CsvPaymentParser().rows(path))
